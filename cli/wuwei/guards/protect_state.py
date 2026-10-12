"""Keep state writes in the CLI and persistent directory changes in the workspace."""

from itertools import chain
import os
from pathlib import Path
import re

from wuwei.guards import Guard
from wuwei.shell import WORKSPACE_ROOT, _cd_target, _cwd, _text
from wuwei.workspace import contains_workspace, worktree_workspace
from wuwei.exits import DAMAGED, PAYLOAD


_STATE_HINT = ('State and config files are protected; use the wuwei CLI for state changes; '
               'owner edits run outside agent tools.')
# Pattern strings compile on first use (re's cache); most Bash calls never reach them.
# #647: a seat's own scratch scripts are not state, unless the path climbs out with ..
_SCRATCH = r'[\\/]scratch[\\/](?![^\s\x27"]*\.\.)'
_STATE_MENTION = (r'(?i)state\.json|events\.jsonl|traces\.jsonl|ledger\.jsonl|'
                  rf'\.wuwei(?!{_SCRATCH})')
_STATE_GLOB = rf'(?i)\.w(?!uwei{_SCRATCH})[\w*?\[]'
_WRITE_CONSTRUCT = (r'>|\b(?:tee|cp|mv|dd|truncate|ln|install|rsync|rm|patch)\b|'
                    r'\bsed\s+(?:--in-place\b|-[^\s]*i)')


def _wuwei_action(argv):
    program = Path(argv[0]).name if argv else ''
    if program == 'wuwei':
        return argv[1:]
    if re.fullmatch(r'(?:python|pypy)[\d.]*', program):
        for index, arg in enumerate(argv[1:], 1):
            if arg == '-m' and argv[index + 1:index + 2] == ['wuwei']:
                return argv[index + 2:]
            if re.fullmatch(r'-[A-Za-z]*mwuwei', arg):
                return argv[index + 1:]
            if not arg.startswith('-') or arg in ('-c', '-m'):
                break
    return None


_INTERPRETER = r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua'
# Programs whose arguments are patterns or text, never run (except rg --pre, checked in
# _write_targets), and that write no file by operand or flag (sort -o, uniq's output
# operand and tee do, so they are not here). #471: shell.reads adds the classifier's
# read-only words (cat, jq, sed -n Np, find without an action).
_READERS = ('grep', 'rg', 'echo', 'printf', 'head', 'tail', 'wc', 'cut', 'tr')


def _input(payload, field):
    value = payload.get('tool_input')
    if not isinstance(value, dict):
        raise ValueError(f'missing or invalid tool_input; {PAYLOAD}')
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
        if tail in (('config.toml',), ('env',), ('security.json',), ('.gitignore',), ('merge.lock',), ('executable',), ('calibration.json',)) or tail[:1] == ('generated',):
            return True
        if tail[:1] in (('integrity',), ('.git',), ('metrics',)):
            return True
        if tail == ('memory', 'goals.md'):
            return True
        if tail and tail[0] == 'archive':
            return True
        if tail[:2] == ('memory', 'archive'):
            return True
        if directories and (not tail or (len(tail) in (1, 2) and tail[0] == 'days')):
            return True
        if directories and tail in (('memory',), ('memory', 'notes'), ('memory', 'archive'), ('charters',)):
            return True
        if len(tail) == 3 and tail[0] == 'days' and tail[2] in ('state.json', 'events.jsonl', 'traces.jsonl', 'proposal.json', 'plan.md', 'goals.md'):
            return True
        if tail == ('memory', 'ledger.jsonl'):
            return True
        if len(tail) == 2 and tail[0] == 'charters' and tail[1].endswith('.md'):
            return True
        if len(tail) == 3 and tail[:2] == ('memory', 'notes') and tail[2].endswith('.md'):
            return True
    return False


