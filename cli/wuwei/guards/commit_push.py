"""Commit and push policy shared by tool guards and native Git hooks."""

from pathlib import Path
import os
from fnmatch import fnmatchcase
import re
import shlex

from wuwei import shell
from wuwei.guards import Guard
from wuwei.registry import data
from wuwei.exits import DAMAGED


def _identity(value):
    if not isinstance(value, dict) or any(
            not isinstance(value.get(key), str) or not value[key].strip()
            or any(char in value[key] for char in '\n\r\0<>')
            for key in ('name', 'email')):
        raise ValueError(f'missing or malformed identity; {DAMAGED}')
    return value['name'], value['email']


def identity_check(expected, actual, head=None):
    """Preserve harness order: effective author, committer, then HEAD identities."""
    try:
        owner = _identity(expected)
        for kind in ('author', 'committer'):
            if _identity(actual[kind]) != owner:
                return 1, (f'GIT_{kind.upper()}_IDENT differs from configured identity; '
                           'create item worktrees with wuwei worktree add, or run '
                           f'git config user.name {shlex.quote(owner[0])} and then '
                           f'git config user.email {shlex.quote(owner[1])} in this worktree')
        if head is not None:
            for kind in ('author', 'committer'):
                if _identity(head[kind]) != owner:
                    return 1, 'HEAD author/committer do not match configured identity; run git commit --amend --reset-author --no-edit in the item worktree, then push again'
        return 0, ''
    except (KeyError, TypeError, ValueError) as exc:
        return 2, f'could not check identity: {exc}'


IDENTITY_SETTINGS = {f'{kind}.{field}' for kind in ('user', 'author', 'committer')
                     for field in ('name', 'email')}
IDENTITY_ENV = {f'GIT_{kind}_{field}' for kind in ('AUTHOR', 'COMMITTER')
                for field in ('NAME', 'EMAIL', 'DATE')}
COMMIT_VERBS = {'commit', 'merge', 'revert', 'cherry-pick', 'rebase', 'am', 'commit-tree', 'notes'}
REPO_ENV = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'}


def context(cwd, settings, env, root, push=None, identity=True):
    """Match cwd to a configured repository; identity=False reads no commit identity.

    With push=(remote, refspecs), also return push_context read alongside, or None.
    """
    from wuwei import registry, workspace

    if 'GIT_COMMON_DIR' in env:
        raise ValueError('GIT_COMMON_DIR overrides cannot be inspected safely; run unset GIT_COMMON_DIR, then run plain git from the item worktree')
    if not identity and (settings or env):
        raise ValueError('identity-free repository read takes no settings or env overrides; retry; if it repeats, run bin/wuwei doctor')
    if not identity and push is not None:
        raise ValueError('push checks need the commit identity; retry; if it repeats, run bin/wuwei doctor')
    config = workspace.load_config(root)
    vcs = registry.load('vcs', config)
    if push is None:
        return _context(cwd, settings, env, root, config, vcs, identity)
    if REPO_ENV & env.keys():
        return *_context(cwd, settings, env, root, config, vcs, identity), None
    # Without repository overrides, Git discovers the same repository from cwd.
    found, early = registry.together(lambda: _context(cwd, settings, env, root, config, vcs, identity),
                                     lambda: vcs.push_context(str(cwd), *push, root=root))
    return *found, early


def _context(cwd, settings, env, root, config, vcs, identity):
    actual = data(vcs.commit_context(str(cwd), settings, env, root=root) if identity
                  else vcs.repo_context(str(cwd), root=root))
    for key in ('path', 'common_dir'):
        if not isinstance(actual.get(key), str) or not Path(actual[key]).is_absolute():
            raise ValueError('missing repository context; run the command from inside a repository checkout or worktree; if it is one, run bin/wuwei doctor')
    for repo in config['repos']:
        path = (root / Path(repo['path']).expanduser()).resolve()
        # A checkout whose own .git directory is the common directory Git just measured
        # is that repository; reading it again would return the same directory.
        if (path / '.git').is_dir() and str((path / '.git').resolve()) == actual['common_dir']:
            return repo, actual, vcs
        configured = data(vcs.repo_context(str(path), root=root))
        if configured.get('common_dir') == actual['common_dir']:
            return repo, actual, vcs
    raise ValueError('repository is not configured in this workspace; work in a configured repository, or the owner adds this one with bin/wuwei config add-repo in a host terminal')


