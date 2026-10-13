"""The irreversible edges, by exact argv per command segment (#839): host merge, approve, admin
and branch protection, force push, a push to the default branch, deploy (design 4.7), outward
send, and a bare gh pr create for a recorded item. Nothing else is refused here, and a call
these guards cannot split is logged, never refused."""

from fnmatch import fnmatchcase
import posixpath
from pathlib import Path, PurePosixPath
import re
import shlex

from wuwei.guards import RAISE, Guard
from wuwei.shell import UNPARSED, _cwd


VERBS = {
    'kubectl': ('apply', 'create', 'replace', 'rollout', 'patch'),
    'helm': ('install', 'upgrade', 'rollback'), 'terraform': ('apply', 'destroy'),
    'tofu': ('apply', 'destroy'), 'pulumi': ('up', 'update'),
    'netlify': ('deploy',), 'ntl': ('deploy',), 'fly': ('deploy', 'launch'),
    'flyctl': ('deploy', 'launch'), 'docker': ('push',), 'podman': ('push',),
}
CLOUD_VERBS = {'deploy', 'deployment', 'deployments', 'create-deployment',
               'create-stack', 'update-stack', 'execute-change-set',
               'update-function-code', 'update-service', 'up', 'start-deployment'}
PROGRAMS = ('git', 'gh', *VERBS, 'vercel', 'vc', 'gcloud', 'aws', 'az')
# Target-dependent actions stay with the hook.
PERMISSIONS_DENY = [f'Bash({command})' for command in (
    'terraform apply*', 'tofu apply*', 'kubectl apply*', 'helm install*',
    'helm upgrade*', 'pulumi up*', 'vercel*', 'vc *', 'netlify deploy*',
    'ntl deploy*', 'fly deploy*', 'flyctl deploy*', 'docker push*',
    'podman push*', 'gh release create*', 'git push --tags*', 'git push * --tags*',
    'gh pr review --approve*', 'gh pr review * --approve*', 'gh pr review * -a*',
    'gh pr merge * --admin*')]
SHELLS = ('sh', 'bash', 'zsh', 'dash', 'ksh')
# Design 4.5: wrappers that run the rest of the line, and their options that take a value.
WRAPPERS = {'command': (), 'exec': ('-a',), 'nohup': (), 'nice': ('-n', '--adjustment'),
            'sudo': ('-u', '--user', '-g', '--group', '-C', '-D', '-p', '--prompt', '-r', '-t',
                     '-U', '-T', '-R'),
            'timeout': ('-s', '--signal', '-k', '--kill-after'),
            'xargs': ('-n', '-L', '-P', '-s', '-d', '-E', '-I', '-a', '--max-args', '--max-lines',
                      '--max-procs', '--max-chars', '--delimiter', '--eof', '--replace', '--arg-file'),
            'time': ('-f', '--format', '-o', '--output')}
DEPTH = 4
# gh options that take a value, so the value is never read as a subcommand or a flag.
GH_VALUED = ('-t', '--title', '--subject', '-b', '--body', '-F', '--body-file', '-f', '--field',
             '--raw-field', '-X', '--method', '--input', '-H', '--header', '--head', '--hostname',
             '-q', '--jq', '--template', '--cache', '--ref', '-r', '--reviewer', '-B', '--base',
             '--assignee', '-l', '--label', '-m', '--milestone', '-p', '--project', '-T',
             '--match-head-commit', '-A', '--author-email', '--recover', '-R', '--repo')
PUSH_VALUED = ('--repo', '-o', '--push-option', '--receive-pack', '--exec')
# Shell words that start a command list or group; the command after them runs (review F2;
# time is a wrapper, with its -p).
RESERVED = frozenset({'{', '}', '!', 'if', 'then', 'elif', 'else', 'do', 'while', 'until', 'coproc'})
_ASSIGNMENT = re.compile(r'[A-Za-z_]\w*=')
_SEPARATORS = set(';&|()<>\n')


def _named(text, words):
    """A plain word search on the raw text, quotes, backslashes and continuations dropped (FR-002)."""
    pattern = r'(?<![\w.-])(?:' + '|'.join(map(re.escape, words)) + r')(?![\w.-])'
    return re.search(pattern, re.sub(r'''\\\n|['"\\]''', '', text)) is not None


