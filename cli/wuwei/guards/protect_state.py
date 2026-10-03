"""Keep state writes in the CLI and persistent directory changes in the workspace."""

import os
from pathlib import Path
import re
import shlex

from wuwei.guards import Guard
from wuwei.workspace import contains_workspace, worktree_workspace


_STATE_HINT = ('State and config files are protected; use the wuwei CLI for state changes. '
               'The owner edits config.toml, voice.md and goals.md outside agent tools.')
# Pattern strings compile on first use (re's cache); most Bash calls never reach them.
_STATE_MENTION = r'(?i)state\.json|state\.snapshot\.json|events\.jsonl|traces\.jsonl|ledger\.jsonl|\.wuwei'
_STATE_GLOB = r'(?i)\.w[\w*?\[]'
_DYNAMIC = r'\$\(|[`*?\[]'
_WRITE_CONSTRUCT = (
    r'>|\b(?:tee|cp|mv|dd|truncate|ln|install|rsync|rm|patch)\b|'
    r'\bsed\s+(?:--in-place\b|-[^\s]*i)')


def _text(value, name):
    if not isinstance(value, str) or not value or '\0' in value:
        raise ValueError(f'missing or invalid {name}')
    return value


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


_OWNER_ACTIONS = {
    ('decision', 'outcome'): 'Decision outcomes require the owner terminal, outside agent tools.',
    ('drafts', 'approve'): 'Draft decisions require the owner terminal, outside agent tools.',
    ('drafts', 'drop'): 'Draft decisions require the owner terminal, outside agent tools.',
    ('mcp', 'decide'): 'MCP decisions require the owner terminal, outside agent tools.',
    ('integrity', 'reconfirm'): 'Integrity re-confirmation is an owner action on the host, outside agent tools.',
    ('state', 'recover'): 'State recovery is an owner action on the host, outside agent tools.',
    # An uninstalled watch reads as off, so a seat could silence a dead-watch page.
    ('watch', 'uninstall'): 'Watch uninstall requires the owner terminal, outside agent tools.',
    # An uninstalled listener reads as off, so a seat could silence a dead-listener report.
    ('listen', 'uninstall'): 'Listener uninstall requires the owner terminal, outside agent tools.',
    ('goals', 'edit'): 'Owner memory edits are an owner action on the host, outside agent tools.',
    ('voice', 'edit'): 'Owner memory edits are an owner action on the host, outside agent tools.',
    # An acknowledged refusal stops paging, so a seat could silence an impostor alert.
    ('remote', 'ack'): 'Remote acknowledgements require the owner terminal, outside agent tools.',
    # config.toml holds executed commands and merge eligibility; seats run wuwei promote.
    ('config', 'promote'): 'Calibration promotion is an owner action on the host, outside agent tools.',
    ('config', 'set'): 'Config edits are an owner action on the host, outside agent tools.',
    ('config', 'add-repo'): 'Config edits are an owner action on the host, outside agent tools.',
    # An empty verb is the whole group: setup's flags take values, which _pair reads as a verb.
    ('setup', ''): 'Setup writes config.toml; it is an owner action on the host, outside agent tools.',
}
_OWNER_GROUPS = {group for group, _ in _OWNER_ACTIONS}
_OWNER_VERBS = tuple(sorted({verb for _, verb in _OWNER_ACTIONS if verb}))
# Owner words as tokens; `_` or `.` may precede them so python snippets such as
# goals.owner_edit( stay relevant.
_OWNER_VERB = r'(?<![A-Za-z0-9])(?:' + '|'.join(_OWNER_VERBS) + r')(?![A-Za-z0-9])'
_OWNER_GROUP = r'(?<![A-Za-z0-9])(?:' + '|'.join(sorted(_OWNER_GROUPS)) + r')(?![A-Za-z0-9])'
_INTERPRETER = r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua'
# Any mention of the CLI word, path segments included, or a dotted owner call such as
# integrity.reconfirm(); relevance starts here.
_WUWEI = re.compile(r'\bwuwei\b|-[A-Za-z]*mwuwei\b|\b(?:'
                    + '|'.join(rf'{g}\.{v}' for g, v in _OWNER_ACTIONS if v) + r')\b')
# The CLI itself: a path segment such as cli/wuwei/x or .wuwei is a read, not the CLI.
_CLI_WORD = r'(?<![\w.-])wuwei(?![\w/.-])|-[A-Za-z]*mwuwei\b|\b(?:from|import)\s+wuwei\b'
# The CLI with a non-literal group or verb: relevant with no verb in the text.
_CLI_NONLITERAL = (r'(?<![\w.-])wuwei(?:\s+-\S*)*(?:\s+(?:' + '|'.join(sorted(_OWNER_GROUPS))
                   + r'))?(?:\s+-\S*)*\s+[$`]')