def _hint(path):
    """#349: the one-line reason for a refused write names the command that makes it."""
    parts = tuple(part.casefold() for part in path.parts)
    tail = parts[len(parts) - parts[::-1].index('.wuwei'):] if '.wuwei' in parts else ()
    if tail == ('config.toml',):
        return ('config.toml is protected: run wuwei config set <key> <value>; it asks the owner '
                'on its Owner step card.')
    if tail[:1] == ('days',) and tail[-1:] in (('state.json',), ('events.jsonl',)):
        return ("Day records are protected: the workflow's wuwei CLI commands write them; run wuwei next "
                'for the step.')
    if tail == ('memory', 'goals.md'):
        return ("goals.md is protected: a goals change goes through the plan's goals block: the lead "
                'proposes the new blocks and plan approve records the goals the morning gate approved.')
    if tail[:1] == ('integrity',):
        return ('Integrity records are protected: run wuwei doctor --fix --apply integrity-reconfirm; it asks the owner '
                'on its Owner step card.')
    return _STATE_HINT


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
        if (path / '.wuwei').is_dir() or contains_workspace(path):
            return True
    # Only multiply linked files need a scan; ordinary commands pay no tree walk.
    if root is not None and path.is_file() and path.stat().st_nlink > 1:
        return any(_protected_name(candidate) and os.path.samefile(path, candidate)
                   for candidate in (root / '.wuwei').rglob('*') if candidate.is_file())
    return False


def _workspace(cwd):
    # Without a discoverable root, skip loading workspace configuration.
    if 'WUWEI_WORKSPACE' not in os.environ and not any(
            (path / '.wuwei').is_dir() for path in chain((cwd,), cwd.parents)):
        return None
    from wuwei.workspace import find_workspace
    try:
        root = find_workspace(cwd)
    except FileNotFoundError:
        return None
    return root


def check_file(payload):
    try:
        cwd = _cwd(payload)
        root = _workspace(cwd) or worktree_workspace(cwd)
        field = 'notebook_path' if payload.get('tool_name') == 'NotebookEdit' else 'file_path'
        value = _input(payload, field)
        if _protected(value, cwd, root):
            return 1, _hint(_path(value, cwd).resolve())
        return 0, ''
    except (ValueError, OSError, RuntimeError) as exc:
        return 2, str(exc)



def check_scratch(payload):
    """#647: a seat's Write into another item's scratch directory; the hook logs it (#837)."""
    try:
        if 'agent_id' not in payload:
            return 0, ''
        cwd = _cwd(payload)
        field = 'notebook_path' if payload.get('tool_name') == 'NotebookEdit' else 'file_path'
        parts = _path(_input(payload, field), cwd).resolve().parts
        found = next(((Path(*parts[:index + 1]), parts[index + 1]) for index in range(1, len(parts) - 2)
                      if parts[index] == 'scratchpad'
                      or parts[index] == 'scratch' and parts[index - 1] == '.wuwei'), None)
        if found is None:
            return 0, ''
        root = _workspace(cwd) or worktree_workspace(cwd)
        if root is None:
            return 0, ''
        from wuwei import brief, state, workspace
        data = state.read_state(root)
        seat = brief.seat_of(payload, data)
        base, other = found
        if seat is None or other == seat['item'] or other not in data['items']:
            return 0, ''
        reason = (f"scratch: {Path(*parts)} is in item {other}'s scratch directory; write item "
                  f"{seat['item']}'s temporary files in {base / seat['item'] / seat['role']}/")
        return 1, reason
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
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
                raise ValueError('missing target directory; pass the target directory')
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
            raise ValueError('copy/move requires source and destination; pass the source and the destination')
        target = operands.pop()
    if not operands:
        raise ValueError('copy/move requires a source; pass the source and the destination')
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
    # The CLI is the state writer; its arguments (job JSON, prompts, paths it reads) are data.
    # Only the real CLI: bare wuwei on PATH, the launcher, or python -P -m wuwei (the only
    # interpreter form that reaches here naming state). Any other program named wuwei is checked.
    if _wuwei_action(argv) is not None:
        from wuwei.shell import _launcher
        if program != 'wuwei' or argv[0] == 'wuwei' or _launcher(Path(cwd, argv[0]), cwd):
            return []
    from wuwei.shell import reads
    # Reader arguments are text; their redirects are checked from command.writes.
    # rg --pre runs a command on each searched file, so those operands are checked.
    if program in _READERS and not (
            program == 'rg' and any(a == '--pre' or a.startswith('--pre=') for a in argv[1:])) or reads(argv):
        return []
    if program in ('ln', 'install', 'rsync', 'rm', 'cp', 'mv', 'tee', 'truncate', 'sed'):
        # Normalized argv has no quote metadata; conservatively check glob matches.
        import glob  # Here, not at module level: most Bash calls never glob.
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
            if protected or re.search(_STATE_MENTION, ' '.join(argv)):
                raise
            return []
    if program == 'dd':
        import glob
        return [match for arg in argv[1:] if arg.startswith('of=')
                for match in (glob.glob(arg[3:], root_dir=cwd) or [arg[3:]])]
    if program == 'sed' and not any(
            arg == '--in-place' or arg.startswith('--in-place=') or
            (arg.startswith('-') and not arg.startswith('--') and 'i' in arg)
            for arg in argv[1:]):
        return []
    return protected


