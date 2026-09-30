"""Keep state writes in the CLI and persistent directory changes in the workspace."""

import glob
import os
from pathlib import Path
import re

from wuwei.guards import Guard
from wuwei.workspace import worktree_workspace


_STATE_HINT = ('State and config files are protected; use the wuwei CLI for state changes. '
               'The owner edits config.toml, voice.md and goals.md outside agent tools.')
_STATE_MENTION = re.compile(r'state\.json|events\.jsonl|traces\.jsonl|ledger\.jsonl|\.wuwei', re.I)
_STATE_GLOB = re.compile(r'\.w[\w*?\[]', re.I)
_DYNAMIC = re.compile(r'\$\(|[`*?\[]')
_WRITE_CONSTRUCT = re.compile(
    r'>|\b(?:tee|cp|mv|dd|truncate|ln|install|rsync|rm|patch)\b|'
    r'\bsed\s+(?:--in-place\b|-[^\s]*i)')


def _text(value, name):
    if not isinstance(value, str) or not value or '\0' in value:
        raise ValueError(f'missing or invalid {name}')
    return value


def _names_wuwei(text):
    """True when quote-stripped script text names the wuwei CLI, including python -mwuwei."""
    return bool(re.search(r'\bwuwei\b|-[A-Za-z]*mwuwei\b', text))


def _wuwei_action(argv):
    program = Path(argv[0]).name if argv else ''
    if program == 'wuwei':
        return argv[1:]
    if (re.fullmatch(r'(?:python|pypy)[\d.]*', program)
            and argv[1:4] == ['-P', '-m', 'wuwei']):
        return argv[4:]
    return None


def _input(payload, field):
    value = payload.get('tool_input')
    if not isinstance(value, dict):
        raise ValueError('missing or invalid tool_input')
    return value.get(field)


def _path(value, cwd):
    _text(value, 'path')
    if value.startswith('~'):
        raise ValueError('use a literal path instead of tilde expansion')
    return cwd / value


def _protected_name(path, directories=False):
    parts = tuple(part.casefold() for part in path.parts)
    for index, part in enumerate(parts):
        if part != '.wuwei':
            continue
        tail = parts[index + 1:]
        if tail in (('config.toml',), ('env',), ('security.json',), ('.gitignore',), ('merge.lock',)) or tail[:1] == ('generated',):
            return True
        if tail[:1] in (('integrity',), ('.git',), ('ziran',)):
            return True
        if tail in (('memory', 'voice.md'), ('memory', 'goals.md')):
            return True
        if tail and tail[0] == 'archive':
            return True
        if tail[:2] == ('memory', 'archive'):
            return True
        if tail[:2] == ('memory', 'snapshots'):
            return True
        if directories and (not tail or (len(tail) in (1, 2) and tail[0] == 'days')):
            return True
        if directories and tail in (('memory',), ('memory', 'notes'),
                                    ('memory', 'archive'), ('charters',)):
            return True
        if len(tail) == 3 and tail[0] == 'days' and tail[2] in ('state.json', 'events.jsonl', 'traces.jsonl', 'undo.jsonl', 'proposal.json', 'plan.md', 'steward-decisions.json'):
            return True
        if tail == ('memory', 'ledger.jsonl'):
            return True
        if len(tail) == 2 and tail[0] == 'charters' and tail[1].endswith('.md'):
            return True
        if len(tail) == 3 and tail[:2] == ('memory', 'notes') and tail[2].endswith('.md'):
            return True
    return False


def _protected(value, cwd, root, directories=False):
    path = _path(value, cwd).resolve()
    if _protected_name(path, directories):
        return True
    root = root or _workspace(path)
    if root is not None:
        from wuwei import security
        data = security.load(root)
        if data:
            decoy = root / '.wuwei' / data['honeytoken_path']
            if (path == decoy or directories and decoy.is_relative_to(path)
                    or path.is_file() and decoy.is_file() and os.path.samefile(path, decoy)):
                return True
    if directories and path.is_dir():
        if root is not None and root.is_relative_to(path):
            return True
        # ponytail: one level only; a recursive walk hung the hook on rm -rf /. Deeper
        # containers are caught when the session runs in the workspace or an anchored worktree.
        if (path / '.wuwei').is_dir() or _contains_workspace(path):
            return True
    # Only multiply linked files need a scan; ordinary commands pay no tree walk.
    if root is not None and path.is_file() and path.stat().st_nlink > 1:
        return any(_protected_name(candidate) and os.path.samefile(path, candidate)
                   for candidate in (root / '.wuwei').rglob('*') if candidate.is_file())
    return False