# Programs whose arguments are patterns or text, never run (except rg --pre, checked in
# _write_targets), and that write no file by operand or flag (sort -o, uniq's output
# operand and tee do, so they are not here).
_READERS = ('grep', 'rg', 'echo', 'printf', 'head', 'tail', 'wc', 'cut', 'tr')


def _pair(words):
    return tuple(([word for word in words if not word.startswith('-')] + ['', ''])[:2])


def _owner_reason(pair):
    """The owner-table reason for a (group, verb) pair, a whole-group row included."""
    return _OWNER_ACTIONS.get(pair) or _OWNER_ACTIONS.get((pair[0], ''))


def _owner_relevant(text, script=False):
    """Text only: the CLI word plus an owner group and verb, a non-literal CLI word, or xargs."""
    from wuwei.shell import mentions
    stripped = re.sub(r"['\"\\]", '', text)
    return bool(_WUWEI.search(stripped) and (
        re.search(_CLI_NONLITERAL, stripped) or mentions(text, ('xargs',), script=script)
        or (re.search(_OWNER_GROUP, stripped) or mentions(text, sorted(_OWNER_GROUPS), script=script))
        and (re.search(_OWNER_VERB, stripped) or mentions(text, _OWNER_VERBS, script=script))))


def _owner_action(commands, text, relevant, cwd, script=False):
    """One rule for every owner-only action; (code, reason) or None."""
    from wuwei.shell import _launcher, is_opaque, mentions
    # normalize unwraps xargs, so a CLI command may take its group or verb from stdin.
    xargs = relevant and mentions(text, ('xargs',), script=script)
    unseen = len(_WUWEI.findall(re.sub(r"['\"\\]", '', text)))
    readers = [bool(c.argv) and Path(c.argv[0]).name in _READERS for c in commands]
    # A pipe feeds an executor unless every later stage is a reader with no redirect.
    feeds = [False] * len(commands)
    for index in range(len(commands) - 2, -1, -1):
        feeds[index] = commands[index].separator == '|' and (
            not readers[index + 1] or bool(commands[index + 1].writes) or feeds[index + 1])
    for index, command in enumerate(commands):
        argv = command.argv
        named = len(_WUWEI.findall(' '.join([*argv, *command.env.values()])))
        # A reader's mentions are only text when it stands alone: no redirect, no group or
        # subshell (scope depth 1, or 2 for a top-level pipe stage), no pipe into an executor.
        piped = command.separator == '|' or index > 0 and commands[index - 1].separator == '|'
        if not readers[index] or (not command.writes and not feeds[index]
                                  and len(command.scope) == (2 if piped else 1)):
            unseen -= named
        action = _wuwei_action(argv)
        # A renamed or symlinked launcher is the CLI too; checked only for a literal owner pair.
        if (action is None and argv and '/' in argv[0] and _owner_reason(_pair(argv[1:]))
                and _launcher(Path(cwd, argv[0]), cwd)):
            action = argv[1:]
        if action is None:
            program = Path(argv[0]).name if argv else ''
            if not relevant or program in _READERS:
                continue
            # A directory such as the cli/wuwei package is read, not run.
            words = [word for word in argv[1:]
                     if not ('/' in word and Path(word).name == 'wuwei' and Path(cwd, word).is_dir())]
            if program == 'git':
                # A commit message or a search pattern is not a wuwei action.
                words = [word for before, word in zip([''] + words, words)
                         if not re.fullmatch(r'-[A-Za-z]*m|--message|--grep|-[SG]', before)
                         and not re.fullmatch(r'--(?:message|grep)=.*|-[A-Za-z]*m.+|-[SG].+', word, re.S)]
            # Code from stdin, a heredoc or an inline flag is unseen; a module or file operand is not.
            hidden = (is_opaque(argv) and '-m' not in argv[1:]
                      or re.fullmatch(_INTERPRETER, program) and (named or any(
                          re.fullmatch(r'-(?:[a-zA-Z]*[ceEpr]|-eval)(?:=.*)?', arg, re.S) for arg in argv[1:])))
            if hidden or re.search(_CLI_WORD, ' '.join(words)):
                return 2, 'Opaque owner action; use the host terminal.'
            continue
        group, verb = _pair(action)
        if xargs and not (re.fullmatch(r'[a-z][\w-]*', group) and (
                group not in _OWNER_GROUPS or re.fullmatch(r'[a-z][\w-]*', verb))):
            return 2, 'Input-driven owner action; use the host terminal.'
        if re.search(r'[$`]', group) or group in _OWNER_GROUPS and re.search(r'[$`]', verb):
            return 2, 'Not a literal owner action; use the host terminal.'
        if reason := _owner_reason((group, verb)):
            return 1, reason
    if relevant and unseen > 0:
        # A CLI mention sits in a heredoc, comment or other input no argv shows.
        return 2, 'Opaque owner action; use the host terminal.'
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
        if tail in (('config.toml',), ('env',), ('security.json',), ('.gitignore',), ('merge.lock',), ('executable',), ('calibration.json',)) or tail[:1] == ('generated',):
            return True
        if tail[:1] in (('integrity',), ('.git',), ('ziran',), ('inbox',)):
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
        if len(tail) == 3 and tail[0] == 'days' and tail[2] in ('state.json', 'state.snapshot.json', 'events.jsonl', 'traces.jsonl', 'undo.jsonl', 'proposal.json', 'plan.md', 'steward-decisions.json', 'interview.json', 'profile.json'):
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
    # The CLI is the state writer; its arguments (job JSON, prompts, paths it reads) are data.
    # Only the real CLI: bare wuwei on PATH, the launcher, or python -P -m wuwei (the only
    # interpreter form that reaches here naming state). Any other program named wuwei is checked.
    if _wuwei_action(argv) is not None:
        from wuwei.shell import _launcher
        if program != 'wuwei' or argv[0] == 'wuwei' or _launcher(Path(cwd, argv[0]), cwd):
            return []
    # Reader arguments are text; their redirects are checked from command.writes.
    # rg --pre runs a command on each searched file, so those operands are checked.
    if program in (*_READERS, 'cat', 'less', 'jq') and not (
            program == 'rg' and any(a == '--pre' or a.startswith('--pre=') for a in argv[1:])):
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
        from wuwei.shell import NonliteralPathError, ParseError, normalize, script_text
        from wuwei.workspace import guard_scope

        def owner_script(raw):
            # ponytail: one script level; a script run by a script, or written and run in
            # one call, is not read. The next call that runs the saved script is.
            body = script_text(raw, cwd) if root is not None else None
            # Every owner action in a script names the CLI word, so only such a body is parsed.
            if body is None or 'wuwei' not in re.sub(r"['\"\\]", '', body):
                return None
            relevant = _owner_relevant(script + '\n' + body, script=True)
            try:
                found = _owner_action(normalize(body), body, relevant, cwd, script=True)
            except ParseError:
                found = relevant and (2, 'Opaque owner script; use the host terminal.')
            return found if found and guard_scope(payload) is not None else None

        owner_relevant = _owner_relevant(script)
        words = []
        try:
            commands = normalize(script, words=words)
        except ParseError as exc:
            # The literal words, nested sh -c included, still name any script the call runs;
            # only a .sh or executable word can be one, not a source file it reads.
            for word in words:
                if ((word.endswith('.sh') or os.access(Path(cwd, word), os.X_OK))
                        and (found := owner_script(shlex.quote(word)))):
                    return found
            if ((owner_relevant and guard_scope(payload) is not None)
                    or re.search(_STATE_MENTION, script) or re.search(_STATE_GLOB, script)
                    or (root is not None and _protected_name(cwd, directories=True)
                        and (isinstance(exc, NonliteralPathError)
                             or (re.search(_DYNAMIC, script) and re.search(_WRITE_CONSTRUCT, script))))):
                return 2, str(exc)
            if contain_cwd and re.search(r'\b(?:cd|pushd|popd)\b', script, re.I):
                return 2, ('workspace guard: a top-level cd, pushd or popd to a directory that '
                           'cannot be resolved statically may leave the workspace; cd to a literal '
                           'directory inside it or use git -C')
            return 0, ''
        # normalize unwraps lists, subshells, wrappers, sh -c and xargs down to each script.
        for command in commands:
            if found := owner_script(shlex.join(command.argv)):
                return found
        found = _owner_action(commands, script, owner_relevant, cwd)
        if found and guard_scope(payload) is not None:
            return found
        directories = persistent = {cwd}
        for command in commands:
            program = Path(command.argv[0]).name if command.argv else ''
            if (re.fullmatch(r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua', program)
                    and command.argv[1:4] != ['-P', '-m', 'wuwei']
                    and re.search(_STATE_MENTION, ' '.join(command.argv[1:]))):
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