def _cut(text):
    """The text without here-doc bodies, comments and line continuations; ValueError when a
    here-doc never ends."""
    out, pending, quote, index = [], [], '', 0
    while index < len(text):
        char = text[index]
        if quote == "'":
            quote = '' if char == "'" else quote
        elif char == '\\':
            if text[index + 1:index + 2] != '\n':
                out.append(text[index:index + 2])
            index += 2  # a continuation joins the two lines
            continue
        elif quote:
            quote = '' if char == '"' else quote
        elif char in '\'"':
            quote = char
        elif char == '#' and (not out or out[-1][-1] in ' \t\n;&|()<>'):
            end = text.find('\n', index)
            index = len(text) if end < 0 else end
            continue
        elif text.startswith('<<<', index):
            out.append('<<<')
            index += 3
            continue
        elif (match := re.match(r'<<(-?)[ \t]*([\'"]?)([^\s;&|()<>\'"]+)\2', text[index:])):
            pending.append((match[3].replace('\\', ''), match[1] == '-'))
            out.append(match[0])
            index += len(match[0])
            continue
        elif char == '\n' and pending:
            out.append(char)
            index += 1
            for delimiter, tabs in pending:
                while True:
                    if index >= len(text):
                        raise ValueError(f'unterminated here-doc; write {delimiter} alone on its last line')
                    end = text.find('\n', index)
                    end = len(text) if end < 0 else end
                    line, index = text[index:end], end + 1
                    if (line.lstrip('\t') if tabs else line) == delimiter:
                        break
            pending = []
            continue
        out.append(char)
        index += 1
    if pending:
        raise ValueError(f'unterminated here-doc; write {pending[0][0]} alone on its last line')
    return ''.join(out)


def segments(text, cwd, depth=0):
    """[(argv, env, cwd)] per simple command: shlex words split at ; & | ( ) newlines and
    redirections (a redirection drops its target), leading NAME=value words and env unwrapped,
    sh -c scripts split the same way, and a literal cd moving cwd for the later segments.
    ValueError when the text cannot be split.
    ponytail: backticks, quoted $( ) and names built at run time are not split; the code host and
    the credential layout hold them (design 9.1); split them here if a seat is seen using them."""
    if depth > DEPTH:
        raise ValueError('shells nested past the cap; run the inner command directly')
    lexer = shlex.shlex(_cut(text), posix=True, punctuation_chars=';&|()<>\n')
    lexer.whitespace, lexer.whitespace_split, lexer.commenters = ' \t\r', True, ''
    found, words, redirect, cwd = [], [], False, Path(cwd)
    for token in [*lexer, ';']:
        separator = bool(token) and set(token) <= _SEPARATORS
        if redirect and not separator:
            redirect = False
            continue
        if separator:
            redirect = ('<' in token or '>' in token) and not token.endswith('(')  # <( and >( run
            if not redirect:
                cwd = _segment(words, cwd, depth, found)
                words = []
            continue
        words.append(token)
    return found


def _segment(words, cwd, depth, found):
    """Unwrap one segment into found; returns the cwd for the next one."""
    env = {}
    while words:
        name = PurePosixPath(words[0]).name
        if _ASSIGNMENT.match(words[0]):
            key, _, env[key] = words.pop(0).partition('=')
        elif words[0] in RESERVED:  # review F2: { ! if then while do coproc and the rest
            words.pop(0)
        elif name == 'env':
            words = _env(words, env)
        elif name in WRAPPERS:
            words = _unwrap(words)
        else:
            break
    if not words:
        return cwd
    if PurePosixPath(words[0]).name in SHELLS:
        index, script = 1, False
        while index < len(words) and words[index][:1] in '-+' and len(words[index]) > 1:
            word = words[index]
            index += 1
            if word == '--':
                break
            if word in ('-o', '+o'):  # review F4: an option name, never the script
                index += 1
            elif not word.startswith(('--', '+')) and 'c' in word:
                script = True
        if script and index < len(words):
            found.extend(segments(words[index], cwd, depth + 1))
            return cwd
    found.append((words, env, cwd))
    if words[0] == 'cd' and len(words) == 2 and '$' not in words[1] and words[1] != '-':
        cwd = (cwd / Path(words[1]).expanduser()).resolve()
    return cwd


