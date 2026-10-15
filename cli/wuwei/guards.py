"""The few doors WUWEI holds. Everything else passes; the harness's own permission rules decide
who may call which tool. A door that cannot read its evidence stays shut; a guard that cannot
read a command lets it through (the audit still sees it)."""

import json
from pathlib import Path
import re
import shlex
import subprocess

from wuwei import evidence, gh, ws

SHELLS = {'sh', 'bash', 'zsh', 'dash'}
WRAPPERS = {'env', 'command', 'exec', 'nohup', 'time', 'sudo', 'xargs', 'nice'}
CONTROL = {'&&', '||', ';', '|', '&', ';;', '(', ')'}
INFRA = {'terraform': {'apply', 'destroy', 'import'}, 'tofu': {'apply', 'destroy', 'import'},
         'pulumi': {'up', 'destroy'}, 'kubectl': {'apply', 'delete', 'create', 'replace', 'patch', 'scale'},
         'helm': {'install', 'upgrade', 'uninstall', 'rollback'}}
NETWORK = {'gh', 'curl', 'wget', 'nc', 'ssh', 'scp', 'http', 'https'}
WRITERS = {'tee', 'truncate', 'rm', 'mv', 'cp', 'dd', 'chmod', 'ln', 'shred'}
SECRETS = re.compile(r'gh[pousr]_[A-Za-z0-9]{36}|github_pat_\w{22,}|sk-ant-[\w-]{20,}|sk-[A-Za-z0-9]{32,}'
                     r'|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AIza[\w-]{35}')
LEDGER = re.compile(r'(^|/)\.wuwei/ledger\.jsonl$')
GUARDED_API = re.compile(r'/branches/[^/]+/protection|/rulesets|/statuses/|/pulls/\d+/merge|/collaborators'
                         r'|/hooks|/keys|/actions/secrets|/environments')
OWNER_CLASSES = ('one-way:', 'scope:', 'goal:', 'trust:', 'infra:', 'owner review:', 'exception:', 'plan:')
NOT_OWNERS = ('''question sent back: the process answers it, not the owner.
Take your recommendation, record it under Assumptions in the spec or PR body (what you assumed, why, what would overturn it) and go on. Ask the owner only for a
decision of one of these classes, named at the start of the question: ''' + ', '.join(OWNER_CLASSES)
              + '. The plan is your mandate: never ask whether to continue planned work.')
PR_STANDARD = '''WUWEI PR standard. Start from this body (keep the repository's own template sections too):

WUWEI-Item: <plan item id>

## What and why
<what changed and why, in two or three sentences>

## Assumptions
<each two-way choice you took: what, why, what would overturn it; or none>

## Tests
<the tests that cover the change; or a line "No test: <reason>">

## Review notes
<residual non-blocking findings; or none>

Request a reviewer. Before merge every gate the tier needs passes at the head, CI is green and every
review thread is answered.'''


def deny(reason):
    return {'decision': 'deny', 'reason': reason}


