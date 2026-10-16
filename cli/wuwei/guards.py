"""The few doors WUWEI holds. Everything else passes; the harness's own permission rules decide
who may call which tool. A door that cannot read its evidence stays shut, and so does one that
cannot read a command naming a door program."""

import json
from pathlib import Path
import re
import shlex
import subprocess

from wuwei import evidence, gh, ws

SHELLS = {'sh', 'bash', 'zsh', 'dash'}
WRAPPERS = {'env', 'command', 'exec', 'nohup', 'time', 'sudo', 'xargs', 'nice'}
CONTROL = {'&&', '||', ';', '|', '&', ';;', '(', ')', '`'}
INFRA = {'terraform': {'apply', 'destroy', 'import'}, 'tofu': {'apply', 'destroy', 'import'},
         'pulumi': {'up', 'destroy'}, 'kubectl': {'apply', 'delete', 'create', 'replace', 'patch', 'scale'},
         'helm': {'install', 'upgrade', 'uninstall', 'rollback'}}
NETWORK = {'gh', 'curl', 'wget', 'nc', 'ssh', 'scp', 'http', 'https'}
WRITERS = {'tee', 'truncate', 'rm', 'mv', 'cp', 'dd', 'chmod', 'ln', 'shred'}
SECRETS = re.compile(r'gh[pousr]_[A-Za-z0-9]{36}|github_pat_\w{22,}|sk-ant-[\w-]{20,}|sk-[A-Za-z0-9]{32,}'
                     r'|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AIza[\w-]{35}')
DOORS = re.compile(r'\bgit\b.*\bpush\b|\bgh\b.*\b(pr|api|repo)\b|\bwuwei\b.*\bhook\b|\.wuwei/ledger', re.S)
HEREDOC = re.compile(r'(?<!<)<<(-?)[ \t]*((?:[^\s;&|()<>\'"\\]|\'[^\']*\'|"[^"]*"|\\.)+)')
LEDGER = re.compile(r'(^|/)\.wuwei/ledger(\.jsonl$|/)')
GUARDED_API = re.compile(r'/branches/[^/]+/protection|/rulesets|/statuses/|/collaborators'
                         r'|/hooks|/keys|/actions/secrets|/environments')
OWNER_CLASSES = ('one-way:', 'scope:', 'goal:', 'trust:', 'infra:', 'owner review:', 'exception:', 'plan:', 'breaking:')
NOT_OWNERS = ('''question sent back: the process answers it, not the owner.
Take your recommendation, record it under Assumptions in the spec or PR body (what you assumed, why, what would overturn it) and go on. Ask the owner only for a
decision of one of these classes, named at the start of the question: ''' + ', '.join(OWNER_CLASSES)
              + '. The plan is your mandate: never ask whether to continue planned work.')
PR_STANDARD = Path(__file__).resolve().parents[2] / 'charters' / '_pr.md'


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


def _lines(command):
    """The command as sh reads its lines: a newline outside quotes ends a command, a backslash-newline joins
    two lines, a comment ends; a heredoc body is one quoted word after its <<, or commands once ((, ${ or a joined [ came."""
    out, quote, waiting, i, expansion = [], '', [], 0, False
    while i < len(command):
        c = command[i]
        if quote and (quote == "'" or c != '\\'):
            quote = '' if c == quote else quote
        elif c == '\\':
            c, i = ('' if command[i + 1:i + 2] == '\n' else command[i:i + 2]), i + 1
        elif c in '\'"':
            quote = c
        elif c == '#' and command[i - 1:i] in ('', ' ', '\t', '\n', ';', '&', '|', '(', ')'):
            c, i = '', (command + '\n').index('\n', i) - 1
        elif c == '\n':
            for delimiter, strip, slot, word in waiting:
                body = re.match(r'(.*?)^' + ('\t*' if strip else '') + re.escape(delimiter) + r'$\n?', command[i + 1:], re.S | re.M)
                if not body or word == delimiter and re.search(r'\$\(|`', body[1]):  # unquoted: sh runs $(...)
                    break  # in order: this body and the ones after it are read as commands
                out[slot], i = shlex.quote(body[1].removesuffix('\n')), i + body.end()
            waiting, c = [], ' ; '
        elif not expansion and re.compile(r'\(\(|\$\{|(?<=\S)\[').match(command, i):  # one way: no pairing to get wrong
            expansion = True  # a << after ((, ${ or a joined [ may be a shift, so no later body is dropped
        elif c == '<' and not expansion and (here := HEREDOC.match(command, i)):
            waiting.append((re.sub(r'[\'"\\]', '', here[2]), here[1], len(out) + 1, here[2]))
            c, i = ['<< ', "''"], here.end() - 1
        out += c
        i += 1
    return ''.join(out)