def _contains_workspace(path):
    try:
        with os.scandir(path) as entries:
            return any(entry.is_dir() and os.path.isdir(os.path.join(entry.path, '.wuwei'))
                       for entry in entries)
    except PermissionError:
        return False


def _workspace(cwd):
    # Without a discoverable root, skip loading workspace configuration.
    if 'WUWEI_WORKSPACE' not in os.environ and not any(
            (path / '.wuwei').is_dir() for path in (cwd, *cwd.parents)):
        return None
    from wuwei.workspace import find_workspace
    try:
        root = find_workspace(cwd)
    except FileNotFoundError:
        return None
    return root


def _cwd(payload):
    cwd = Path(_text(payload.get('cwd'), 'cwd'))
    if not cwd.is_absolute():
        raise ValueError('cwd must be absolute')
    return cwd.resolve()


def check_file(payload):
    try:
        cwd = _cwd(payload)
        root = _workspace(cwd) or worktree_workspace(cwd)
        field = 'notebook_path' if payload.get('tool_name') == 'NotebookEdit' else 'file_path'
        if _protected(_input(payload, field), cwd, root):
            return 1, _STATE_HINT
        return 0, ''
    except (ValueError, OSError, RuntimeError) as exc:
        return 2, str(exc)


def _copy_targets(argv, cwd):
    """Parse supported copy/move options; unknown relevant forms fail closed."""
    rsync = Path(argv[0]).name == 'rsync'
    operands, target = [], None
    index, options = 1, True
    while index < len(argv):
        arg = argv[index]
        index += 1
        if options and arg == '--':
            options = False
        elif options and not rsync and arg in ('-t', '--target-directory'):
            if index == len(argv):
                raise ValueError('missing target directory')
            target = argv[index]
            index += 1
        elif options and not rsync and arg.startswith('--target-directory='):
            target = arg.split('=', 1)[1]
        elif options and not rsync and arg.startswith('-t'):
            target = arg[2:]
        elif options and arg.startswith('-'):
            if not arg[1:] or any(flag not in 'afginoprtuvzRTLHP' for flag in arg[1:]):
                raise ValueError('unsupported copy/move option; use literal file operands')
        else:
            operands.append(arg)
    if target is None:
        if len(operands) < 2:
            raise ValueError('copy/move requires source and destination')
        target = operands.pop()
    if not operands:
        raise ValueError('copy/move requires a source')
    destination = _path(target, cwd)
    targets = [] if destination.is_dir() else [target]
    for source in operands:
        source_path = _path(source, cwd)
        if source_path.is_dir() and Path(argv[0]).name != 'mv':
            raise ValueError('directory copy/move is opaque; use explicit file operations')
        if destination.is_dir():
            targets.append(str(destination / source_path.name))
    if Path(argv[0]).name == 'mv':
        targets.extend(operands)
    return targets


def _write_targets(argv, cwd, root):
    if not argv:
        return []
    program = Path(argv[0]).name
    if program in ('cd', 'pushd', 'popd'):
        return []
    if program in ('ln', 'install', 'rsync', 'rm', 'cp', 'mv', 'tee', 'truncate', 'sed'):
        # Normalized argv has no quote metadata; conservatively check glob matches.
        argv = [argv[0], *(match for arg in argv[1:]
                          for match in (glob.glob(arg, root_dir=cwd) or [arg]))]
    arguments = {arg for arg in argv[1:] if arg}
    arguments.update(arg.split('=', 1)[1] for arg in argv[1:] if '=' in arg and arg.split('=', 1)[1])
    protected = [arg for arg in arguments
                 if _protected(arg, cwd, root, program in ('rm', 'chmod', 'chown'))]
    if program == 'rm' and protected:
        return protected
    if program in ('cp', 'mv', 'rsync'):
        if program == 'rsync' and '--remove-source-files' in argv and protected:
            return protected
        try:
            return _copy_targets(argv, cwd)
        except ValueError:
            if protected or _STATE_MENTION.search(' '.join(argv)):
                raise
            return []
    if program == 'dd':
        return [match for arg in argv[1:] if arg.startswith('of=')
                for match in (glob.glob(arg[3:], root_dir=cwd) or [arg[3:]])]
    if program in ('cat', 'head', 'tail', 'less', 'jq', 'grep', 'wc'):
        return []
    if program == 'sed' and not any(
            arg == '--in-place' or arg.startswith('--in-place=') or
            (arg.startswith('-') and not arg.startswith('--') and 'i' in arg)
            for arg in argv[1:]):
        return []
    return protected


