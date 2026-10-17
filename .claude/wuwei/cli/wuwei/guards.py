"""The few doors WUWEI holds. Everything else passes; the harness's own permission rules decide
who may call which tool. A door that cannot read its evidence stays shut; a guard that cannot
read a command lets it through unless it names a door program (the audit still sees it)."""

from fnmatch import fnmatchcase
import json
from os.path import join, normpath
from pathlib import Path
import re
import shlex
import subprocess
from urllib.parse import unquote

from wuwei import evidence, gh, ws

SHELLS = {'sh', 'bash', 'zsh', 'dash'}
WRAPPERS = {'env', 'command', 'exec', 'nohup', 'time', 'sudo', 'xargs', 'nice', 'timeout', 'stdbuf'}
CONTROL, REDIRECTS = {'&&', '||', ';', '|', '&', ';;', '(', ')', '|&'}, {'>', '>>', '>|', '&>', '&>>', '<', '<>', '>&', '<&', '<<', '<<<'}
OPS = r'&>>|<<<|&&|\|\||>>|<<|>&|<&|<>|>\||&>|\|&|[();<>|&]'  # sh's operators in a run of punctuation, longest first (;; splits the same)
INFRA = {'terraform': {'apply', 'destroy', 'import'}, 'tofu': {'apply', 'destroy', 'import'},
         'pulumi': {'up', 'destroy'}, 'kubectl': {'apply', 'delete', 'create', 'replace', 'patch', 'scale'},
         'helm': {'install', 'upgrade', 'uninstall', 'rollback'}}
NETWORK = {'gh', 'curl', 'wget', 'nc', 'ssh', 'scp', 'http', 'https'}
WRITERS, FIND = {'tee', 'truncate', 'rm', 'mv', 'cp', 'dd', 'chmod', 'ln', 'shred'}, {'-delete', '-exec', '-execdir', '-fprint', '-fprintf', '-fls'}
READ = {'git', 'gh', 'wuwei', 'sed'} | SHELLS | set(INFRA) | NETWORK | WRITERS  # the programs a door reads
UNREAD = ([], ['<an unreadable sh -c body>'])  # the segment an unreadable body leaves for the raw-text rule
DOORS = {'edit': ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'), 'merge': ('merge_pull_request', 'enable_pr_auto_merge'),
         'create': ('create_pull_request',), 'push': ('push_files', 'create_or_update_file', 'delete_file'),
         'ready': ('update_pull_request', 'request_copilot_review')}  # hook.door() reads it
DOOR_WORDS = ((r'\bgit\b', r'\bpush\b'), (r'\bgh\b', r'\b(pr|api|repo)\b'), (r'\bwuwei[\'"]?(\s|\\\n)+[\'"]?hook\b',), (r'\.wuwei[/.]*(/ledger|(?![\w./-]))',))
SECRETS = re.compile(r'gh[pousr]_[A-Za-z0-9]{36}|github_pat_\w{22,}|sk-ant-[\w-]{20,}|sk-[A-Za-z0-9]{32,}'
                     r'|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AIza[\w-]{35}')
LEDGER, CACHE = ('ledger', 'ledger.jsonl'), ('ledger', 'ledger.jsonl', 'cache')  # what lies below .wuwei that a session never writes
WRITE, REPO = ('POST', 'PUT', 'PATCH', 'DELETE'), r'repos/([^/]+/[^/]+)'
API = ((REPO + '/pulls', ('POST',), 'create'), (REPO + r'/pulls/[^/0-9]*([0-9]+)[^/]*/(merge|ccr/auto_merge)', ('PUT',), 'merge'),
       (REPO + r'/pulls/[^/0-9]*([0-9]+)[^/]*/(ccr/ready_for_review|requested_reviewers)', ('POST',), 'ready'),  # 7abc, %207: PR 7
       (REPO + '/(merges|git/refs/.+|contents/.+)', WRITE, 'push'), (REPO, ('DELETE',), 'delete'), (r'(.*/)?\.\.(/.*)?', WRITE, 'dots'),
       (r'.*(/branches/[^/]+/protection|/rulesets|/statuses/|/collaborators|/hooks|/keys|/actions/secrets|/environments).*',
        WRITE, 'rules'))  # gh api routes to a door, matched on the whole endpoint
