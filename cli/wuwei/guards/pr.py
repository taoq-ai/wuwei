"""Pre-PR evidence and non-overridable review/merge boundaries."""

import os
from fnmatch import fnmatchcase
import posixpath
from pathlib import Path
import re
import shlex
from urllib.parse import unquote, urlsplit

from wuwei import registry, shell, verdict, workspace
from wuwei.guards import Guard
from wuwei.guards.commit_push import data
from wuwei.guards.protect_state import _cd_target, _cwd


GATES = ('arch', 'quality', 'security')
# Built-ins cannot be shadowed by gh aliases. Unknown commands stay opaque.
GH_BUILTINS = set('agent-task alias api attestation auth browse cache codespace completion '
                  'config copilot discussion extension gist gpg-key help issue label licenses '
                  'org pr preview project release repo ruleset run search secret skill ssh-key '
                  'status variable version workflow'.split())


def merge_check(repo, pr, cwd, root, config):
    from wuwei import merge
    if pr is None:
        return 1, 'merge policy requires an explicit PR; use wuwei merge <pr>'
    result = merge.check(pr, root, cwd=cwd, repo=repo)
    if result.exit:
        return result.exit, result.reason
    return 1, 'merge policy passed; use wuwei merge <pr> to record evidence and monitor the merge'


def possible_workspace_change(raw, directories):
    """Scope a failed parse from directory operands, never from gh arguments."""
    lexer = shlex.shlex(raw, posix=False, punctuation_chars=';&|()')
    lexer.whitespace_split = True
    while True:
        start = lexer.instream.tell()
        try:
            word = next(lexer)
        except StopIteration:
            return False
        except ValueError:
            # Inspect an unfinished quoted script, not unrelated malformed argv.
            tail = raw[start:].strip().lstrip("\"'")
            return bool(tail and tail != raw and possible_workspace_change(tail, directories))
        try:
            decoded = shlex.split(word)[0]
        except ValueError:
            continue
        if decoded in ('cd', 'pushd'):
            try:
                args = [decoded]
                for operand in lexer:
                    if operand in (';', '&', '&&', '|', '||', ')'):
                        break
                    args.append(operand)
                    if operand not in ('-L', '-P', '--'):
                        break
                command, = shell.normalize(' '.join(args))
                target = _cd_target(command)
            except ValueError:
                return True
            destinations = {(base / target).resolve() for base in directories}
            if any(workspace.scope(path) for path in destinations):
                return True
            directories.update(destinations)
            if len(directories) > 64:
                return True
        elif word.startswith(('"', "'")) and decoded != word:
            # Shell -c and interpreter strings may contain directory changes.
            if possible_workspace_change(decoded, directories):
                return True


def values(found, *keys):
    return [found[key] for key in keys if key in found]


def _recorded_gates(root, sha, records, item, items=None):
    """Check the bounded fix and delta path recorded by the receive producer."""
    from wuwei.dispatch import gate_set
    candidates = [item] if item is not None else sorted({
        key.split(':', 1)[0] for key in records if isinstance(key, str) and ':' in key})
    failures = []
    for candidate in candidates:
        roles = gate_set((items or {}).get(candidate, {}))
        initial = [records.get(f'{candidate}:{role}:initial') for role in roles]
        missing = [role for role, row in zip(roles, initial) if row is None]
        if missing:
            failures.append((candidate, missing))
            continue
        if len({row['head'] for row in initial}) != 1:
            raise ValueError('initial gate verdicts disagree on HEAD')
        complete = True
        missing = []
        for role, first in zip(roles, initial):
            row = records.get(f'{candidate}:{role}:delta') if first['verdict'] == 'FIX' else first
            if row is None or (row['verdict'] != 'PASS' and not (
                    first['verdict'] == 'FIX' and row['verdict'] == 'FIX'
                    and row['blocks'] is False)):
                complete = False
                missing.append(role)
                continue
            path = root / row['file']
            expected = workspace.day_dir(root) / 'decisions'
            if path.parent != expected or path.is_symlink() or not path.name.startswith('gate-'):
                raise ValueError('gate verdict path is outside the day decisions')
            text = path.read_text(encoding='utf-8')
            code, reason = verdict.lint(text, quality=role == 'quality', class_sweep=True)
            if code:
                raise ValueError(f'{role} verdict: {reason}')
            active = verdict.active_text(text)
            heads = verdict.rows(active, 'Head')
            decisions = re.findall(verdict.VERDICT_ROW, active, re.M)
            if heads != [row['head']] or decisions != [row['verdict']]:
                raise ValueError(f'{role} recorded verdict differs from file')
            actual_blocks = any(re.search(verdict.BLOCKS_YES, block, re.I)
                                for block in verdict.finding_blocks(active))
            if row['blocks'] is not actual_blocks:
                raise ValueError(f'{role} recorded blocking status differs from file')
            if not sha.lower().startswith(row['head'].lower()) and (
                    first['verdict'] == 'FIX' or not any(
                        initial_row['verdict'] == 'FIX' for initial_row in initial)):
                complete = False
                missing.append(role)
        if complete:
            return 0, ''
        failures.append((candidate, missing))
    candidate, missing = min(failures, key=lambda row: len(row[1])) if failures else (item, list(GATES))
    label = f' for item {candidate}' if candidate else ''
    return 1, f'pre-PR gates not passed at current HEAD {sha}{label}: {", ".join(missing or GATES)}; run the named gate for this HEAD'