def segments(command):
    """(argv, redirect targets) per simple command; sh -c, shell heredocs and wrappers unwrapped; ValueError if unreadable."""
    lexer = shlex.shlex(_lines(command), posix=True, punctuation_chars='();<>|&`')
    lexer.whitespace_split = True
    lexer.commenters = ''  # '#' inside a word is literal in sh: owner/repo#42 must not hide the rest (#1038)
    out, current = [], []
    for token in list(lexer) + [';']:
        if token not in CONTROL:
            current.append(token)
        elif current:
            out.extend(_unwrap(current))
            current = []
    return out


def _unwrap(tokens):
    argv, targets, bodies, rest = [], [], [], iter(tokens)
    for token in rest:
        if token in ('>', '>>', '>|', '&>', '2>', '1>', '<<'):
            (bodies if token == '<<' else targets).append(next(rest, ''))
        else:
            argv.append(token)
    while argv and (re.fullmatch(r'[A-Za-z_]\w*=.*', argv[0]) or Path(argv[0]).name in WRAPPERS):
        argv = argv[1:]
        while argv and Path(argv[0]).name not in WRAPPERS and argv[0].startswith('-'):
            argv = argv[1:]
    if len(argv) >= 3 and Path(argv[0]).name in SHELLS and argv[1] == '-c':
        return segments(argv[2]) + ([([], targets)] if targets else [])
    return [(argv, targets)] + [s for body in bodies if argv and Path(argv[0]).name in SHELLS for s in segments(body)]


def _default(root, repo):
    if not repo:
        return {'main', 'master'}
    name = 'default-' + repo.replace('/', '__')
    try:
        return {ws.cache_get(root, name, 86400) or ws.cache_put(root, name, gh.default_branch(repo))}
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
    hit = sorted(set(targets) & _default(root, origin(cwd)))
    if hit:
        return deny(f'{"deleting" if deleting else "pushing to"} the default branch {hit[0]} refused: every change '
                    'reaches it through a pull request with its evidence. Push a branch and open a PR.')
    return None


def _repo_number(args, cwd):
    repo, number = '', None
    for i, arg in enumerate(args):
        if arg in ('--repo', '-R') and i + 1 < len(args):
            repo = args[i + 1]
        match = re.fullmatch(r'https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)/?', arg)
        if match:
            repo, number = match[1], int(match[2])
        elif arg.isdigit() and number is None and (i == 0 or args[i - 1] not in ('--repo', '-R')):
            number = int(arg)
    return repo or origin(cwd), number