def _cd_target(command):
    args = command.argv[1:]
    while args and args[0] in ('-L', '-P'):
        args = args[1:]
    if args and args[0] == '--':
        args = args[1:]
    elif args and args[0].startswith('-') and args[0] != '-':
        raise ValueError('unsupported cd option; use git -C or a subshell')
    if len(args) > 1:
        raise ValueError('cd requires a single literal directory')
    env = {**os.environ, **command.env}
    target = args[0] if args else _text(env.get('HOME'), 'HOME')
    if target == '~' or target.startswith('~/'):
        target = _text(env.get('HOME'), 'HOME') + target[1:]
    if target == '-':
        target = _text(env.get('OLDPWD'), 'OLDPWD')
    if env.get('CDPATH') and not Path(target).is_absolute() and not target.startswith(('./', '../')):
        raise ValueError('CDPATH directory search is opaque; use an absolute path')
    return target


def check_bash(payload):
    try:
        cwd = _cwd(payload)
        root = _workspace(cwd) or worktree_workspace(cwd)
        contain_cwd = root is not None and cwd.is_relative_to(root)
        script = _input(payload, 'command')
        if not isinstance(script, str):
            raise ValueError('missing or invalid command')
        from wuwei.shell import mentions
        owner_action_text = re.sub(r"['\"\\]", '', script)
        owner_outcome_relevant = (root is not None and _names_wuwei(owner_action_text)
                                  and re.search(r'\bdecision\b', owner_action_text)
                                  and re.search(r'\boutcome\b', owner_action_text))
        owner_edit_relevant = (root is not None
                               and re.search(r'(?i)wuwei|goals|voice|edit', script)
                               and mentions(script, ('wuwei',))
                               and mentions(script, ('goals', 'voice'))
                               and (mentions(script, ('edit',)) or 'owner_edit' in script))
        if (mentions(script, ('integrity',))
                and 'reconfirm' in re.sub(r"['\"\\]", '', script)):
            from wuwei.workspace import guard_scope
            if guard_scope(payload) is not None:
                return 1, 'Integrity re-confirmation is an owner action on the host, outside agent tools.'
        from wuwei.workspace import guard_scope
        mcp_relevant = (_names_wuwei(owner_action_text)
                        and mentions(script, ('mcp',)) and guard_scope(payload) is not None)
        drafts_relevant = ((re.search(r'(?i)wuwei|drafts', re.sub(r"['\"\\]", '', script))
                            or "$'" in script)
                           and _names_wuwei(owner_action_text)
                           and mentions(script, ('drafts',))
                           and guard_scope(payload) is not None)
        # An uninstalled watch reads as off, so a seat could silence a dead-watch page.
        watch_relevant = (_names_wuwei(owner_action_text) and mentions(script, ('uninstall',))
                          and guard_scope(payload) is not None)
        from wuwei.shell import NonliteralPathError, ParseError, normalize
        try:
            commands = normalize(script)
        except ParseError as exc:
            if (owner_edit_relevant or owner_outcome_relevant or mcp_relevant or drafts_relevant
                    or watch_relevant
                    or _STATE_MENTION.search(script) or _STATE_GLOB.search(script)
                    or (root is not None and _protected_name(cwd, directories=True)
                        and (isinstance(exc, NonliteralPathError)
                             or (_DYNAMIC.search(script) and _WRITE_CONSTRUCT.search(script))))
                    or (contain_cwd and re.search(r'\b(?:cd|pushd|popd)\b', script, re.I))):
                return 2, str(exc)
            return 0, ''
        if owner_outcome_relevant:
            for command in commands:
                action = _wuwei_action(command.argv)
                if action is None:
                    return 2, 'Opaque owner decision action; use the host terminal.'
                if action[:1] == ['decision'] and any('$' in arg or '`' in arg for arg in action[1:2]):
                    return 2, 'Decision action is not a literal list; use the host terminal.'
                if action[:2] == ['decision', 'outcome']:
                    return 1, 'Decision outcomes require the owner terminal, outside agent tools.'
            if not commands:
                return 2, 'Opaque owner decision action; use the host terminal.'
        if owner_edit_relevant:
            from wuwei.shell import is_opaque
            for command in commands:
                argv = command.argv
                program = Path(argv[0]).name if argv else ''
                action = _wuwei_action(argv)
                if action is None:
                    if (is_opaque(argv) or
                            re.fullmatch(r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua', program)
                            and any(re.fullmatch(r'-(?:[a-zA-Z]*[ceEr]|-eval)(?:=.*)?', arg)
                                    for arg in argv[1:])):
                        return 2, 'Opaque owner edit; use the wuwei CLI.'
                    continue
                if action[:2] in (['goals', 'edit'], ['voice', 'edit']):
                    if guard_scope(payload) is not None:
                        return 1, 'Owner memory edits are an owner action on the host, outside agent tools.'
        if mcp_relevant or drafts_relevant or watch_relevant:
            from wuwei.shell import is_opaque
            for command in commands:
                argv = command.argv
                cli = argv and (Path(argv[0]).name == 'wuwei'
                        or re.fullmatch(r'(?:python|pypy)[\d.]*', Path(argv[0]).name)
                        and (any(re.fullmatch(r'-[A-Za-z]*mwuwei', arg) for arg in argv) or
                             '-m' in argv and argv[argv.index('-m') + 1:][:1] == ['wuwei']))
                if not cli and (is_opaque(argv) or argv and re.fullmatch(
                        r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua', Path(argv[0]).name)):
                    return 2, 'Opaque owner action; use the host terminal.'
                if cli:
                    if watch_relevant and 'watch' in argv:
                        action = argv[argv.index('watch') + 1:][:1]
                        if action == ['uninstall']:
                            return 1, 'Watch uninstall requires the owner terminal, outside agent tools.'
                        if any('$' in arg or '`' in arg for arg in action):
                            return 2, 'Watch action is not literal; use the host terminal.'
                    if drafts_relevant and 'drafts' in argv:
                        action = argv[argv.index('drafts') + 1:]
                        if action[:1] in (['approve'], ['drop']):
                            return 1, 'Draft decisions require the owner terminal, outside agent tools.'
                        if action and action != ['--help']:
                            return 2, 'Draft action is not a literal list; use the host terminal.'
                    if 'mcp' in argv:
                        action = argv[argv.index('mcp') + 1:]
                        if action == ['decide']:
                            return 1, 'MCP decisions require the owner terminal, outside agent tools.'
                        if action != ['check']:
                            return 2, 'MCP owner action is not a literal check; use the host terminal.'
        directories = persistent = {cwd}
        for command in commands:
            program = Path(command.argv[0]).name if command.argv else ''
            if (re.fullmatch(r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua', program)
                    and command.argv[1:4] != ['-P', '-m', 'wuwei']
                    and _STATE_MENTION.search(' '.join(command.argv[1:]))):
                return 2, 'Opaque interpreter; use the wuwei CLI for state changes.'
            for directory in directories:
                if program == 'git' and 'apply' in command.argv[1:]:
                    git_directory = directory
                    options = iter(command.argv[1:])
                    for option in options:
                        if option in ('-c', '--git-dir', '--work-tree', '--namespace', '--config-env'):
                            next(options, '')
                        elif option.startswith('-C'):
                            target = next(options, None) if option == '-C' else option[2:]
                            git_directory = _path('.' if target == '' else target, git_directory).resolve()
                        elif not option.startswith('-'):
                            if option == 'apply' and any((base / '.wuwei').is_dir()
                                    for base in (git_directory, *git_directory.parents)):
                                return 1, _STATE_HINT
                            break
                targets = [*command.writes, *_write_targets(command.argv, directory, root)]
                if any(_protected(target, directory, root, program in ('rm', 'mv', 'chmod', 'chown'))
                       for target in targets):
                    return 1, _STATE_HINT
            if program == 'popd' or (program == 'pushd' and (len(command.argv) == 1 or
                    re.fullmatch(r'[+-][0-9]+', command.argv[1]))):
                if contain_cwd and not command.subshell:
                    return 2, 'Unknown directory stack; use git -C or a subshell instead of top-level pushd/popd.'
                continue
            if program in ('cd', 'pushd'):
                target = _cd_target(command)
                bases = directories if command.subshell else persistent
                destinations = {_path(target, base).resolve() for base in bases}
                if not command.subshell:
                    if contain_cwd and any(not path.is_relative_to(root) for path in destinations):
                        return 1, 'Keep the workspace root; use git -C or a subshell instead of top-level cd/pushd.'
                    persistent = persistent | destinations
                # ponytail: flattened commands omit branch and nested-scope identity.
                # Retain possible paths; add scope metadata if false positives matter.
                directories = directories | destinations
                if len(directories) > 64:
                    raise ValueError('too many possible working directories; split the command')
        return 0, ''
    except (ValueError, OSError, RuntimeError) as exc:
        return 2, str(exc)


GUARDS = [Guard('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', check_file),
          Guard('PreToolUse', 'Bash', check_bash)]