def gate_check(root, cwd, config, *, sha=None, item=None):
    vcs = registry.load('vcs', config)
    if sha is None:
        sha = data(vcs.head(str(cwd), root=root)).get('sha')
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha):
        raise ValueError('invalid current HEAD')
    from wuwei import state
    current = state.read_state(root)
    recorded = current['gate_verdicts']
    if recorded:
        return _recorded_gates(root, sha, recorded, item, current['items'])
    groups = {}
    for path in sorted((workspace.day_dir(root) / 'decisions').glob('gate-*.md')):
        match = re.fullmatch(r'gate-(.+)-(arch|quality|security)\.md', path.name)
        if not match:
            continue
        found_item, gate = match.groups()
        if item is not None and found_item != item:
            continue
        passed = groups.setdefault(found_item, set())
        try:
            text = path.read_text(encoding='utf-8')
            active = verdict.active_text(text)
            heads = verdict.rows(active, 'Head')
            if len(heads) != 1 or not re.fullmatch(r'[0-9a-fA-F]{7,64}', heads[0].strip()):
                raise ValueError('expected exactly one valid Head row')
            head = heads[0].strip().lower()
            if len(head) < len(sha):
                resolved = data(vcs.resolve(str(cwd), head, root=root)).get('sha')
                if (not isinstance(resolved, str)
                        or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', resolved)
                        or not resolved.startswith(head)):
                    raise ValueError('invalid resolved Head')
                head = resolved
            if head != sha:
                continue
            decisions = re.findall(r'^(?:## |- )?Verdict:? *(\w+)\b', active, re.M)
            if len(decisions) == 1 and decisions[0] in ('FIX', 'PARK', 'ESCALATE'):
                continue
            code, reason = verdict.lint(text, quality=gate == 'quality', class_sweep=True)
            if code:
                raise ValueError(reason)
            if decisions == ['PASS']:
                passed.add(gate)
        except (OSError, ValueError) as exc:
            raise ValueError(f'{gate} verdict: {exc}') from exc
    if any(all(gate in passed for gate in GATES) for passed in groups.values()):
        return 0, ''
    best = max(groups.values(), key=len, default=set())
    missing = ', '.join(gate for gate in GATES if gate not in best)
    return 1, f'pre-PR gates not passed at current HEAD {sha}: {missing}; run the named gate for this HEAD'


def create_check(args, command, cwd, root, config):
    operands, found = shell.operands(args, {
        '--reviewer', '-r', '--title', '-t', '--body', '-b', '--body-file', '-F',
        '--base', '-B', '--head', '-H', '--repo', '-R', '--assignee', '-a',
        '--label', '-l', '--milestone', '-m', '--project', '-p', '--template', '-T', '--recover',
    }, {'--draft', '-d', '--fill', '--fill-first', '--fill-verbose', '--web', '-w', '--editor', '-e'})
    if values(found, '--repo', '-R'):
        raise ValueError('repository override cannot be tied to the checked local HEAD')
    if values(found, '--head', '-H'):
        raise ValueError('explicit head cannot be tied to the checked local HEAD')
    if any(key.startswith('GIT_CONFIG') or key in (
            'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE', 'GIT_NAMESPACE',
            'GH_REPO', 'GH_HOST', 'GH_CONFIG_DIR') for key in command.env.keys() | os.environ.keys()):
        raise ValueError('repository environment override cannot be verified')
    if operands or values(found, '--web', '-w'):
        raise ValueError('opaque PR create; use explicit CLI options')
    reviewers = values(found, '--reviewer', '-r')
    if (reviewers or config['shepherd']['min_reviewers']) and not (reviewers and all(
            part.strip() and not part.strip().startswith('-')
            for value in reviewers for part in value.split(','))):
        return 1, 'PR create requires a named --reviewer in the same command'
    return gate_check(root, cwd, config)