def push_check(repo, actual, push, root, vcs):
    """Check identities and push shape for either anchor; fast_evidence reads the evidence."""
    from wuwei import workspace

    result = identity_check(repo['identity'], actual, push['head'])
    if result[0]:
        return result
    item = _item(actual['path'], root)
    branch = item.lower() if item else '<branch>'
    sha = push['head']['sha']
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha):
        raise ValueError(f'invalid HEAD; {DAMAGED}')
    if type(push['force']) is not bool:
        raise ValueError(f'invalid force evidence; {DAMAGED}')
    if push['force']:
        return 1, f'force-push is refused; run it without --force: git push origin HEAD:refs/heads/{branch}'
    updates = push['updates']
    if not isinstance(updates, list) or not updates:
        raise ValueError(f'push destinations are unmeasured; run git push origin HEAD:refs/heads/{branch}')
    if not repo['default_branch'].strip():
        raise ValueError('missing default branch; the owner sets repos.<n>.default_branch with bin/wuwei config set in a host terminal')
    config = workspace.load_config(root)
    for update in updates:
        destination = update['destination']
        if isinstance(destination, str) and destination.startswith('refs/tags/'):
            # #530: a tag is a release. Below strict the deploy guard's release card and grants
            # (once, today, always) are the gate; strict refuses it from the session.
            if workspace.posture(config)[0] != 'strict':
                continue
            return 1, (f'tag push {destination} is a release; posture strict refuses it from the session; '
                       f'run git push origin HEAD:refs/heads/{branch} without the tag')
        if not isinstance(destination, str) or not destination.startswith('refs/heads/'):
            raise ValueError(f'only branch and tag pushes are supported; run git push origin HEAD:refs/heads/{branch}')
        if destination == 'refs/heads/' + repo['default_branch']:
            return 1, (f'push to the default branch {repo["default_branch"]} is refused; run git push '
                       f'origin HEAD:refs/heads/{branch} for the item branch instead')
        if any(fnmatchcase(destination.removeprefix('refs/heads/'), pattern)
               for pattern in config['environments']):
            return 1, f'push to an environment branch is refused; deploying is an owner action, so run git push origin HEAD:refs/heads/{branch} for the item branch'
        if update['source'] != sha:
            return 1, 'push must use the checked current HEAD; run git push <remote> HEAD:<branch> from the item worktree'
        commits = data(vcs.push_commits(actual['path'], push['remote'], destination,
                                       sha, update.get('remote_sha'), repo['default_branch'],
                                       root=root))['commits']
        if not isinstance(commits, list):
            raise ValueError('malformed pushed commit range; run git fetch origin in the worktree, then push again; if it repeats, run bin/wuwei doctor')
        for commit in commits:
            result = identity_check(repo['identity'], commit)
            if result[0]:
                return result[0], 'pushed commit identity: ' + result[1]
    return 0, ''