def _env(words, env):
    """The words env runs after its options and assignments; -S splits its value as a script
    (review F4). ValueError when an option's value is missing."""
    words = words[1:]
    while words and (words[0].startswith('-') or _ASSIGNMENT.match(words[0])):
        word = words.pop(0)
        if word == '--':
            break
        if _ASSIGNMENT.match(word):
            key, _, env[key] = word.partition('=')
            continue
        key, separator, value = word.partition('=')
        long = key if word.startswith('--') else None
        if long in ('--chdir', '--unset', '--split-string') or word[:2] in ('-C', '-u', '-P', '-S') and not long:
            if long and not separator or not long and len(word) == 2:
                if not words:
                    raise ValueError(f'env {word} has no value; run the command without env')
                value = words.pop(0)
            elif not long:
                value = word[2:]
            if long == '--split-string' or word[:2] == '-S' and not long:
                words = shlex.split(value) + words
    return words


def _unwrap(words):
    """The words a wrapper runs, after its own options; ValueError when they cannot be read."""
    name, index = PurePosixPath(words[0]).name, 1
    while index < len(words) and words[index].startswith('-') and words[index] != '-':
        word = words[index]
        index += 1
        if word == '--':
            break
        if word in WRAPPERS[name]:
            if index == len(words):
                raise ValueError(f'{name} {word} has no value; run the command without {name}')
            index += 1
    rest = words[index:]
    if name == 'timeout':
        if not rest or not re.fullmatch(r'\d+(?:\.\d+)?[smhd]?', rest[0]):
            raise ValueError('timeout names no duration; run the command without timeout')
        rest = rest[1:]
        if rest[:1] == ['--']:
            rest = rest[1:]
    return rest


def _scan(args, valued):
    """(words, {option: [values]}): words are the operands and the flags; an option in valued
    takes its value attached (--x=v, -Xv) or from the next word. Never raises."""
    words, values, index = [], {}, 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == '--':
            words += args[index:]
            break
        key, separator, value = arg.partition('=')
        if key not in valued and arg[:2] in valued and not arg.startswith('--'):
            key, separator, value = arg[:2], '=', arg[2:]
        if key not in valued or not arg.startswith('-'):
            words.append(arg)
            continue
        if not separator:
            value = args[index] if index < len(args) else ''
            index += 1
        values.setdefault(key, []).append(value)
    return words, values


def _last(values, *keys):
    found = [value for key in keys for value in values.get(key, [])]
    return found[-1] if found else None


def _git(args):
    """(verb, rest) after git's global options."""
    args = list(args)
    while args and args[0].startswith('-'):
        option = args.pop(0)
        if option in ('-C', '-c', '--git-dir', '--work-tree', '--namespace') and args:
            args.pop(0)
    return (args[0], args[1:]) if args else ('', [])


def _pushed(rest):
    """The branch or ref names git push's refspecs write."""
    words, values = _scan(rest, PUSH_VALUED)
    operands = [word for word in words if not word.startswith('-')]
    refspecs = operands if '--repo' in values else operands[1:]
    return [ref.lstrip('+').rsplit(':', 1)[-1].removeprefix('refs/heads/') for ref in refspecs]


def _forced(rest):
    words, _ = _scan(rest, PUSH_VALUED)
    return any(word.startswith('--force') or word == '--mirror' or word.startswith('+')
               or re.fullmatch(r'-[a-zA-Z]*f[a-zA-Z]*', word) for word in words)


def _gh(args):
    """(repository, args) with gh's -R and --repo taken out wherever they stand."""
    repo, rest, index = None, [], 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg in ('-R', '--repo'):
            repo = args[index] if index < len(args) else None
            index += 1
        elif arg.startswith(('--repo=', '-R')):
            repo = arg.removeprefix('--repo=').removeprefix('-R')
        else:
            rest.append(arg)
            if arg in GH_VALUED and index < len(args):
                rest.append(args[index])
                index += 1
    return repo, rest


def _pr(ref, repo):
    """The owner/repo#number bin/wuwei merge takes."""
    match = re.fullmatch(r'https://github\.com/([^/]+/[^/]+)/pull/(\d+)/?', ref or '')
    if match:
        return f'{match[1]}#{match[2]}'
    if ref and ref.isdecimal():
        return f'{repo or "<owner/repo>"}#{ref}'
    return ref or '<owner/repo>#<pr>'