def api_check(args, cwd, root, config):
    from wuwei.security import gh_outbound
    operands, found = shell.operands(args, {'--method', '-X', '--field', '-F', '--raw-field', '-f',
                                    '--input', '--header', '-H', '--hostname', '--jq', '-q',
                                    '--template', '-t', '--cache', '--preview', '-p'},
                              {'--silent', '--include', '-i', '--paginate', '--slurp', '--verbose'})
    if len(operands) != 1:
        raise ValueError('expected one API endpoint')
    endpoint = operands[0]
    if '://' in endpoint:
        endpoint = urlsplit(endpoint).path
    else:
        endpoint = endpoint.split('?', 1)[0].split('#', 1)[0]
    endpoint = posixpath.normpath(unquote(endpoint)).strip('/')
    endpoint = re.sub(r'^api/v3/', '', endpoint, flags=re.I)
    fields = values(found, '--field', '-F', '--raw-field', '-f')
    methods = values(found, '--method', '-X')
    method = methods[-1].upper() if methods else ('POST' if fields or '--input' in found else 'GET')
    code, reason = gh_outbound(args, cwd, root, api=True,
                              text_write=bool(fields or '--input' in found
                                              or method not in ('GET', 'HEAD', 'OPTIONS')))
    if code:
        return code, reason
    if endpoint.casefold() in ('graphql', 'api/graphql'):
        raise ValueError('opaque GraphQL API request; use explicit PR commands')
    if method in ('GET', 'HEAD', 'OPTIONS'):
        return 0, ''
    if (re.fullmatch(r'repos/[^/]+/[^/]+/(?:branches/.+/protection(?:/.*)?|rulesets(?:/.*)?)', endpoint, re.I)
            or re.fullmatch(r'orgs/[^/]+/rulesets(?:/.*)?', endpoint, re.I)):
        return 1, 'branch protection changes are refused'
    match = re.fullmatch(r'repos/([^/]+/[^/]+)/pulls/(\d+)/merge', endpoint, re.I)
    if match:
        return merge_check(match[1], match[2], cwd, root, config)
    match = re.fullmatch(r'repos/([^/]+/[^/]+)/merges', endpoint, re.I)
    if match:
        return merge_check(match[1], None, cwd, root, config)
    match = re.fullmatch(r'repos/([^/]+/[^/]+)/git/refs/heads/(.+)', endpoint, re.I)
    if match and method in ('PATCH', 'POST'):
        if any(fnmatchcase(match[2], pattern) for pattern in config['environments']):
            return 1, 'push to an environment branch is refused'
        repo = next((repo for repo in config['repos'] if repo['name'].casefold() == match[1].casefold()), None)
        if repo is None:
            raise ValueError('API repository default branch is unmeasured')
        if match[2] == repo['default_branch']:
            return 1, 'push to the default branch is refused'
    if re.fullmatch(r'repos/[^/]+/[^/]+/pulls/\d+/reviews(?:/.*)?', endpoint, re.I):
        events = [field.partition('=')[2] for field in fields if field.partition('=')[0] == 'event']
        if 'APPROVE' in events:
            return 1, 'PR approval is refused'
        if '--input' in found or not events or any(event not in ('COMMENT', 'REQUEST_CHANGES') for event in events):
            raise ValueError('opaque review body; cannot rule out approval')
    if re.fullmatch(r'repos/[^/]+/[^/]+/pulls', endpoint, re.I):
        raise ValueError('API PR create cannot request a reviewer in the same action; use gh pr create')
    return 0, ''