def fast_evidence(repo, sha, path, root):
    """#530: the configured fast checks recorded as passed at the pushed HEAD sha."""
    from wuwei import state
    item = _item(path, root)
    checks = f'bin/wuwei build check {item}' if item else 'bin/wuwei fast-checks in this worktree'
    evidence = state.read_state(root).get('fast_checks', {})
    if not isinstance(evidence, dict) or not isinstance(evidence.get(repo['name'], {}), dict):
        raise ValueError(f'malformed fast-check evidence; {DAMAGED}')
    for check in repo['fast_checks']:
        if not check.strip():
            raise ValueError('empty configured fast check; the owner removes the empty entry with bin/wuwei config set repos.<n>.fast_checks in a host terminal')
        record = evidence.get(repo['name'], {}).get(check)
        if record is None:
            return 1, f'fast check "{check}" has not passed for HEAD {sha[:12]}; run {checks}'
        if (not isinstance(record, dict) or not isinstance(record.get('sha'), str)
                or type(record.get('exit')) is not int or record['exit'] not in (0, 1, 2)):
            raise ValueError(f'malformed fast-check evidence; {DAMAGED}')
        if record['sha'] != sha or record['exit'] != 0:
            return 1, f'fast check "{check}" has not passed for HEAD {sha[:12]}; run {checks}'
    return 0, ''


def git_command(command, cwd, errors=None):
    """Consume Git's global argv options, never shell text."""
    def invalid(reason):
        if errors is None:
            raise ValueError(reason)
        errors.append(reason)

    args = iter(command.argv[1:])
    settings, env = {}, dict(command.env)
    for arg in args:
        if arg in ('-C', '-c') or arg.startswith(('-C', '-c')):
            flag, value = arg[:2], arg[2:] or next(args, None)
            if value is None:
                invalid(f'missing {flag} value')
                break
            if flag == '-C':
                cwd = (cwd / value).resolve()
            else:
                key, separator, value = value.partition('=')
                if not separator or key.lower() not in IDENTITY_SETTINGS:
                    invalid('unsupported Git configuration override')
                settings[key.lower()] = value
        elif arg.startswith(('--git-dir=', '--work-tree=')):
            key, _, value = arg.partition('=')
            env['GIT_DIR' if key == '--git-dir' else 'GIT_WORK_TREE'] = value
        elif arg in ('--git-dir', '--work-tree'):
            value = next(args, None)
            if value is None:
                invalid(f'missing {arg} value')
                break
            env['GIT_DIR' if arg == '--git-dir' else 'GIT_WORK_TREE'] = value
        elif arg in ('--no-pager', '--literal-pathspecs'):
            continue
        elif arg.startswith('-'):
            invalid('unsupported Git global option')
        else:
            return cwd, settings, env, arg, list(args)
    invalid('missing Git command')
    return cwd, settings, env, '', []


def commit_options(args, actual):
    # Expand common short flag bundles before interpreting value-taking options.
    args = list(args)
    reused = False
    reset = False
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if len(arg) > 2 and arg[0] == '-' and arg[1] in 'aenqsv':
            args.insert(index, '-' + arg[2:])
            arg = arg[:2]
        if arg == '--':
            break
        if arg in ('--no-verify', '-n'):
            return 1, 'disabling commit hooks is refused; run the commit without --no-verify or -n'
        if arg == '--reset-author':
            reset = True
        elif arg == '--amend':
            reused = True
        elif arg in ('-a', '--all', '-s', '--signoff', '-v', '--verbose', '-q', '--quiet',
                     '--allow-empty', '--allow-empty-message', '--no-edit', '--edit', '-e',
                     '--no-gpg-sign', '--dry-run') or arg.startswith('-S'):
            continue
        else:
            key, separator, value = arg.partition('=')
            if key in ('--author', '--message', '--file', '--template', '--date',
                       '--reuse-message', '--reedit-message', '--fixup', '--trailer'):
                if not separator:
                    if index == len(args):
                        raise ValueError('missing commit option value; add the value after the option')
                    value, index = args[index], index + 1
            elif arg[:2] in ('-m', '-F', '-t', '-C', '-c'):
                key, value = arg[:2], arg[2:]
                if not value:
                    if index == len(args):
                        raise ValueError('missing commit option value; add the value after the option')
                    value, index = args[index], index + 1
            elif not arg.startswith('-'):
                continue
            else:
                raise ValueError('unsupported commit option; remove it, or run the commit with -m, -a, --amend or --author only')
            if key == '--author':
                match = re.fullmatch(r'([^<>]+) <([^<>]+)>', value)
                if not match:
                    raise ValueError('commit author must be an explicit name and email; use --author \'Name <email>\' with the configured identity, or remove --author')
                actual['author'] = {'name': match[1], 'email': match[2]}
            if key in ('-C', '-c', '--reuse-message', '--reedit-message'):
                reused = True
    if reused and not reset:
        raise ValueError('reused commit authors require --reset-author; add --reset-author to the commit')
    return 0, ''