def gh_command(root, args, cwd, session, command=''):
    if args[:2] == ['pr', 'merge']:
        if '--admin' in args:
            return deny('--admin bypasses branch protection; WUWEI never merges around the repository rules.')
        repo, number = _repo_number(args[2:], cwd)
        return merge_door(root, repo, number, auto='--auto' in args)
    if args[:2] == ['repo', 'delete']:
        return deny('deleting a repository is the owner\'s act, never an agent\'s.')
    if args[:1] == ['api'] and len(args) > 1:
        method = next((args[i + 1].upper() for i, a in enumerate(args[:-1]) if a in ('-X', '--method')), '')
        if not method and any(a in ('-f', '-F', '--field', '--raw-field', '--input') for a in args):
            method = 'POST'
        endpoint = next((a for a in args[1:] if not a.startswith('-') and '/' in a), '')
        merging = re.search(r'repos/([\w.-]+/[\w.-]+)/pulls/(\d+)/(merge|ccr/auto_merge)$', endpoint)
        if merging and method == 'PUT':
            return merge_door(root, merging[1], int(merging[2]), auto=merging[3] != 'merge')
        if method in ('POST', 'PUT', 'PATCH', 'DELETE') and GUARDED_API.search(endpoint):
            return deny(f'gh api {method} {endpoint} changes protection, statuses, merges or access: the '
                        'repository rules and the merge door are not changed from an agent session.')
    if args[:2] == ['pr', 'create']:
        flag = lambda *names: next((args[i + 1] for i, a in enumerate(args[:-1]) if a in names), '')  # noqa: E731
        try:
            text = command + Path(cwd, flag('--body-file', '-F')).read_text(encoding='utf-8') if flag('--body-file', '-F') else command
        except OSError:
            text = command
        found = create_door(root, _repo_number(args, cwd)[0], flag('--head', '-H') or current_branch(cwd),
                            flag('--base', '-B'), text)
        if found or once(root, session, 'pr-standard'):
            version = json.loads((PR_STANDARD.parents[1] / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']
            return found or {'decision': 'note', 'reason': PR_STANDARD.read_text(encoding='utf-8').strip().replace('<version>', version)}
    return None


def create_door(root, repo, branch, base, text):
    """Gates run on the pushed branch before its PR opens (#1050): review and merge start at a gated head."""
    try:
        diff = gh.compare(repo, base or sorted(_default(root, repo))[0], branch)
    except gh.GhError as exc:
        return deny(f'cannot read {branch} on {repo} ({exc}): push the branch; its PR opens once its gates pass there.')
    named = evidence.ITEM.search(text or '')
    pr = {'body': f'WUWEI-Item: {named[1]}' if named else '', 'headRefName': branch}
    item_id, tier, gates, why = evidence.gates_for(root, repo, pr, diff['files'], evidence.item_for(root, pr, repo))
    head = (diff.get('commits') or [{}])[-1].get('sha', '')
    found = evidence.gate_gaps(root, repo, item_id, gates, head, why, '', tier)
    return deny(f'{repo} {branch} opens as a PR once its gates pass at the branch head (gates run before review):\n'
                + '\n'.join('- ' + g['text'] for g in found)) if found else None


def merge_door(root, repo, number, auto=False):
    """Every merge route (gh pr merge, gh api PUT .../merge, a GitHub MCP merge tool) meets the same
    evidence: only safety gaps hold it; the process fit it flows past is recorded."""
    if not repo or number is None:
        return deny('name the PR by number or URL (and --repo when outside its checkout) so WUWEI can read '
                    'its evidence before the merge.')
    found = evidence.gaps(root, repo, number)
    gaps = [g for g in evidence.blocking(found) if not (auto and g['text'] == 'CI running')]  # auto-merge waits for CI
    if gaps:
        return deny(f'{repo}#{number} is not ready to merge:\n' + '\n'.join('- ' + g['text'] for g in gaps))
    ws.record(root, 'merge.checked', {'pr': f'{repo}#{number}', 'auto': auto,
                                      'process': [g['text'] for g in found if g['kind'] == 'process']})
    return None


def once(root, session, topic):
    seen = ws.cache_get(root, f'notes-{session}', 7 * 86400) or []
    if topic not in seen:
        ws.cache_put(root, f'notes-{session}', seen + [topic])
    return topic not in seen


def leak(root, text):
    canary_file = Path(root) / ws.DIR / 'canary'
    canary = canary_file.read_text(encoding='utf-8').strip() if canary_file.is_file() else ''
    if canary and canary in text:
        return deny('the workspace canary is in this outward call: workspace content would leave the machine.')
    found = SECRETS.search(text)
    return deny(f'a secret ({found[0][:6]}...) is in this outward call; remove it before sending.') if found else None


def bash(root, command, cwd, session):
    try:
        parsed = segments(command)
    except ValueError as exc:
        return DOORS.search(command) and deny(f'cannot read this command ({exc}) and it names a door (git push, gh, wuwei hook, '
                                              'the ledger): close the quote, or put the text in a file (gh --body-file, git commit -F).')
    for argv, targets in parsed:
        program = Path(argv[0]).name if argv else ''
        if any(LEDGER.search(t) for t in targets) or any(LEDGER.search(a) for a in argv[1:]) and (
                program in WRITERS or program == 'sed' and '-i' in argv or program.startswith('python')):
            return deny('the ledger is written only by WUWEI\'s hooks; it is the audit record.')
        if program == 'wuwei' and argv[1:2] == ['hook']:
            return deny('wuwei hook is called by the harness, never by a session: a hand-made call would forge the record.')
        if program in NETWORK and (found := leak(root, ' '.join(argv))):
            return found
        if program == 'git':
            rest, i, here = argv[1:], 0, cwd
            while i < len(rest) and rest[i].startswith('-'):
                if rest[i] == '-C' and i + 1 < len(rest):
                    here = rest[i + 1]
                i += 2 if rest[i] in ('-C', '-c', '--git-dir', '--work-tree') else 1
            if rest[i:i + 1] == ['push'] and (found := git_push(root, rest[i + 1:], here)):
                return found
        elif program == 'gh' and (found := gh_command(root, argv[1:], cwd, session, command)):
            return found
        elif program in INFRA and INFRA[program] & set(argv[1:]):
            return {'decision': 'ask', 'reason': f'{program} {" ".join(a for a in argv[1:] if a in INFRA[program])} '
                    'changes infrastructure: a one-way door the owner decides.'}
    return None


def pre_tool(root, payload):
    tool = payload.get('tool_name', '')
    data = payload.get('tool_input') or {}
    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        paths = [str(data.get('file_path') or data.get('notebook_path') or ''), *map(str, data.get('file_paths') or ())]
        return deny('the ledger is written only by WUWEI\'s hooks; it is the audit record.') if any(map(LEDGER.search, paths)) else None
    if tool == 'AskUserQuestion':
        questions = [str(q.get('question', '')) for q in data.get('questions') or () if isinstance(q, dict)]
        process = [q for q in questions if q.strip().lower().startswith('exception:') and re.search(
            r"specs/|openspec/|no spec in the diff|template's sections|changed lines|open \d+ days", q)]
        if process:
            return deny('process gaps never block a merge and are nobody\'s decision: merge when the safety '
                        'evidence is complete; the merge records the process fit for the retro.')
        unparsed = [q for q in questions if q.strip().lower().startswith(('exception:', 'owner review:', 'breaking:'))
                    and not re.search(r'[\w.-]+/[\w.-]+#\d+ at [0-9a-f]{7,40}', q)]
        if unparsed:
            return deny(f'"{unparsed[0][:120]}" will not be recorded as asked (one-way:, scope:, goal:, trust:, infra: '
                        'and plan: take any wording). Use the exact shape: "exception: '
                        'owner/repo#n at <sha7> [and #m at <sha7>]: <the gap as wuwei evidence prints it>. <question>" or '
                        '"owner review: owner/repo#n at <sha7>. <question>" or "breaking: owner/repo#n at <sha7>: '
                        '<what breaks>. Announced at <link>. Proceed?".')
        unclassed = [q for q in questions if not q.strip().lower().startswith(OWNER_CLASSES)]
        named = '; '.join(f'"{q[:120]}"' for q in unclassed)
        rest = ' Decide those yourself and resend the classed questions on their own.' if len(unclassed) < len(questions) else ''
        return deny(f'{NOT_OWNERS}\nSent back: {named}.{rest}') if unclassed else None
    if tool.startswith('mcp__') and tool.endswith(('merge_pull_request', 'enable_pr_auto_merge')):
        number = data.get('pullNumber', data.get('pull_number'))
        repo = f'{data.get("owner")}/{data.get("repo")}' if data.get('owner') and data.get('repo') else ''
        return leak(root, json.dumps(data)) or merge_door(root, repo, int(number) if str(number).isdigit() else None,
                                                          auto=tool.endswith('enable_pr_auto_merge'))
    if tool.startswith('mcp__') and tool.endswith('create_pull_request'):
        return leak(root, json.dumps(data)) or create_door(root, f'{data.get("owner")}/{data.get("repo")}', str(
            data.get('head', '')), str(data.get('base', '')), str(data.get('body', '')))
    if tool.startswith('mcp__'):
        return leak(root, json.dumps(data))
    if tool == 'Bash':
        return bash(root, str(data.get('command', '')), payload.get('cwd') or '.', payload.get('session_id', ''))
    return None