def action(command, cwd, root, config, isolated):
    from wuwei.security import gh_outbound
    args = command.argv[1:]
    if args in (['--version'], ['--help'], ['-h']):
        return 0, ''
    # Global repository selection can appear before the subcommand.
    prefix = []
    family = None
    while args:
        if args[0] in ('pr', 'api') and family is None:
            family = args.pop(0)
            continue
        if not args[0].startswith('-'):
            break
        # API flags have their own parser, including flags before the endpoint.
        if family == 'api':
            break
        option = args.pop(0)
        prefix.append(option)
        if option in ('-R', '--repo'):
            if not args:
                raise ValueError('missing repository value')
            prefix.append(args.pop(0))
        elif not option.startswith(('--repo=', '-R')):
            raise ValueError('unsupported gh global option')
    if family == 'api':
        return api_check(args + prefix, cwd, root, config)
    text_write = ((family == 'pr' and args and args[0] in ('comment', 'create', 'edit', 'review', 'merge'))
                  or (len(args) > 1 and ((args[0] == 'issue' and args[1] in ('comment', 'create', 'edit'))
                                        or (args[0] == 'release' and args[1] in ('create', 'edit')))))
    code, reason = gh_outbound(command.argv, cwd, root, text_write=text_write)
    if code:
        return code, reason
    if family is None and args:
        if args[0] not in GH_BUILTINS:
            raise ValueError('opaque gh alias or extension; use a built-in command')
        if args[0] == 'alias' and any(arg in ('set', 'import', 'delete') for arg in args[1:]):
            return 1, 'gh alias changes are refused'
    if not args or family != 'pr':
        return 0, ''
    verb, args = args[0], prefix + args[1:]
    if verb == 'create':
        if not isolated:
            raise ValueError('run PR create separately without redirections to keep HEAD evidence current')
        return create_check(args, command, cwd, root, config)
    if verb == 'merge':
        operands, found = shell.operands(args, {'--repo', '-R', '--subject', '-t', '--body', '-b',
                                        '--body-file', '-F', '--author-email', '-A', '--match-head-commit'},
                                  {'--admin', '--auto', '--disable-auto', '--delete-branch', '-d',
                                   '--merge', '-m', '--rebase', '-r', '--squash', '-s'})
        if 'true' in values(found, '--admin'):
            return 1, 'admin merge is refused'
        repos = values(found, '--repo', '-R')
        return merge_check(repos[0] if repos else None, operands[0] if operands else None,
                           cwd, root, config)
    if verb == 'review':
        _, found = shell.operands(args, {'--repo', '-R', '--body', '-b', '--body-file', '-F'},
                           {'--approve', '-a', '--comment', '-c', '--request-changes', '-r'})
        if 'true' in values(found, '--approve', '-a'):
            return 1, 'PR approval is refused'
    return 0, ''


def check(payload):
    try:
        raw = payload['tool_input']['command']
        if not isinstance(raw, str):
            raise ValueError('command must be text')
        if not shell.mentions(raw, {'gh'}) and shell.script_path(raw, payload['cwd']) is None:
            return 0, ''
        cwd = _cwd(payload)
        initial = workspace.scope(cwd)
        script = shell.script_text(raw, cwd) if initial else None
        script_relevant = bool(script and shell.mentions(script, {'gh'}, script=True)
                               and shell.mentions(script, {'create', 'merge', 'review', 'api', 'admin'}, script=True))
        if not shell.mentions(raw, {'gh'}) and not script_relevant:
            return 0, ''
        try:
            commands = shell.normalize(raw)
        except shell.ParseError:
            if initial is None and not possible_workspace_change(raw, {cwd}):
                return 0, ''
            raise
        directories = {cwd}
        contexts = {cwd: initial} if initial else {}
        for command in commands:
            program = Path(command.argv[0]).name if command.argv else ''
            for key in ('GIT_DIR', 'GIT_WORK_TREE'):
                target = command.env.get(key, os.environ.get(key))
                if target:
                    directories |= {(base / target).resolve() for base in list(directories)}
            if program in ('cd', 'pushd'):
                target = _cd_target(command)
                directories |= {(base / target).resolve() for base in list(directories)}
                if len(directories) > 64:
                    raise ValueError('too many possible directories; split the command')
            for directory in directories:
                if directory not in contexts:
                    context = workspace.scope(directory)
                    if context:
                        contexts[directory] = context
        if not contexts:
            return 0, ''
        if script_relevant:
            raise ValueError('opaque script command; run gh as a plain command')
        for index, command in enumerate(commands):
            if not command.argv:
                continue
            program = Path(command.argv[0]).name
            fed = bool(command.reads) or index > 0 and commands[index - 1].separator == '|'
            if shell.is_opaque(command.argv, fed):
                raise ValueError(f'opaque command: {" ".join(command.argv)}; run gh as a plain command')
            if program == 'popd':
                raise ValueError('opaque directory stack; use an explicit directory')
            if program == 'gh':
                for directory, (root, config) in contexts.items():
                    result = action(command, directory, root, config,
                                    len(commands) == 1 and not command.writes)
                    if result[0]:
                        return result
        return 0, ''
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, RuntimeError) as exc:
        return 2, f'PR guard could not run: {exc}'


GUARDS = [Guard('PreToolUse', 'Bash', check)]