API_VALUED = set('XfFHqtp') | {'method', 'raw-field', 'field', 'input', 'header', 'jq', 'template', 'preview', 'hostname', 'cache'}
MUTATIONS = re.compile(r'\w*(mergePullRequest|enablePullRequestAutoMerge|createPullRequest|updateRef|deleteRef|createCommitOnBranch'
                       r'|mergeBranch|enqueuePullRequest|BranchProtectionRule|RepositoryRuleset|markPullRequestReadyForReview|requestReviews)\w*')
TRUE, FALSE = ('1', 't', 'T', 'true', 'TRUE', 'True'), ('0', 'f', 'F', 'false', 'FALSE', 'False')  # pflag's; any other makes gh exit
VALUED = set('aBbFHlmpTtR') | {'assignee', 'base', 'body', 'body-file', 'head', 'label', 'milestone', 'project', 'template', 'title', 'repo'}
PR_VALUED = {'A', 'r', 'reviewer', 'recover', 'subject', 'match-head-commit', 'author-email', *(f'{verb}-{what}' for verb in (
    'add', 'remove') for what in ('reviewer', 'assignee', 'label', 'project'))}  # gh pr create, edit and merge add these
UNVALUED = set('defw') | {'draft', 'editor', 'fill', 'web', 'dry-run', 'fill-first', 'fill-verbose', 'no-maintainer-edit'}  # gh pr create's
OPEN = 'opens ready for review only once its gates pass at its head: open a draft now (gh pr create --draft, gh api -F draft=true)'
READY = 'leaves draft or asks reviewers only once its gates pass at the PR head (gates run before review)'
PUSHED = 'refused: every change reaches it through a pull request with its evidence. Push a branch and open a PR.'
OWNER_CLASSES = ('one-way:', 'scope:', 'goal:', 'trust:', 'infra:', 'owner review:', 'exception:', 'plan:', 'breaking:')
NOT_OWNERS = ('''question sent back: the process answers it, not the owner.
Take your recommendation, record it under Assumptions in the spec or PR body (what you assumed, why, what would overturn it) and go on. Ask the owner only for a
decision of one of these classes, named at the start of the question: ''' + ', '.join(OWNER_CLASSES)
              + '. The plan is your mandate: never ask whether to continue planned work.')
LEDGER_DENIED = ("the ledger is written only by WUWEI's hooks; it is the audit record. The cache (.wuwei/cache) is written only by WUWEI: "
                 'its entries feed gate inputs (ci-, review-, default-branch). Removing a cache file passes; the next read fetches it.')
PR_STANDARD = ws.PLUGIN / 'charters' / '_pr.md'