def _recorded(root, config, *, path=None, repo=None, branch=None):
    """#534: (item, worktree) of the recorded item worktree at path, or whose branch is branch
    in repository repo; None when no recorded item matches."""
    from wuwei import merge, registry, state
    vcs = registry.load('vcs', config)
    data = state.read_state(root)
    for item, row in sorted(data['items'].items(),
                            key=lambda pair: (pair[0] not in data['approved_items'], pair[0])):
        if not isinstance(row.get('worktree'), str) or not row['worktree']:
            continue
        tree = (root / row['worktree']).resolve()
        if path is not None and tree == path:
            return item, tree
        if (branch is not None and tree.is_dir() and repo in merge.configured(root, config, tree)
                and registry.data(vcs.branch(str(tree), root=root)).get('name') == branch):
            return item, tree
    return None


def _merge(pr, admin=False):
    """Each reason starts with a guards.MERGE prefix: the floor."""
    if admin:
        return 1, f'admin merge is refused; run bin/wuwei merge {pr}, which never uses --admin'
    return 1, (f'merge policy: a PR merges only through bin/wuwei merge {pr}; it checks the policy '
               'at the head and asks the Owner step card when the owner decides')


def _approve(pr):
    return 1, ("PR approval is the owner's; post a comment review (gh pr review --comment), and "
               f'merge through bin/wuwei merge {pr}')


def _branch(cwd, root):
    from wuwei.commit_push import _item
    item = _item(cwd, root)
    return item, item.lower() if item else '<branch>'


def _default(name, cwd, root):
    """B6 lead call: a push to a default branch is a merge outside the policy."""
    item, branch = _branch(cwd, root)
    return 1, (f'push to the default branch {name} is refused; push the item branch with '
               f'git push origin HEAD:refs/heads/{branch} and raise its PR with bin/wuwei pr raise '
               f'<owner/repo> --base {name} --title <title> --body-file <file> --item {item or "<item>"}')


def _git_edge(args, cwd, root, config, env=None):
    verb, rest = _git(args)
    if verb != 'push':
        return 0, ''
    if owned := _owned(args[:len(args) - len(rest) - 1], rest, env or {}, cwd, root):
        return owned
    if _forced(rest):
        return 1, ('force-push is refused; commit the change on top and run '
                   f'git push origin HEAD:refs/heads/{_branch(cwd, root)[1]}')
    defaults = {repo['default_branch'] for repo in config['repos']}
    # ponytail: a bare git push or HEAD follows the checked-out branch, unread here; the
    # protected base branch holds it (design 9.1).
    name = next((name for name in _pushed(rest) if name in defaults), None)
    return _default(name, cwd, root) if name else (0, '')


def _owned(options, rest, env, cwd, root):
    """#879, #903: a push to a raised or claimed PR's branch (recorded on a claim), or from its
    worktree (-C, --git-dir, --work-tree, GIT_DIR, GIT_WORK_TREE included): only bin/wuwei pr act
    --push puts a gated head on it."""
    from wuwei import state
    base = Path(cwd)
    places = [base / env[key] for key in ('GIT_DIR', 'GIT_WORK_TREE') if env.get(key)]
    for index, option in enumerate(options):
        name, equals, value = option.partition('=')
        value = value if equals else options[index + 1] if index + 1 < len(options) else ''
        if name == '-C':
            base = base / value  # K2: a relative --git-dir after -C is read from there
        if name in ('-C', '--git-dir', '--work-tree'):
            places.append(base if name == '-C' else base / value)
    places = [place.resolve() for place in [Path(cwd), *places]]
    targets, data = {target.removeprefix('heads/') for target in _pushed(rest)}, state.read_state(root)
    every = bool({'--all', '--branches'} & set(rest)) or any('*' in target for target in targets)
    for name, row in data['items'].items():
        tree = row.get('worktree')
        if row.get('pr') and (
                (row.get('branch') and (every or row['branch'] in targets)) or (
                isinstance(tree, str) and tree
                and any(place.is_relative_to((root / tree).resolve()) for place in places))):
            return 1, (f'{name} owns PR {row["pr"]}: its branch takes only the gated push; run '
                       f'bin/wuwei pr act {row["pr"]} --push once every gate passed')
    return None