def check_bash(payload):
    try:
        cwd = _cwd(payload)
        root = _workspace(cwd) or worktree_workspace(cwd)
        contain_cwd = root is not None and cwd.is_relative_to(root)
        script = _input(payload, 'command')
        if not isinstance(script, str):
            raise ValueError(f'missing or invalid command; {DAMAGED}')
        from wuwei.shell import ParseError, UNPARSED, normalize, reads, snippet_write

        try:
            commands = normalize(script)
        except ParseError:
            # #839: a call the parser cannot read is logged, never refused.
            if contain_cwd and re.search(r'\b(?:cd|pushd|popd)\b', script, re.I):
                return 2, WORKSPACE_ROOT
            # Review F7: or a write construct while cwd is a protected directory.
            if (re.search(_STATE_MENTION, script) or re.search(_STATE_GLOB, script)
                    or root is not None and _protected_name(cwd, directories=True)
                    and re.search(_WRITE_CONSTRUCT, re.sub(r'\d*>\s*/dev/null', '', script))):
                return 2, UNPARSED
            return 0, ''
        directories = persistent = {cwd}
        for command in commands:
            program = Path(command.argv[0]).name if command.argv else ''
            if root is not None and (_wuwei_action(command.argv) or [''])[0] == 'hook':  # #831
                return 2, ('wuwei hook runs only from Claude Code hooks, never from a tool call; '
                           'run the command the hook guards instead')
            # #349: a script run with no state operand passes; -m json.tool with one file reads.
            # #643: so does a python -c snippet with no write-like token; a refusal names it.
            if (re.fullmatch(_INTERPRETER, program)
                    and command.argv[1:4] != ['-P', '-m', 'wuwei']
                    and not reads(command.argv)
                    and re.search(_STATE_MENTION, ' '.join(command.argv[1:]))):
                token = snippet_write(command.argv)
                return 2, (f'Opaque interpreter: {token} in the snippet is not a read; use the wuwei '
                           'CLI for state changes.' if token else
                           'Opaque interpreter; use the wuwei CLI for state changes.')
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
                hit = next((target for target in targets if _protected(
                    target, directory, root, program in ('rm', 'mv', 'chmod', 'chown'))), None)
                if hit is not None:
                    return 1, _hint(_path(hit, directory).resolve())
            if program == 'popd' or (program == 'pushd' and (len(command.argv) == 1 or
                    re.fullmatch(r'[+-][0-9]+', command.argv[1]))):
                if contain_cwd and not command.subshell:
                    return 2, WORKSPACE_ROOT
                continue
            if program in ('cd', 'pushd'):
                try:
                    target = _cd_target(command)
                except ValueError:
                    return 2, WORKSPACE_ROOT
                bases = directories if command.subshell else persistent
                destinations = {_path(target, base).resolve() for base in bases}
                if not command.subshell:
                    if contain_cwd and any(not path.is_relative_to(root) for path in destinations):
                        return 1, WORKSPACE_ROOT
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
          Guard('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', check_scratch),
          Guard('PreToolUse', 'Bash', check_bash)]