def records(path, below=LEDGER, cap=512):  # .wuwei, or what lies below it (None: anything), as sh expands the path (cap: words left)
    if m := re.search(r'\{(?:([^{},]*,[^{}]*)|(\w)\.\.(\w)(\.\.-?[0-9]+)?)\}', path):  # brace expansion, innermost first: {a,b}, {z..a..2}
        alts = m[1].split(',') if m[1] is not None else [*map(chr, range(lo := ord(min(m[2], m[3])), min(ord(max(m[2], m[3])), lo + cap) + 1))]
        return len(alts) > cap or any(records(path[:m.start()] + a + path[m.end():], below, cap // max(len(alts), 2)) for a in alts)
    path = re.sub(r'(?<![^/])([^/[]*)\[(?=[^/]*?\[[:=.])[^/]*\]', r'\1*', path.replace('[^', '[!'))  # [^x] is [!x]; [[:a:]x] [[=a=]] [[.a.]]: *
    parts = [p for p in re.split(r'[/=]', normpath(path)) if p not in ('', '.')]  # //, /./, .. and of= too
    return any(p[:1] == '.' and fnmatchcase('.wuwei', p) and (below is None or i + 1 == len(parts) or any(  # * ? [..] skip a leading dot
        fnmatchcase(name, parts[i + 1]) for name in below)) for i, p in enumerate(parts))


def deny(reason):
    return {'decision': 'deny', 'reason': reason}


def _git(cwd, *args):
    try:
        return subprocess.run(['git', '-C', cwd, *args], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def origin(cwd):
    """owner/repo of the origin remote at cwd, or ''."""
    match = re.search(r'github\.com[:/]([\w.-]+/[\w.-]+?)(\.git)?$', _git(cwd, 'remote', 'get-url', 'origin'))
    return match[1] if match else ''


def current_branch(cwd):
    return _git(cwd, 'rev-parse', '--abbrev-ref', 'HEAD')


def segments(command):
    """Each simple command as (argv, redirect targets), with sh -c bodies and wrappers unwrapped."""
    try:
        lexer = shlex.shlex(re.sub(r"'[^']*'|\"(\\[\s\S]|[^\"\\])*\"|\\[\s\S]|\n|(?<![^\s;&|()<>])(?<![<>]&)([0-9]+|\{[A-Za-z_]\w*\})(?=[<>])",
            lambda m: {'\n': ' ; ', '\\\n': ''}.get(m[0], '' if m[0][0] in '{0123456789' else m[0]), command), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True  # sh's lines: an unquoted newline ends a command; the 2 of 2>&1 and {fd} of {fd}>x are a redirect, not a word
        lexer.commenters = ''  # '#' inside a word is literal in sh: owner/repo#42 must not hide the rest (#1038)
        tokens, current = [t for word in lexer for t in (re.findall(OPS, word) if re.fullmatch(r'[();<>|&]+', word) else [word])] + [';'], []
        dollar = any(m[0][0] == '$' for m in re.finditer(r'\$[\'"]|\'[^\']*\'|"(\\[\s\S]|[^"\\])*"|\\[\s\S]', command))
        # '' keeps the last pair: zip stops at its shortest list, so without it `x >` reads as clean (8,400 of 82,944 probes change)
        glued = any(a in REDIRECTS and (b in REDIRECTS and c != '(' or b in CONTROL - {'('})
                    for a, b, c in zip(tokens, tokens[1:], tokens[2:] + ['']))
        out = [UNREAD] if dollar or glued else []
        for token in tokens:  # $'..', $".." or a redirect with no word after it (<(x) is one) is unread; its segments are still read
            if token in CONTROL:  # <( ;> &&( |& ); split into the operators sh reads
                if current:
                    out.extend(_unwrap(current))
                current = []
            else:
                current.append(token)
        return out
    except ValueError:
        return None


def _unwrap(tokens):
    argv, targets, i = [], [], 0
    while i < len(tokens):
        if tokens[i] in REDIRECTS and i + 1 < len(tokens):
            if not re.fullmatch(r'<[<&]*', tokens[i]):  # an input redirect's word is read, never written
                targets.append(tokens[i + 1])
            i += 1
        else:
            argv.append(tokens[i])
        i += 1
    while argv and re.fullmatch(r'[A-Za-z_]\w*=.*|do|then|else|elif|if|while|until|!|\{', argv[0]):  # a body opens
        argv = argv[1:]
    if argv and Path(argv[0]).name in WRAPPERS:  # a wrapper's options hide nothing: the command is the first program read
        argv = next((argv[i:] for i, a in enumerate(argv) if not a.startswith('-') and '=' not in a  # not an option or VAR=
                     and (Path(a).name in READ or Path(a).name.startswith('python'))), argv)
    body = next((i for i, a in enumerate(argv) if i and not a.startswith('-')), 0)  # bash -c, -lc, -e -c
    if body and Path(argv[0]).name in SHELLS and any(re.fullmatch(r'-\w*c\w*', a) for a in argv[1:body]):
        return (n if (n := segments(argv[body])) is not None else [UNREAD]) + ([([], targets)] if targets else [])
    return [(argv, targets)] + ([UNREAD] if argv and Path(argv[0]).name in SHELLS else [])  # its commands come from stdin or a file


def _default(root, repo):
    try:
        return {evidence._cached(root, 'default-' + repo.replace('/', '__'), lambda: gh.default_branch(repo))} if repo else {'main', 'master'}
    except gh.GhError:
        return {'main', 'master'}


def git_push(root, args, cwd):
    if any(a.startswith('--force') or a == '--mirror' or re.fullmatch(r'-[a-z]*f[a-z]*', a) for a in args):
        return deny('force push refused: history on a shared branch does not come back. Push a new commit instead.')
    positional = [a for a in args if not a.startswith('-')]
    deleting = any(a in ('--delete', '-d') for a in args)
    if any(ref.startswith('+') for ref in positional[1:]):
        return deny('force push refused (a + refspec): push a new commit instead.')
    targets = []
    for ref in positional[1:] or ['HEAD']:
        destination = ref.split(':', 1)[1] if ':' in ref else ref
        if destination in ('', 'HEAD'):
            destination = current_branch(cwd)
        targets.append(destination.removeprefix('refs/heads/'))
        deleting = deleting or ref.startswith(':')
    protected = _default(root, origin(cwd))
    if hit := [t for t in targets if t in protected]:
        return deny(f'{"deleting" if deleting else "pushing to"} the default branch {hit[0]} ' + PUSHED)
    return None


def _flags(args, valued):  # (name, value) per flag as pflag reads it (a value flag takes =x, the cluster's rest or the next word)
    out, words = [], iter(args)
    for word in words:
        if word == '--' or word[:1] != '-' or word == '-':
            out += [('', w) for w in (words if word == '--' else [word])]
        elif long := re.fullmatch(r'--([^=]+)(?:=(.*))?', word, re.S):
            out.append((long[1], long[2] if long[2] is not None or long[1] not in valued else next(words, None)))
        elif rest := word[1:]:
            while rest:  # a short cluster: -fd, -dt x, -d=t, -Rx/y
                name, rest = rest[0], rest[1:]
                out.append((name, rest[1:] if rest[:1] == '=' else (rest or next(words, None)) if name in valued else None))
                rest = '' if rest[:1] == '=' or name in valued else rest
    return out


def _repo_number(args, cwd, valued=VALUED | PR_VALUED):  # the last -R (or the URL's repository) and the first positional
    flags = _flags(args, valued)
    url = re.fullmatch(r'https://github\.com/([\w.-]+/[\w.-]+)/pull/([0-9]+)/?', word := next((v for n, v in flags if not n), ''))
    repo = url[1] if url else ([v for n, v in flags if n in ('R', 'repo') and v] or [''])[-1]
    return repo or origin(cwd), int(url[2]) if url else int(word) if word.isascii() and word.isdigit() else None


def _draft(args):
    """gh pr create's --draft as pflag reads it (the last wins); a reviewer, --recover, a bad flag or value or a positional: no."""
    flags = _flags(args, VALUED)
    return not any(n not in VALUED | UNVALUED or n in VALUED and v is None or n in ('d', 'draft') and v not in (None, *TRUE, *FALSE)
                   for n, v in flags) and ([v in (None, *TRUE) for n, v in flags if n in ('d', 'draft')] or [False])[-1]


def _read(cwd, path):
    return Path(cwd, path).read_text(encoding='utf-8') if path != '-' and Path(cwd, path).is_file() else ''  # gh reads - as stdin


def _api(args, cwd, alone=True):
    """gh api's method, fields (-XPUT, --method=put, -fk=v, -F k=@file) and endpoint (//, %xx and . read as GitHub does)."""
    flags = _flags(args, API_VALUED)  # an empty attached value (-X=, --method=) is a value; a flag with none takes the next word
    opts, rest = [('-' * min(len(n), 2) + n, v or '') for n, v in flags if n], [v for n, v in flags if not n]
    pairs = [(f, *kv.split('=', 1)) for f, kv in opts if f in ('-f', '--raw-field', '-F', '--field') and '=' in kv]
    fields = {k: _read(cwd, v[1:]) if f in ('-F', '--field') and v.startswith('@') else v for f, k, v in pairs}
    data = ''.join(_read(cwd, v) for f, v in opts if f == '--input')
    fields |= dict(re.findall(r'"(head|base|body)"\s*:\s*"((?:\\.|[^"\\])*)"', data))  # the --input file's JSON
    fields |= {'query': fields.get('query', '') + data.encode().decode('unicode_escape', 'replace')} if alone and data else {}  # all of it, \u read
    unread = any(not (alone and _read(cwd, p)) for f, v in opts if (p := v if f == '--input' else v[7:] if f in ('-F', '--field')
                                                                     and v[:7] == 'query=@' else None) is not None)  # stdin, missing, cd
    draft = (alone and (json.loads(data) if data.lstrip()[:1] == '{' else {}).get('draft') is True if '--input' in dict(opts)  # gh reads
             else ([f in ('-F', '--field') and v == 'true' for f, k, v in pairs if k == 'draft'] or [False])[-1])  # the file in its own cwd
    method = ([v.upper() for f, v in opts if f in ('-X', '--method')] or ['POST' if fields or '--input' in dict(opts) else 'GET'])[-1]
    endpoint = '/'.join(p for p in unquote(re.sub(r'(?i)^[a-z][\w+.-]*://[^/]*|[?#].*$', '', rest[0] if rest else '')).split('/') if p not in ('', '.'))
    owner, name = ((origin(cwd) if '{' in endpoint else '') or '{owner}/{repo}').split('/')
    return method, endpoint.replace('{owner}', owner).replace('{repo}', name), fields, draft, unread


def gh_command(root, args, cwd, session, command=''):
    if args[:2] == ['pr', 'merge']:
        valued = (VALUED | PR_VALUED) - {'m', 'r'}  # merge's -m and -r are bools; the last --admin or --auto pflag reads wins
        on = lambda name: ([v in (None, *TRUE) for n, v in _flags(args[2:], valued) if n == name] or [False])[-1]  # noqa: E731
        if on('admin'):
            return deny('--admin bypasses branch protection; WUWEI never merges around the repository rules.')
        return merge_door(root, *_repo_number(args[2:], cwd, valued), auto=on('auto'))
    if args[:2] == ['repo', 'delete']:
        return deny('deleting a repository is the owner\'s act, never an agent\'s.')
    flag = lambda *names: next((args[i + 1] for i, a in enumerate(args[:-1]) if a in names), '')  # noqa: E731
    opening = args[:2] in (['pr', 'create'], ['pr', 'new']) and (_repo_number(args, cwd)[0], flag('--head', '-H'), flag(
        '--base', '-B'), _read(cwd, flag('--body-file', '-F')), _draft(args[2:]))
    undo = ([a[6:] for a in args if a == '--undo' or a.startswith('--undo=')] or ['no'])[-1] in ('', *('=' + t for t in TRUE))
    if args[:2] == ['pr', 'ready'] and not undo or args[:2] == ['pr', 'edit'] and any(a.startswith('--add-reviewer') for a in args):
        return ready_door(root, *_repo_number(args[2:], cwd))
    if args[:1] == ['api'] and len(args) > 1:
        method, endpoint, fields, draft, unread = _api(args[1:], cwd, (words := shlex.split(command))[:1] == ['gh'] and all(
            re.fullmatch(r'[\w./=@:-]+', w) for w in words))  # an --input or -F query=@ file is the one gh reads: alone, unwrapped, plain words
        if endpoint.lower() == 'graphql' and unread:
            return deny('a gh api graphql query WUWEI cannot read (stdin, a missing file, a file outside one plain gh call): pass -f query=...')
        if method in WRITE and re.match('(?i)repositories/', endpoint):
            return deny(f'gh api {method} {endpoint}: spell the endpoint repos/<owner>/<repo>/... so WUWEI can read which door it is.')
        if endpoint.lower() == 'graphql' and (named := MUTATIONS.search(fields.get('query', ''))):
            return deny(f'gh api graphql {named[0]} goes around the doors: use gh pr merge, gh pr create --draft, gh pr ready or gh pr '
                        'edit --add-reviewer (in a cloud session gh api -X POST repos/<o>/<r>/pulls[/<n>/ccr/ready_for_review]).')
        door, m = next(((d, m) for pattern, methods, d in API if method in methods and (m := re.fullmatch(pattern, endpoint, re.I))),
                       ('', None))
        if door in ('merge', 'ready'):
            return merge_door(root, m[1], int(m[2]), auto=m[3].lower() != 'merge') if door == 'merge' else ready_door(root, m[1], int(m[2]))
        if door in ('push', 'delete', 'rules', 'dots'):
            return deny({'push': f'gh api {method} {endpoint} writes a branch outside a pull request: like pushing to the '
                                 'default branch it is ' + PUSHED, 'dots': f'gh api {endpoint} has a .. segment: spell the '
                                 'endpoint plainly.', 'delete': 'deleting a repository is the owner\'s act, never '
                         'an agent\'s.'}.get(door, f'gh api {method} {endpoint} changes protection, statuses, merges or access: '
                                                    'the repository rules and the merge door are not changed from an agent session.'))
        opening = door == 'create' and (m[1], fields.get('head', ''), fields.get('base', ''), fields.get('body', ''), draft)
    if opening:
        repo, head, base, body, draft = opening  # a draft opens before its gates (#1050, #1074); the flip to ready waits
        found = None if draft else create_door(root, repo, head or current_branch(cwd), base, command + body)
        if found or once(root, session, 'pr-standard'):
            return found or {'decision': 'note', 'reason': PR_STANDARD.read_text(encoding='utf-8').strip().replace('<version>', ws.version())}
    return None


def create_door(root, repo, branch, base, text, act=OPEN):
    """Gates run on the pushed head before review (#1050): a PR opens ready, or a draft leaves draft, at a gated head."""
    try:
        diff = gh.compare(repo, base or sorted(_default(root, repo))[0], branch)
    except gh.GhError as exc:
        return deny(f'cannot read {branch} on {repo} ({exc}): push the branch; it {act}.')
    pr = {'body': f'WUWEI-Item: {named[1]}' if (named := evidence.ITEM.search(text or '')) else '', 'headRefName': branch}
    item_id, tier, gates, why = evidence.gates_for(root, repo, pr, diff['files'], evidence.item_for(root, pr, repo))
    found = evidence.gate_gaps(root, repo, item_id, gates, (diff.get('commits') or [{}])[-1].get('sha', ''), why, '', tier)
    found += [{'text': 'no plan item is named, so no gate verdict can count: end the PR body with the WUWEI footer or a '
               'WUWEI-Item line, passed by --body or a --body-file path WUWEI can read (a literal path, not $VAR)'}] if found and not item_id else []
    return deny(f'{repo} {branch} {act}:\n' + '\n'.join('- ' + g['text'] for g in found)) if found else None


def ready_door(root, repo, number):
    """The flip to ready and a reviewer request on a draft wait for the gates at the PR head: the create door on its head."""
    if not repo or number is None:
        return deny(f'name the PR by number or URL (and --repo when outside its checkout): a draft {READY}.')
    try:
        pr = gh.pr(repo, number)
    except gh.GhError as exc:
        return deny(f'cannot read {repo}#{number} ({exc}): a draft {READY}.')
    return create_door(root, repo, pr['headRefName'], pr['baseRefName'], pr['body'], READY) if pr['isDraft'] else None


def merge_door(root, repo, number, auto=False):
    """Every merge route (gh pr merge, gh api PUT .../merge, a GitHub MCP merge tool) meets the same
    evidence: only safety gaps hold it; the process fit it flows past is recorded."""
    if not repo or number is None:
        return deny('name the PR by number or URL (and --repo when outside its checkout) so WUWEI can read '
                    'its evidence before the merge.')
    found = evidence.gaps(root, repo, number)
    gaps = [g for g in evidence.blocking(found) if not (auto and g['text'] == 'CI running')]  # auto-merge waits for running CI, not for none (#1085)
    if gaps:
        return deny(f'{repo}#{number} is not ready to merge:\n' + '\n'.join('- ' + g['text'] for g in gaps))
    ws.record(root, 'merge.checked', {'pr': f'{repo}#{number}', 'auto': auto,
                                      'process': [g['text'] for g in found if g['kind'] == 'process']})
    return None


def once(root, session, topic):
    seen = ws.cache_get(root, f'notes-{session}', 7 * 86400) or []
    if topic in seen:
        return False
    ws.cache_put(root, f'notes-{session}', seen + [topic])
    return True


def leak(root, text):
    canary_file = Path(root) / ws.DIR / 'canary'
    canary = canary_file.read_text(encoding='utf-8').strip() if canary_file.is_file() else ''
    if canary and canary in text:
        return deny('the workspace canary is in this outward call: workspace content would leave the machine.')
    if found := SECRETS.search(text):
        return deny(f'a secret ({found[0][:6]}...) is in this outward call; remove it before sending.')
    return None


def bash(root, command, cwd, session):
    parts = segments(command)
    if (parts is None or UNREAD in parts or re.search('[\r\n]', command)) and any(all(re.search(w, command) for w in d) for d in DOOR_WORDS):
        return deny('a multi-line or unreadable command naming a door program (git push, gh pr/api/repo, wuwei hook, '
                    '.wuwei or .wuwei/ledger) is refused: run the door command in its own one-line Bash call, and pass long text '
                    'by --body-file, -F or a file written with Write.')
    inside = records(cwd, None)  # after cd .wuwei (or in it), a relative path reaches the records unnamed
    for argv, targets in parts or ():
        program, words = Path(argv[0]).name if argv else '', argv[1:] + re.findall(r'[^\s\'"(),;]+', ' '.join(argv[1:]))  # and python -c's paths
        writer = program in WRITERS or program == 'sed' and '-i' in argv or program.startswith('python') or program == 'find' and FIND & {*argv}
        if any(records(t, CACHE) for t in targets) or writer and any(records(a, LEDGER if program == 'rm' else CACHE) for a in words) or (
                inside and (writer or any(not re.fullmatch(r'[0-9]*-?|/dev/\w+', t) for t in targets))):
            return deny(LEDGER_DENIED)
        inside = inside or program in ('cd', 'pushd') and any(records(a, None) for a in argv[1:])
        if program == 'wuwei' and argv[1:2] == ['hook']:
            return deny('wuwei hook is called by the harness, never by a session: a hand-made call would forge the record.')
        if program in NETWORK and (found := leak(root, ' '.join(argv))):
            return found
        if program in ('git', 'git-clean'):
            rest, i, here = ['clean'] * (program == 'git-clean') + argv[1:], 0, cwd
            while i < len(rest) and rest[i].startswith('-'):
                here = rest[i + 1] if rest[i] == '-C' and i + 1 < len(rest) else here
                i += 2 if rest[i] in ('-C', '-c', '--git-dir', '--work-tree') else 1
            flags, dirs, plain = _flags(rest[i + 1:], ex := {'exclude'[:j] for j in range(1, 8)}), rest[1:i:2], lambda w: re.fullmatch(r'[\w./-]+', w or '')
            if 'clean' in str(rest) and ((other := {*rest[:i:2]} - {'-C'}) or rest[i:i + 1] == ['clean']) and ('GIT_' in command or other or any(  # only -C
                    n in ('x', 'X') or n in ex and not plain(v) for n, v in flags) and (inside or not (paths := [v for n, v in flags if not n]) or any(
                    not plain(w) for w in dirs + paths) or any(re.match(r'\.{0,2}(/|$)', normpath(p := join(*dirs, w))) or records(p, None) for w in paths))):
                return deny(LEDGER_DENIED)
            if rest[i:i + 1] == ['push'] and (found := git_push(root, rest[i + 1:], here)):
                return found
        elif program == 'gh' and (found := gh_command(root, argv[1:], cwd, session, command)):  # a clean gh falls to INFRA: no gh key
            return found
        elif program in INFRA and INFRA[program] & set(argv[1:]):
            return {'decision': 'ask', 'reason': f'{program} {" ".join(a for a in argv[1:] if a in INFRA[program])} '
                    'changes infrastructure: a one-way door the owner decides.'}
    return None


def pre_tool(root, payload):
    tool = payload.get('tool_name', '')
    data = payload.get('tool_input') or {}
    cwd = payload.get('cwd') or '.'
    if tool in DOORS['edit']:
        paths = [str(data.get('file_path') or data.get('notebook_path') or ''), *map(str, data.get('file_paths') or ())]
        return deny(LEDGER_DENIED) if any(records(path, CACHE) for path in paths) else None
    if tool == 'AskUserQuestion':
        questions = [str(q.get('question', '')) for q in data.get('questions') or () if isinstance(q, dict)]
        process = [q for q in questions if q.strip().lower().startswith('exception:') and re.search(
            r"specs/|openspec/|no spec in the diff|template's sections|changed lines|open [0-9]+ days", q)]
        if process:
            return deny('process gaps never block a merge and are nobody\'s decision: merge when the safety '
                        'evidence is complete; the merge records the process fit for the retro.')
        unparsed = [q for q in questions if q.strip().lower().startswith(('exception:', 'owner review:', 'breaking:')) and not
                    re.match(r'\s*(?i:exception:[\s\S]*?|owner review:\s*|breaking:\s*)[\w.-]+/[\w.-]+#[0-9]+ at [0-9a-f]{7,40}\b', q)]
        if unparsed:
            return deny(f'"{unparsed[0][:120]}" will not be recorded as asked (one-way:, scope:, goal:, trust:, infra: '
                        'and plan: take any wording). Use the exact shape: "exception: '
                        'owner/repo#n at <sha7> [and #m at <sha7>]: <the gap as wuwei evidence prints it>. <question>" or '
                        '"owner review: owner/repo#n at <sha7>. <question>" or "breaking: owner/repo#n at <sha7>: '
                        '<what breaks>. Announced at <link>. Proceed?".')
        if not (unclassed := [q for q in questions if not q.strip().lower().startswith(OWNER_CLASSES)]):
            return None
        named = '; '.join(f'"{q[:120]}"' for q in unclassed)
        rest = ' Decide those yourself and resend the classed questions on their own.' if len(unclassed) < len(questions) else ''
        return deny(f'{NOT_OWNERS}\nSent back: {named}.{rest}')
    repo = f'{data.get("owner")}/{data.get("repo")}' if data.get('owner') and data.get('repo') else ''
    number = int(n) if (n := str(data.get('pullNumber', data.get('pull_number')))).isascii() and n.isdigit() else None
    if tool.startswith('mcp__') and tool.endswith(DOORS['push']):
        branch = str(data.get('branch') or '').removeprefix('refs/heads/')
        return leak(root, json.dumps(data)) or (deny(f'pushing to the default branch {branch or "(no branch named)"} '
                                                     + PUSHED) if not branch or branch in _default(root, repo) else None)
    if tool.startswith('mcp__') and tool.endswith(DOORS['merge']):
        return leak(root, json.dumps(data)) or merge_door(root, repo, number, auto=tool.endswith('auto_merge'))
    if tool.startswith('mcp__') and tool.endswith(DOORS['create']) and not (data.get('draft') is True and not data.get('reviewers')):
        return leak(root, json.dumps(data)) or create_door(root, f'{data.get("owner")}/{data.get("repo")}', str(
            data.get('head', '')), str(data.get('base', '')), str(data.get('body', '')))  # a draft opens before its gates
    if tool.startswith('mcp__') and tool.endswith(DOORS['ready']) and (data.get('draft', True) is not True or data.get('reviewers') or 'copilot' in tool):
        return leak(root, json.dumps(data)) or ready_door(root, repo, number)
    if tool.startswith('mcp__'):
        return leak(root, json.dumps(data))
    if tool == 'Bash':
        return bash(root, str(data.get('command', '')), cwd, payload.get('session_id', ''))
    return None