def origin(cwd):
    """owner/repo of the origin remote at cwd, or ''."""
    try:
        url = subprocess.run(['git', '-C', cwd, 'remote', 'get-url', 'origin'], capture_output=True,
                             text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''
    match = re.search(r'github\.com[:/]([\w.-]+/[\w.-]+?)(\.git)?$', url)
    return match[1] if match else ''


def current_branch(cwd):
    try:
        return subprocess.run(['git', '-C', cwd, 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def segments(command):
    """Each simple command as (argv, redirect targets), with sh -c bodies and wrappers unwrapped."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    out, current = [], []
    for token in tokens + [';']:
        if token in CONTROL:
            if current:
                out.extend(_unwrap(current))
            current = []
        else:
            current.append(token)
    return out


def _unwrap(tokens):
    argv, targets, i = [], [], 0
    while i < len(tokens):
        if tokens[i] in ('>', '>>', '>|', '&>', '2>', '1>') and i + 1 < len(tokens):
            targets.append(tokens[i + 1])
            i += 2
            continue
        argv.append(tokens[i])
        i += 1
    while argv and (re.fullmatch(r'[A-Za-z_]\w*=.*', argv[0]) or Path(argv[0]).name in WRAPPERS):
        argv = argv[1:]
        while argv and Path(argv[0]).name not in WRAPPERS and argv[0].startswith('-'):
            argv = argv[1:]
    if len(argv) >= 3 and Path(argv[0]).name in SHELLS and argv[1] == '-c':
        return segments(argv[2]) + ([([], targets)] if targets else [])
    return [(argv, targets)]


def _default(root, repo):
    if not repo:
        return {'main', 'master'}
    name = 'default-' + repo.replace('/', '__')
    branch = ws.cache_get(root, name, 86400)
    if branch is None:
        try:
            branch = ws.cache_put(root, name, gh.default_branch(repo))
        except gh.GhError:
            return {'main', 'master'}
    return {branch}


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
        if ref.startswith(':'):
            deleting = True
    protected = _default(root, origin(cwd))
    hit = [t for t in targets if t in protected]
    if hit:
        verb = 'deleting' if deleting else 'pushing to'
        return deny(f'{verb} the default branch {hit[0]} refused: every change reaches it through a pull '
                    'request with its evidence. Push a branch and open a PR.')
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


def gh_command(root, args, cwd, session):
    if args[:2] == ['pr', 'merge']:
        if '--admin' in args:
            return deny('--admin bypasses branch protection; WUWEI never merges around the repository rules.')
        repo, number = _repo_number(args[2:], cwd)
        if not repo or number is None:
            return deny('name the PR by number or URL (and --repo when outside its checkout) so WUWEI can read '
                        'its evidence before the merge.')
        gaps = evidence.gaps(root, repo, number)
        if gaps:
            return deny(f'{repo}#{number} is not ready to merge:\n' + '\n'.join('- ' + g['text'] for g in gaps))
        try:
            used = [list(w) for w in evidence.waivers(gh.pr(repo, number).get('body'))]
        except gh.GhError:
            used = []
        ws.record(root, 'merge.checked', {'pr': f'{repo}#{number}', 'waived': used})
        return None
    if args[:2] == ['repo', 'delete']:
        return deny('deleting a repository is the owner\'s act, never an agent\'s.')
    if args[:1] == ['api'] and len(args) > 1:
        method = next((args[i + 1].upper() for i, a in enumerate(args[:-1]) if a in ('-X', '--method')), '')
        if not method and any(a in ('-f', '-F', '--field', '--raw-field', '--input') for a in args):
            method = 'POST'
        endpoint = next((a for a in args[1:] if not a.startswith('-') and '/' in a), '')
        if method in ('POST', 'PUT', 'PATCH', 'DELETE') and GUARDED_API.search(endpoint):
            return deny(f'gh api {method} {endpoint} changes protection, statuses, merges or access: the '
                        'repository rules and the merge door are not changed from an agent session.')
    if args[:2] == ['pr', 'create'] and once(root, session, 'pr-standard'):
        return {'decision': 'note', 'reason': PR_STANDARD}
    return None


def once(root, session, topic):
    name = f'notes-{session}'
    seen = ws.cache_get(root, name, 7 * 86400) or []
    if topic in seen:
        return False
    ws.cache_put(root, name, seen + [topic])
    return True


def leak(root, text):
    canary_file = Path(root) / ws.DIR / 'canary'
    canary = canary_file.read_text(encoding='utf-8').strip() if canary_file.is_file() else ''
    if canary and canary in text:
        return deny('the workspace canary is in this outward call: workspace content would leave the machine.')
    found = SECRETS.search(text)
    if found:
        return deny(f'a secret ({found[0][:6]}...) is in this outward call; remove it before sending.')
    return None


def bash(root, command, cwd, session):
    for argv, targets in segments(command):
        if any(LEDGER.search(t) for t in targets):
            return deny('the ledger is written only by WUWEI\'s hooks; it is the audit record.')
        if not argv:
            continue
        program = Path(argv[0]).name
        if program == 'wuwei' and argv[1:2] == ['hook']:
            return deny('wuwei hook is called by the harness, never by a session: a hand-made call would forge the record.')
        if any(LEDGER.search(a) for a in argv[1:]) and (program in WRITERS or program == 'sed' and '-i' in argv
                                                        or program.startswith('python')):
            return deny('the ledger is written only by WUWEI\'s hooks; it is the audit record.')
        if program in NETWORK:
            found = leak(root, ' '.join(argv))
            if found:
                return found
        if program == 'git':
            rest, i, here = argv[1:], 0, cwd
            while i < len(rest) and rest[i].startswith('-'):
                if rest[i] == '-C' and i + 1 < len(rest):
                    here = rest[i + 1]
                i += 2 if rest[i] in ('-C', '-c', '--git-dir', '--work-tree') else 1
            if rest[i:i + 1] == ['push']:
                found = git_push(root, rest[i + 1:], here)
                if found:
                    return found
        elif program == 'gh':
            found = gh_command(root, argv[1:], cwd, session)
            if found:
                return found
        elif program in INFRA and INFRA[program] & set(argv[1:]):
            return {'decision': 'ask', 'reason': f'{program} {" ".join(a for a in argv[1:] if a in INFRA[program])} '
                    'changes infrastructure: a one-way door the owner decides.'}
    return None


def pre_tool(root, payload):
    tool = payload.get('tool_name', '')
    data = payload.get('tool_input') or {}
    cwd = payload.get('cwd') or '.'
    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        path = str(data.get('file_path') or data.get('notebook_path') or '')
        return deny('the ledger is written only by WUWEI\'s hooks; it is the audit record.') if LEDGER.search(path) else None
    if tool == 'AskUserQuestion':
        questions = [str(q.get('question', '')) for q in data.get('questions') or () if isinstance(q, dict)]
        process = [q for q in questions if q.strip().lower().startswith('exception:') and re.search(
            r"specs/|openspec/|no spec in the diff|template's sections|changed lines|open \d+ days", q)]
        if process:
            return deny('a process gap (spec artifacts, PR template, size, staleness) is yours to settle, not an '
                        'owner exception: add a line "Waive: <the gap text>: <why it does not apply>" to the PR body. '
                        'The waiver is recorded at merge and the retro reviews it.')
        unclassed = [q for q in questions if not q.strip().lower().startswith(OWNER_CLASSES)]
        if not unclassed:
            return None
        named = '; '.join(f'"{q[:120]}"' for q in unclassed)
        rest = ' Decide those yourself and resend the classed questions on their own.' if len(unclassed) < len(questions) else ''
        return deny(f'{NOT_OWNERS}\nSent back: {named}.{rest}')
    if tool.startswith('mcp__'):
        return leak(root, json.dumps(data))
    if tool == 'Bash':
        return bash(root, str(data.get('command', '')), cwd, payload.get('session_id', ''))
    return None