def _approved(fields, values, cwd):
    """An APPROVE review event in a field or in the JSON --input body (review F6); a body that
    cannot be read (stdin, a missing file) counts as one, so the floor holds."""
    import json
    if any(field.upper() == 'EVENT=APPROVE' for field in fields):
        return True
    for name in values.get('--input', []):
        try:
            if name in ('', '-'):
                return True
            body = json.loads((cwd / name).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return True
        if isinstance(body, dict) and str(body.get('event', '')).upper() == 'APPROVE':
            return True
    return False


def _api_edge(args, cwd, root, config):
    """The edge an API write reaches, decided before the body scan (review F1)."""
    from urllib.parse import unquote, urlsplit
    from wuwei.security import gh_outbound
    words, values = _scan(args, GH_VALUED)
    operands = [word for word in words if not word.startswith('-')]
    if not operands:
        return 0, ''
    endpoint = operands[0]
    endpoint = urlsplit(endpoint).path if '://' in endpoint else endpoint.split('?', 1)[0].split('#', 1)[0]
    endpoint = re.sub(r'^api/v3/', '', posixpath.normpath(unquote(endpoint)).strip('/'), flags=re.I)
    fields = [value for key in ('-f', '-F', '--field', '--raw-field') for value in values.get(key, [])]
    method = (_last(values, '-X', '--method') or ('POST' if fields or '--input' in values else 'GET')).upper()
    writes = method not in ('GET', 'HEAD', 'OPTIONS')
    if writes:
        match = re.fullmatch(r'repos/([^/]+/[^/]+)/(?:pulls/(\d+)/merge|merges)', endpoint, re.I)
        if match:
            return _merge(_pr(match[2], match[1]))
        if (re.fullmatch(r'repos/[^/]+/[^/]+/(?:branches/.+/protection(?:/.*)?|rulesets(?:/.*)?)', endpoint, re.I)
                or re.fullmatch(r'orgs/[^/]+/rulesets(?:/.*)?', endpoint, re.I)):
            return 1, ("branch protection changes are refused; the protected base branch is the owner's; "
                       'merge through bin/wuwei merge <owner/repo>#<pr>')
        match = re.fullmatch(r'repos/([^/]+/[^/]+)/pulls/(\d+)/reviews(?:/.*)?', endpoint, re.I)
        if match and _approved(fields, values, cwd):
            return _approve(_pr(match[2], match[1]))
        match = re.fullmatch(r'repos/[^/]+/[^/]+/git/refs/heads/(.+)', endpoint, re.I)
        if match and match[1] in {repo['default_branch'] for repo in config['repos']}:
            return _default(match[1], cwd, root)
    return gh_outbound(args, cwd, root, api=True, text_write=writes)


def _gh_edge(argv, cwd, root, config):
    """The pr edges first, then the body scan of a text write (review F1)."""
    from wuwei.security import gh_outbound
    repo, args = _gh(argv[1:])
    family, verb = (args + ['', ''])[:2]
    if family == 'api':
        return _api_edge(args[1:], cwd, root, config)
    text_write = (family == 'pr' and verb in ('comment', 'create', 'edit', 'review', 'merge')
                  or family == 'issue' and verb in ('comment', 'create', 'edit')
                  or family == 'release' and verb in ('create', 'edit'))
    if family != 'pr':
        return gh_outbound(argv, cwd, root, text_write=text_write)
    words, values = _scan(args[2:], GH_VALUED)
    operands = [word for word in words if not word.startswith('-')]
    pr = _pr(operands[0] if operands else None, repo)
    if verb == 'merge':
        return _merge(pr, admin=any(word == '--admin' or word.startswith('--admin=') for word in words))
    if verb == 'review' and any(word == '--approve' or word.startswith('--approve=')
                                or re.fullmatch(r'-[a-zA-Z]*a[a-zA-Z]*', word) for word in words):
        return _approve(pr)
    code, reason = gh_outbound(argv, cwd, root, text_write=text_write)
    if code or verb != 'create':
        return code, reason
    from wuwei import merge, state
    head = _last(values, '-H', '--head')
    linked = (_recorded(root, config, repo=repo, branch=head) if repo and head
              else _recorded(root, config, path=cwd.resolve()))
    if not linked or state.read_state(root)['items'][linked[0]].get('pr'):
        return 0, ''
    names = [repo] if repo else merge.configured(root, config, linked[1])
    named = names[0] if len(names) == 1 else '<owner/repo>'
    # #783: pr raise links the PR to its item; a PR from gh pr create stays unlinked.
    return 1, (f'{RAISE}{linked[0]} is a WUWEI item: raise its PR with bin/wuwei pr raise {named} '
               f'--base <branch> --title <title> --body-file <file> --item {linked[0]}. It links '
               f'the PR to {linked[0]}; gh pr create does not')


def check_bash(payload):
    """Merge, approve, admin, branch protection, force push, the default branch, a bare
    gh pr create for a recorded item, and the gh body scan (records floor)."""
    try:
        from wuwei import workspace
        root = workspace.guard_scope(payload)
        raw = payload['tool_input']['command']
        if root is None or not _named(raw, ('git', 'gh')):
            return 0, ''
        try:
            found = segments(raw, _cwd(payload))
        except ValueError:
            return 2, UNPARSED
        config = workspace.load_config(root)
        exported = {}  # K2: an exported GIT_DIR or GIT_WORK_TREE reaches the later git push
        for argv, env, cwd in found:
            program = PurePosixPath(argv[0]).name
            if program == 'export':
                exported.update(word.split('=', 1) for word in argv[1:] if '=' in word)
            result = (_git_edge(argv[1:], cwd, root, config, {**exported, **env}) if program == 'git'
                      else _gh_edge(argv, cwd, root, config) if program == 'gh' else (0, ''))
            if result[0]:
                return result
        return 0, ''
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return 2, f'edges guard could not run: {exc}'


def deny(rule, repo=None):
    """An owner-only rule and the repository the command names; check_deploy asks its card."""
    return 1, (rule, repo)


def environment(branch, config):
    branch = branch.removeprefix('refs/heads/')
    return any(fnmatchcase(branch, pattern) for pattern in config['environments'])


def workflow(target, config, repo=None):
    if not target:
        return 0, ''
    marked = config['deploy']['workflows']
    if any(target == item or PurePosixPath(target).name == PurePosixPath(item).name
           for item in marked):
        return deny('deploy.workflows', repo)
    # #478: a name or ID that may be a marked workflow is a deploy the owner decides.
    if marked and (not target.endswith(('.yml', '.yaml')) or
                   any(not item.endswith(('.yml', '.yaml')) for item in marked)):
        return deny('deploy.workflows', repo)
    return 0, ''


def git(args, config):
    verb, rest = _git(args)
    if verb != 'push':
        return 0, ''
    if any(arg in ('--tags', '--follow-tags', '--mirror', 'tag') or 'refs/tags/' in arg for arg in rest):
        return deny('tag push')
    for target in _pushed(rest):
        if environment(target, config):
            return deny('environment branch push')
        if re.fullmatch(r'v?\d+\.\d+.*', target):
            return deny('tag push')
    return 0, ''


def api(args, config):
    from urllib.parse import unquote, urlsplit
    words, options = _scan(args, GH_VALUED)
    targets = [word for word in words if not word.startswith('-')]
    if len(targets) != 1:
        return 0, ''
    parts = unquote(urlsplit(targets[0]).path).strip('/').split('/')
    repo = '/'.join(parts[1:3]) if parts[0] == 'repos' and len(parts) > 2 else None
    if 'deployments' in parts or 'environments' in parts:
        return deny('deployment/environment API', repo)
    method = _last(options, '-X', '--method')
    writes = method.upper() not in ('GET', 'HEAD') if method else any(
        key in options for key in ('-f', '-F', '--field', '--raw-field', '--input'))
    if 'dispatches' in parts and 'workflows' in parts:
        return workflow(parts[parts.index('workflows') + 1], config, repo)
    if ('rerun' in parts or 'rerun-failed-jobs' in parts) and config['deploy']['workflows']:
        return deny('deploy.workflows', repo)
    if writes and 'releases' in parts:
        return deny('release API', repo)
    if writes and ('refs' in parts or 'tags' in parts):
        return deny('tag or branch ref API', repo)
    if writes and 'merges' in parts and any(
            value.startswith('base=') and environment(value[5:], config)
            for key in ('-f', '-F', '--field', '--raw-field') for value in options.get(key, [])):
        return deny('environment branch merge API', repo)
    return 0, ''


def gh(args, config):
    repo, args = _gh(args)
    if args[:2] == ['release', 'create']:
        return deny('release create', repo)
    if args[:1] == ['api']:
        return api(args[1:], config)
    if args[:2] == ['run', 'rerun']:
        return deny('deploy.workflows', repo) if config['deploy']['workflows'] else (0, '')
    if args[:2] in (['workflow', 'run'], ['workflow', 'rerun']):
        words, _ = _scan(args[2:], ('-r', '--ref', '-f', '-F', '--field', '--raw-field'))
        targets = [word for word in words if not word.startswith('-')]
        return workflow(targets[0] if len(targets) == 1 else '', config, repo)
    return 0, ''


def command_result(argv, config):
    """(0, '') or (1, (rule, repo)) for an owner-only command (design 4.7)."""
    program, *args = argv
    program = PurePosixPath(program).name
    text = ' '.join([program, *args])
    for pattern in config['deploy']['deny']:
        if fnmatchcase(text, pattern) or text.startswith(pattern + ' '):
            return deny(f'deploy.deny: {pattern}')
    # Matching any argv verb is conservative and also catches global options.
    for verb in VERBS.get(program, ()):
        if verb in args:
            return deny(f'{program} {verb}')
    if program == 'kubectl' and any(args[i:i + 2] == ['set', 'image']
                                   for i in range(len(args) - 1)):
        return deny('kubectl set image')
    if program in ('docker', 'podman') and 'build' in args:
        for index, arg in enumerate(args):
            if arg == '--push' or arg.startswith('--push='):
                return deny(f'{program} build --push')
            output = (args[index + 1] if arg in ('--output', '-o') and index + 1 < len(args)
                      else arg.removeprefix('--output=') if arg.startswith('--output=')
                      else arg[2:].lstrip('=') if arg.startswith('-o') else '')
            if 'type=registry' in output.split(','):
                return deny(f'{program} build registry output')
    if program in ('vercel', 'vc') and (not args or args[0] not in (
            'ls', 'list', 'inspect', 'logs', 'whoami', 'help', '--help', '--version')):
        return deny(f'{program} deployment')
    if program in ('gcloud', 'aws', 'az') and CLOUD_VERBS.intersection(args):
        return deny(f'{program} deployment')
    if program == 'git':
        return git(args, config)
    if program == 'gh':
        return gh(args, config)
    return 0, ''


def check_deploy(payload):
    """Design 4.7 by argv; the owner's Yes on the exact command's Owner step card runs it (#816)."""
    try:
        from wuwei import workspace
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
        raw = payload['tool_input']['command']
        try:
            config = workspace.load_config(root)
        except (ValueError, OSError):
            if not _named(raw, PROGRAMS):
                return 0, ''
            raise
        if not _named(raw, (*PROGRAMS, *(pattern.split()[0] for pattern in config['deploy']['deny']))):
            return 0, ''
        try:
            found = segments(raw, _cwd(payload))
        except ValueError:
            return 2, UNPARSED
        for argv, _, _ in found:
            code, rule = command_result(argv, config)
            if code:  # #816: the owner's Yes on this exact call's Owner step card
                from wuwei import sessions  # off the hook path until a deploy is refused
                from wuwei.commands import hook
                text = ' '.join(hook.redacted_target(payload, root).split())
                if reason := sessions.needs_owner(root, text, f'Run it from the session: {rule[0]}, '
                                                  'owner-only; it cannot be undone.'):
                    return 1, f'publish: {reason}'
        return 0, ''
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        return 2, f'deploy guard could not run: {exc}'


def check_send(payload):
    """#838: an MCP write is local, allowed (exactly on outward.allow) or refused; the canary
    floor stays on every send. The MCP resolution it shares with the lint lives in outward."""
    from wuwei.guards.outward import _check
    return _check(payload, send=True)


GUARDS = [Guard('PreToolUse', 'Bash', check_bash), Guard('PreToolUse', 'Bash', check_deploy),
          Guard('PreToolUse', None, check_send)]