def _item(path, root):
    """The item of an item worktree (<root>/worktrees/<ITEM>), else None."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve() / 'worktrees').parts[0]
    except (ValueError, IndexError):
        return None


def push_options(args, branch='<branch>'):
    operands = []
    for arg in args:
        if (arg.startswith(('--force', '--mirror')) or arg.startswith('+')
                or arg.startswith('-') and not arg.startswith('--') and 'f' in arg[1:]):
            return (1, 'force-push is refused'), None, []
        if arg in ('--no-verify', '-n'):
            return (1, 'disabling push hooks is refused'), None, []
        if arg in ('-u', '--set-upstream', '-v', '--verbose', '-q', '--quiet',
                   '--porcelain', '--atomic', '--dry-run', '--thin', '--no-thin'):
            continue
        if arg.startswith('-'):
            raise ValueError(f'unsupported push option {arg}; run git push origin HEAD:refs/heads/{branch}')
        operands.append(arg)
    if len(operands) < 2:
        return (1, f'name the remote and the branch: run git push origin HEAD:refs/heads/{branch}'), None, []
    return (0, ''), operands[0], operands[1:]


def check(payload):
    try:
        from wuwei import workspace

        raw = payload['tool_input']['command']
        relevant = COMMIT_VERBS | {'push', 'config', 'wuwei-workspace', 'executable'} | IDENTITY_ENV | IDENTITY_SETTINGS
        script = shell.script_text(raw, payload['cwd'])
        opaque_script = script and shell.mentions(script, {'git', 'gh'}, script=True) and shell.mentions(script, relevant, script=True)
        if opaque_script:
            raw = script
        if not shell.mentions(raw, {'git', 'gh', 'rm'}) or not shell.mentions(raw, relevant):
            return 0, ''
        initial = Path(payload['cwd']).resolve()
        session = workspace.scope(initial)
        session_root = session[0] if session else None
        words = [value for key, value in os.environ.items() if key in REPO_ENV]
        try:
            commands = shell.normalize(raw, words=words)
        except shell.ParseError:
            # #347: rm is a publisher word here, so a hook pointer removal keeps its refusal.
            if session_root:
                if (found := shell.unread(raw, ('rm',), cwd=payload['cwd'])) is None:
                    raise
                return found
            # Literal tokens are observed by the shared parser, not reparsed here.
            bases = {initial}
            for word in words:
                value = word.partition('=')[2] if '=' in word else word.removeprefix('-C')
                for base in tuple(bases):
                    path = (base / value).resolve()
                    if workspace.scope(path):
                        if (found := shell.unread(raw, ('rm',), cwd=payload['cwd'])) is None:
                            raise
                        return found
                    if path.is_dir() and len(bases) < 64:
                        bases.add(path)
            if re.search(r'-C|\b(?:cd|pushd|popd|git-dir|work-tree|GIT_DIR|GIT_WORK_TREE)\b',
                         re.sub(r'''['"\\]''', '', raw)):
                # Parsing may have stopped before a target; do not guess its scope.
                if (found := shell.unread(raw, ('rm',), cwd=payload['cwd'])) is None:
                    raise
                return found
            return 0, ''
        scoped = []
        locations = {(): {initial}}
        mixed = any(command.separator in (';', '||', '|', '&', '\n') for command in commands)
        from wuwei.guards.protect_state import _cd_target
        for command in commands:
            program = Path(command.argv[0]).name
            for depth in range(1, len(command.scope) + 1):
                scope = command.scope[:depth]
                locations.setdefault(scope, set(locations[scope[:-1]]))
            directories = locations[command.scope]
            if program in ('cd', 'pushd'):
                target = _cd_target(command)
                destinations = {(base / target).resolve() for base in directories}
                # ponytail: mixed lists retain all paths because a failed cd or
                # backgrounded AND-list can leave the caller's directory intact.
                locations[command.scope] = (destinations if command.separator == '&&' and not mixed
                                            else directories | destinations)
                if len(locations[command.scope]) > 64:
                    raise ValueError('too many possible working directories; split the command')
                continue
            for directory in sorted(directories):
                parsed = None
                errors = []
                paths = [directory]
                if program == 'git':
                    parsed = git_command(command, directory, errors)
                    cwd, settings, env, verb, args = parsed
                    env = {**{key: value for key, value in os.environ.items()
                              if key.startswith('GIT_')}, **env}
                    parsed = cwd, settings, env, verb, args
                    paths = [(cwd / env[key]).resolve() for key in ('GIT_DIR', 'GIT_WORK_TREE')
                             if key in env] + [cwd]
                elif program == 'rm':
                    paths += [(directory / arg).resolve() for arg in command.argv[1:]
                              if not arg.startswith('-')]
                root = next((found[0] for path in paths
                             if (found := workspace.scope(path)) is not None), session_root)
                if root is not None:
                    scoped.append((command, directory, root, parsed, errors))
        if not scoped:
            return 0, ''
        if (found := shell.unread(raw, ('rm',), cwd=payload['cwd'])) is not None:
            return found
        if opaque_script:
            raise ValueError('opaque script command; run git as a plain command')
        # The shared parser intentionally discards these context-changing wrappers.
        if re.search(r'\benv\s+(?:-i|--ignore-environment|-u|--unset)\b|\bexec\s+-c\b', raw):
            raise ValueError('unsupported environment clearing around Git; run git with the normal environment, without clearing or unsetting variables')
        if re.search(r'''(?:^|[;\n'"])\s*\w+=[^;\n]*[;\n]''', raw):
            raise ValueError('standalone environment assignment before Git; write the assignment directly in front of the git command, or remove it')
        creates_commit, used = False, []
        for command, directory, root, parsed, errors in scoped:
            if errors:
                raise ValueError(errors[0])
            if Path(command.argv[0]).name == 'rm':
                for arg in command.argv[1:]:
                    target = (directory / arg).resolve()
                    if target.name == 'wuwei-workspace' or target == root / '.wuwei/executable':
                        return 1, 'removing a WUWEI hook pointer is refused; leave it in place, and run bin/wuwei doctor if it looks wrong'
            if Path(command.argv[0]).name != 'git':
                if (shell.is_opaque(command.argv) or len(commands) > 1
                        or '/' in command.argv[0] and not shell.known_cli(command.argv[0], directory)
                        or re.fullmatch(r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua',
                                        Path(command.argv[0]).name)):
                    raise ValueError(f'opaque interpreter command: {" ".join(command.argv)}; run git directly, for example git push origin HEAD:refs/heads/<branch>')
                continue
            cwd, settings, env, verb, args = parsed
            if verb == 'push' and creates_commit:
                item = _item(directory, root)
                checks = f'bin/wuwei build check {item}' if item else 'bin/wuwei fast-checks'
                return 1, (f'push runs after fresh fast checks: run the commit alone, then {checks}, then '
                           f'git push origin HEAD:refs/heads/{item.lower() if item else "<branch>"} '
                           'as its own command')
            creates_commit |= verb in COMMIT_VERBS
            if verb == 'config':
                args = [part for arg in args for part in arg.split('=', 1)]
                action = next((arg for arg in args if arg not in
                               ('--local', '--global', '--system', '--worktree')), '')
                protected = any(arg.lower() in ('core.hookspath', 'extensions.worktreeconfig')
                                for arg in args)
                section_change = any(arg in ('--remove-section', '--rename-section',
                                             'remove-section', 'rename-section') for arg in args)
                protected |= section_change and any(arg.lower() in ('core', 'extensions') for arg in args)
                if protected and action not in (
                        '--get', '--get-all', '--get-regexp', '--list', '-l', 'get', 'list'):
                    return 1, "changing Git hook configuration is refused; read it with git config --get; WUWEI's hooks stay as bin/wuwei worktree add set them"
                if len(commands) > 1:
                    raise ValueError('run configuration changes separately')
            overrides = settings or any(key in IDENTITY_ENV or key.startswith('GIT_CONFIG')
                                        for key in command.env)
            if verb not in COMMIT_VERBS | {'push'} and not overrides:
                if len(commands) > 1 and verb != 'add':
                    raise ValueError('unsupported compound Git command; run it as its own call, without &&, ; or pipes')
                continue
            if any(key in command.env for key in ('HOME', 'XDG_CONFIG_HOME', 'PATH')):
                raise ValueError('unsupported Git configuration or executable environment override; remove the override and run git with the normal environment')
            allowed_env = IDENTITY_ENV | REPO_ENV | {'GIT_EDITOR', 'GIT_PAGER'}
            if any(key.startswith('GIT_') and key not in allowed_env for key in env):
                raise ValueError('unsupported GIT_* override; remove it from the command')
            try:
                early, remote, refs = push_options(args) if verb == 'push' else ((1, ''), None, [])
            except ValueError:
                early = (1, '')
            repo, actual, vcs, *early = context(cwd, settings, env, root,
                                                None if early[0] else (remote, refs))
            expected = repo['identity']
            _identity(expected)
            # Explicit mismatching overrides are refused even if another override wins.
            for key, value in settings.items():
                if value != expected[key.rsplit('.', 1)[1]]:
                    return 1, 'Git configuration override differs from configured identity; remove the override; worktrees from bin/wuwei worktree add already use repos.<n>.identity'
            for key, value in env.items():
                if key in IDENTITY_ENV and not key.endswith('_DATE'):
                    if value != expected[key.rsplit('_', 1)[1].lower()]:
                        return 1, 'Git environment override differs from configured identity; unset it, or set it to the exact name and email in repos.<n>.identity'
            if verb == 'commit':
                result = commit_options(args, actual)
                if result[0]:
                    return result
            result = identity_check(expected, actual)
            if result[0]:
                return result
            if verb != 'push':
                continue
            item = _item(actual['path'], root)
            result, remote, refs = push_options(args, item.lower() if item else '<branch>')
            if result[0]:
                return result
            push = data(next(iter(early), None) or vcs.push_context(actual['path'], remote, refs, root=root))
            result = push_check(repo, actual, push, root, vcs)
            if not result[0]:
                result = fast_evidence(repo, push['head']['sha'], actual['path'], root)
                if result[0] == 1:  # #530: a warning, the owner's card or (strict) the refusal
                    from wuwei import grants
                    result = grants.evidence(payload, root, workspace.load_config(root), command.argv,
                                             result[1], repo['name'])
            if result[0]:
                return result
            if callable(result[1]):
                used.append(result[1])
        for use in used:  # #478: a grant is spent only when the whole call runs
            use()
        return 0, ''
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        reason = str(exc)
        if 'unaccounted git/gh mention' in reason:
            reason += '; run git directly, for example git push origin HEAD:refs/heads/<branch>'
        return 2, f'commit/push guard could not run: {reason}'


GUARDS = [Guard('PreToolUse', 'Bash', check)]
