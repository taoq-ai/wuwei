"""Static shell normalization for guards. Never execute or expand input text."""

from collections import namedtuple
from itertools import count
from pathlib import Path, PurePosixPath
import re
import os
import shlex

from wuwei.exits import DAMAGED, PAYLOAD


class ParseError(ValueError):
    """The command cannot be inspected safely; guards must return exit 2."""


class NonliteralPathError(ParseError):
    """A file or directory operand cannot be resolved statically."""


# argv: list[str], subshell: bool, env: dict[str, str], writes and reads: tuple[str, ...],
# scope: tuple[int, ...], separator: str. collections.namedtuple: typing costs every hook 1 ms.
Command = namedtuple('Command', 'argv subshell env writes reads scope separator',
                     defaults=((), (), (), ''))


def operands(args, valued=(), flags=()):
    """Read normalized argv; repeated options and gh method/repo aliases use the last value."""
    result, values = [], {}
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == '--':
            result.extend(args[index:])
            break
        if not arg.startswith('-'):
            result.append(arg)
            continue
        key, sep, value = arg.partition('=')
        if key in flags and (not sep or value in ('true', 'false')):
            values[key] = value if sep else 'true'
            continue
        if key not in valued:
            # Short value options also accept attached values, e.g. -Rorg/repo.
            key = next((k for k in valued if len(k) == 2 and arg.startswith(k)), '')
            if not key:
                raise ValueError('unsupported option; use explicit targets')
            value, sep = arg[len(key):], '='
        if not sep:
            if index == len(args):
                raise ValueError('missing option value; add the value after it (for example -R owner/repo) or remove the option')
            value = args[index]
            index += 1
        for aliases in (('-X', '--method'), ('-R', '--repo')):
            if key in aliases:
                for alias in aliases:
                    values.pop(alias, None)
        values[key] = value
    return result, values


# Words retain quote boundaries so expansion checks distinguish literal data.
_TOKEN = re.compile(r'(?P<space>[ \t\r]+)|(?P<comment>\#[^\n]*)|'
                    r'(?P<redirect>[0-9]*(?:<<-?|>>!?|>!|<>|>&|<&|>\||[<>])|&>>?)|'
                    r'(?P<operator>\&\&|\|\||[;&|()\n])')
_ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z_0-9]*=')
# #730: a whole word that is one plain variable (the _variable_read form).
_VARIABLE = re.compile(r'"?\$\{?([A-Za-z_]\w*)\}?"?')
# #730: builtins that can set a variable named by any word, and the . and source loaders.
_WRITERS = re.compile(r'(?<![\w./-])(?:read|printf|mapfile|readarray|declare|typeset|local|export|readonly|'
                      r'unset|getopts|eval|source|let|wait|\.)(?![\w./-])')


def leading_variables(text):
    """#730: {name: value} of a leading assignment statement (x=bin/wuwei; ...) whose values are
    single literal words; a name written anywhere else as a bare word (x=, x+=, read x, getopts g
    x, unset x) is left out, only its $x and ${x} reads may follow. The first statement always
    runs, in the outer shell, before every later stage. Any variable-writing builtin word makes
    every name opaque: its name operand can be built by expansion (read ${n%?})."""
    text = re.sub(r'''['"\\]''', '', text)
    if _WRITERS.search(text):
        return {}
    match = re.match(r'\s*((?:[A-Za-z_]\w*=[\w./][\w./:@+-]*[ \t]+)*[A-Za-z_]\w*=[\w./][\w./:@+-]*)'
                     r'[ \t]*(?:;|&&|\n)', text)
    pairs = dict(word.split('=', 1) for word in match[1].split()) if match else {}
    return {key: value for key, value in pairs.items()
            if len(re.findall(rf'(?<![\w$])(?<!\$\{{){key}(?!\w)', text)) == 1}
PLUGIN_LAUNCHER = Path(__file__).resolve().parents[2] / 'bin/wuwei'  # resolved once, as registry.ADAPTERS
_PATH_COMMANDS = ('cd', 'pushd', 'popd', 'tee', 'cp', 'mv', 'sed', 'dd', 'truncate')

# #508: a whole word, never a directory component (a '/' later in the same path segment),
# so a path such as 508-git-in/bin/wuwei or ~/git/x is no mention.
_GUARDED = re.compile(r'(?<![.\w])(?:git|gh)\b(?![\w.-]*/)')
_QUOTED_PART = re.compile(r''' '[^']*'|"(?:\\[\s\S]|[^"\\])*"|\\[\s\S]|[^'"\\]+ ''', re.VERBOSE)


def _expands(raw):
    return any('$' in re.sub(r'\\[\s\S]', '', part[0])
               for part in _QUOTED_PART.finditer(raw)
               if not part[0].startswith(("'", '\\')))


def _reject_mentions(text):
    if _GUARDED.search(text) or _GUARDED.search(re.sub(r'''['"\\]''', '', text)):
        raise ParseError('unaccounted git/gh mention; remove the mention, or run git or gh as its own plain command')


def _launcher(path, cwd):
    """The plugin's own bin/wuwei or the workspace's recorded executable."""
    from wuwei import workspace
    path = path.resolve()
    if path == PLUGIN_LAUNCHER:
        return True
    try:
        try:
            root = workspace.find_workspace(cwd)
        except FileNotFoundError:
            root = workspace.worktree_workspace(Path(cwd).resolve())
        if root is None:
            return False
        recorded = (root / '.wuwei/executable').read_text(encoding='utf-8').splitlines()
        return bool(recorded and recorded[0]) and path == Path(recorded[0]).resolve()
    except (OSError, ValueError, RuntimeError):
        return False


def _text(value, name):
    if not isinstance(value, str) or not value or '\0' in value:
        raise ValueError(f'missing or invalid {name}; {PAYLOAD}')
    return value


def _cwd(payload):
    cwd = Path(_text(payload.get('cwd'), 'cwd'))
    if not cwd.is_absolute():
        raise ValueError(f'cwd must be absolute; {PAYLOAD}')
    return cwd.resolve()


def _cd_target(command):
    args = command.argv[1:]
    while args and args[0] in ('-L', '-P'):
        args = args[1:]
    if args and args[0] == '--':
        args = args[1:]
    elif args and args[0].startswith('-') and args[0] != '-':
        raise ValueError('unsupported cd option; use git -C or a subshell')
    if len(args) > 1:
        raise ValueError('cd requires a single literal directory; pass one literal directory to cd')
    env = {**os.environ, **command.env}
    target = args[0] if args else _text(env.get('HOME'), 'HOME')
    if target == '~' or target.startswith('~/'):
        target = _text(env.get('HOME'), 'HOME') + target[1:]
    if target == '-':
        target = _text(env.get('OLDPWD'), 'OLDPWD')
    if env.get('CDPATH') and not Path(target).is_absolute() and not target.startswith(('./', '../')):
        raise ValueError('CDPATH directory search is opaque; use an absolute path')
    return target


def known_cli(word, cwd):
    """#348: wuwei on PATH, the running plugin's bin/wuwei or the recorded executable."""
    return word == 'wuwei' or (cwd is not None and '/' in word
                               and PurePosixPath(word).name == 'wuwei'
                               and _launcher(Path(cwd, word), cwd))


def _literal(raw, allow_globs=False):
    return not _expands(raw) and not any(
        re.search((r'`' if allow_globs else r'[`*?\[]') + r'|\{[^{}]*(,|\.\.)[^{}]*\}', part[0])
        for part in _QUOTED_PART.finditer(raw)
        if not part[0].startswith(("'", '"', '\\')))


def _word(raw):
    parts = list(_QUOTED_PART.finditer(raw))
    for first, second in zip(parts, parts[1:]):
        if not first[0].startswith(("'", '"', '\\')) and first[0].endswith('$') and second[0].startswith("'"):
            raise ParseError('ANSI-C quoting is unsupported; use plain \'single\' or "double" quotes instead of $\'...\'')
    return ''.join(shlex.split(part[0])[0].replace('\\$', '$')
                   if part[0].startswith('"') else shlex.split(part[0])[0]
                   for part in parts)


def normalize(command: str, *, protected=(), words=None) -> list[Command]:
    """Return argv lists with subshell scope, or raise ParseError.

    Extra protected executable names receive literal argument checks only.
    If supplied, words collects literal tokens even when parsing fails, allowing
    callers to establish target scope without reparsing rejected shell text.

    ponytail: this is a conservative simple-command parser, not a shell evaluator.
    Reject dynamic substitutions, control flow and unknown wrapper options; extend
    the supported grammar with bypass tests when a guard needs those constructs.
    """
    protected, texts = ('git', 'gh', *protected), []
    try:
        found = _parse(command, False, protected=protected,
                       words=[] if words is None else words, texts=texts, scope_ids=count(),
                       variables=leading_variables(command))
        # #671: a reader's text is data only when no command of the call can run it,
        # and no write lands in git's own files (hooks, config).
        if texts and any(item.argv and PurePosixPath(item.argv[0]).name not in protected
                         and not reads(item.argv)
                         or any('.git' in (part.casefold() for part in PurePosixPath(target).parts)
                                for target in item.writes)  # case-insensitive filesystems
                         for item in found):
            for text in texts:
                _reject_mentions(text)
        return found
    except (ValueError, RecursionError) as exc:
        error = type(exc) if isinstance(exc, ParseError) else ParseError
        raise error((str(exc) or 'shell nesting too deep') +
                    '; run git or gh as a plain command') from exc


def _heredoc(script, position, delimiter, strip_tabs=False):
    ending = re.compile(r'^' + (r'\t*' if strip_tabs else '') +
                        re.escape(delimiter) + r'(?:\n|$)', re.MULTILINE)
    match = ending.search(script, position)
    if not match:
        raise ParseError('unterminated here-doc; write the delimiter alone on its own line after the body')
    body = script[position:match.start()]
    if strip_tabs:
        body = re.sub(r'^\t+', '', body, flags=re.MULTILINE)
    return body, match.end()


def _read_word(script, position):
    raw, quote = [], None
    while position < len(script):
        char = script[position]
        if quote is None and (char.isspace() or char in ';&|()<>'):
            break
        if char == '\\' and quote != "'":
            if position + 1 == len(script):
                raise ParseError('trailing backslash; remove the backslash or finish the line')
            raw.append(script[position:position + 2])
            position += 2
            continue
        if quote != "'" and script.startswith('$(', position):
            # Only a quoted literal cat here-doc has a statically known result.
            header = re.match(r"""\$\(cat[ \t]+<<(-?)[ \t]*(['"])([\w-]+)\2[ \t]*\n""",
                              script[position:])
            if quote != '"' or not header:
                raise ParseError('command substitution is unsupported; run that command first and write its result as a literal, or use a quoted cat here-doc ($(cat <<\'EOF\' ... EOF))')
            body, position = _heredoc(script, position + header.end(), header[3], bool(header[1]))
            end = re.match(r'\s*\)', script[position:])
            if not end:
                raise ParseError('command substitution contains more than a literal here-doc; close the $( right after the here-doc delimiter line, or pass the text with --body-file')
            position += end.end()
            raw.append('"' + shlex.quote(body.rstrip('\n')) + '"')
            continue
        if char == '`' and quote != "'":
            raise ParseError('command substitution is unsupported; run that command first and write its result as a literal, or use a quoted cat here-doc ($(cat <<\'EOF\' ... EOF))')
        if char in ("'", '"'):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        raw.append(char)
        position += 1
    if quote or not raw:
        raise ParseError('unbalanced quotes or missing word; close the quote or add the missing word so the guard can read the command')
    return ''.join(raw), position


def _parse(script, subshell, env=None, protected=('git', 'gh'), *, words, texts, scope=(), scope_ids,
           variables=None):
    if not isinstance(script, str) or '\0' in script:
        raise ParseError(f'command must be text without NUL; {DAMAGED}')
    tokens, raw_tokens, heredocs = [], [], []
    writes_at, reads_at = {}, {}
    command_start = 0
    position = 0
    while position < len(script):
        match = _TOKEN.match(script, position)
        if match:
            position = match.end()
            kind, raw = match.lastgroup, match[0]
            if kind in ('space', 'comment'):
                _reject_mentions(raw)
                continue
            if kind == 'redirect':
                while position < len(script) and script[position] in ' \t':
                    position += 1
                start = position
                target, position = _read_word(script, position)
                if '<<' in raw:
                    if not re.fullmatch(r"""(['"])[\w-]+\1""", target):
                        raise ParseError('only quoted here-doc delimiters are supported; write <<\'EOF\' instead of <<EOF so the body stays literal')
                    heredocs.append((_word(target), raw.endswith('-'), command_start))
                elif not _literal(target):
                    raise NonliteralPathError('nonliteral redirection is unsupported; use a literal path')
                elif '>' in raw and not ('&' in raw and re.fullmatch(r'[0-9]+-?|-', _word(target))):
                    writes_at[len(tokens)] = _word(target)
                    tokens.append(('', False))
                    raw_tokens.append('')
                elif '<' in raw and not ('&' in raw and re.fullmatch(r'[0-9]+-?|-', _word(target))):
                    reads_at[len(tokens)] = _word(target)
                    tokens.append(('', False))
                    raw_tokens.append('')
                _reject_mentions(script[start:position])
                continue
            if raw == '\n':
                for delimiter, strip_tabs, owner_start in heredocs:
                    body, position = _heredoc(script, position, delimiter, strip_tabs)
                    owner = tokens[owner_start] if owner_start < len(tokens) else ('', True)
                    if owner[1] or PurePosixPath(owner[0]).name not in ('git', 'gh'):
                        texts.append(body)
                heredocs.clear()
            operator = True
        else:
            start = position
            raw, position = _read_word(script, position)
            operator = False
        # Comments are already consumed, so their backslashes cannot join lines.
        for part in _QUOTED_PART.finditer(raw):
            if not part[0].startswith("'") and '\\\n' in part[0]:
                _reject_mentions(part[0])
        raw = _QUOTED_PART.sub(
            lambda m: m[0] if m[0].startswith("'") else m[0].replace('\\\n', ''), raw)
        if not operator and len(_GUARDED.findall(script[start:position])) > len(_GUARDED.findall(raw)):
            raise ParseError('normalization hides a git/gh mention; write git or gh as one plain unbroken word')
        if not raw:
            continue
        tokens.append((raw if operator else _word(raw), operator))
        raw_tokens.append(raw)
        if not operator and _literal(raw):
            words.append(_word(raw))
        if operator:
            command_start = len(tokens)
    if heredocs:
        raise ParseError('missing here-doc body; add the body and the delimiter line, or drop the here-doc')

    position = 0

    def group(nested, parent_scope):
        nonlocal position
        current_scope = (*parent_scope, next(scope_ids))
        commands = []
        pending = None
        while position < len(tokens):
            token, operator = tokens[position]
            if operator and token == ')':
                break
            if operator and token == '\n':
                position += 1
                continue
            if operator and token != '(':
                raise ParseError('unexpected shell separator; remove the empty slot or split the line into separate commands')
            if operator:
                position += 1
                current = group(True, current_scope)
                if position == len(tokens) or tokens[position] != (')', True) or not current:
                    raise ParseError('unbalanced or empty subshell; add the missing parenthesis and a command inside, or remove the parentheses')
                position += 1
            else:
                argv = []
                raw_argv, writes, reads = [], [], []
                while position < len(tokens) and not tokens[position][1]:
                    if position in writes_at:
                        writes.append(writes_at[position])
                    elif position in reads_at:
                        reads.append(reads_at[position])
                    else:
                        argv.append(tokens[position][0])
                        raw_argv.append(raw_tokens[position])
                    position += 1
                current = _unwrap(argv, nested, raw_argv, env, protected,
                                  words=words, texts=texts, scope=current_scope, scope_ids=scope_ids,
                                  variables=variables)
                if writes or reads:
                    if not current:
                        current = [Command([], nested, dict(env or {}))]
                    current[0] = current[0]._replace(writes=tuple(writes) + current[0].writes,
                                                   reads=tuple(reads) + current[0].reads)
            while position in writes_at:
                current[0] = current[0]._replace(writes=current[0].writes + (writes_at[position],))
                position += 1
            while position in reads_at:
                current[0] = current[0]._replace(reads=current[0].reads + (reads_at[position],))
                position += 1
            next_token = tokens[position] if position < len(tokens) else None
            if next_token in (('|', True), ('&', True)) or pending == '|':
                detached = (*current_scope, next(scope_ids))
                current = [item._replace(subshell=item.subshell or next_token in (('|', True), ('&', True)),
                                         scope=detached + item.scope[len(current_scope):])
                           for item in current]
            if current:
                current[-1] = current[-1]._replace(separator=next_token[0] if next_token else '')
            commands.extend(current)
            pending = None
            if next_token is None or next_token == (')', True):
                break
            if not next_token[1] or next_token[0] not in (';', '&', '&&', '||', '|', '\n'):
                raise ParseError('expected shell separator; separate the commands with ;, && or a newline, or run each in its own call')
            pending = next_token[0]
            position += 1
        if pending in ('&&', '||', '|'):
            raise ParseError('missing command after separator; add the next command or remove the trailing operator')
        return commands

    result = group(subshell, scope)
    if position != len(tokens):
        raise ParseError('unmatched closing parenthesis; remove the ) or add the opening parenthesis')
    return result


def _unwrap(argv, subshell, raw_argv, inherited_env=None, protected=('git', 'gh'), *, words, texts, scope, scope_ids,
            variables=None):
    env = dict(inherited_env or {})
    while argv:
        if _ASSIGNMENT.match(argv[0]):
            _reject_mentions(raw_argv[0])
            if _expands(raw_argv[0]):
                raise ParseError('expanding environment assignment is unsupported; assign a literal value, or set it in an earlier separate command')
            key, value = argv[0].split('=', 1)
            env[key] = value
            argv = argv[1:]
            raw_argv = raw_argv[1:]
            continue
        program = PurePosixPath(argv[0]).name or argv[0]
        if not _literal(raw_argv[0]):
            # #730: a variable from the leading assignment statement is its literal value.
            name = _VARIABLE.fullmatch(raw_argv[0])
            value = (variables or {}).get(name[1]) if name else None
            if value is None or PurePosixPath(value).name in protected:
                raise ParseError(f'nonliteral command name {raw_argv[0]} in stage {" ".join(raw_argv)} is unsupported; '
                                 'assign it a literal path at the start of the command (x=bin/wuwei; $x ...), '
                                 'or write the command name literally')
            argv, raw_argv = [value, *argv[1:]], [value, *raw_argv[1:]]
            program = PurePosixPath(value).name
        if program in _PATH_COMMANDS and not all(
                _literal(raw, allow_globs=program not in ('cd', 'pushd', 'popd')) for raw in raw_argv):
            raise NonliteralPathError('nonliteral file or directory arguments are unsupported; write the literal path')
        if program not in ('git', 'gh'):
            _reject_mentions(raw_argv[0])
        if any(char in argv[0] for char in '$`*?[]') or program in (
                'if', 'then', 'else', 'fi', 'for', 'while', 'until', 'do', 'done',
                'case', 'esac', 'function', '{', '}', '!', 'trap',
                'alias', 'unalias', '.', 'source', 'shopt', 'enable',
                'export', 'readonly', 'unset', 'declare', 'typeset'):
            raise ParseError('dynamic command or shell control flow is unsupported; run plain simple commands, one per call. Or write the commands to a file and run bash <file>')
        if program == 'eval':
            if any(_expands(raw) for raw in raw_argv[1:]):
                raise ParseError('expanding eval is unsupported; run the command directly, or give eval a literal string')
            expanded = _parse(' '.join(argv[1:]), subshell, env, protected,
                              words=words, texts=texts, scope=scope, scope_ids=scope_ids)
            # eval runs in the current shell, unlike a shell -c child.
            return [item._replace(scope=scope + item.scope[len(scope) + 1:])
                    for item in expanded]
        if program == 'busybox':
            if len(argv) < 2 or argv[1] != 'sh':
                raise ParseError('unsupported busybox applet; run the command directly or use busybox sh -c \'...\'')
            argv, raw_argv = argv[1:], raw_argv[1:]
            program = 'sh'
        if program in ('sh', 'bash', 'zsh', 'dash', 'ksh'):
            index, has_script = 1, False
            while index < len(argv) and argv[index].startswith(('-', '+')):
                option = argv[index]
                index += 1
                if option == '--':
                    break
                if not re.fullmatch(r'[-+][a-zA-Z]+', option) or 'o' in option:
                    raise ParseError('unsupported shell option; use bash -c \'...\' with plain letter flags such as -c, -e and -u')
                has_script |= option.startswith('-') and 'c' in option
            if not has_script or index == len(argv):
                raise ParseError('missing shell -c script; use bash -c \'command\' or run the command directly')
            if _expands(raw_argv[index]):
                raise ParseError('expanding shell script is unsupported; put the script in single quotes or write the values literally')
            if index + 1 < len(argv) and re.search(r'\$[@*0-9{]', argv[index]):
                raise ParseError('shell positional expansion is unsupported; write the real values into the script text and drop the extra arguments')
            _reject_mentions(' '.join(raw_argv[:index] + raw_argv[index + 1:]))
            return _parse(argv[index], True, env, protected,
                          words=words, texts=texts, scope=scope, scope_ids=scope_ids)
        if program not in ('env', 'command', 'exec', 'nohup', 'time', 'xargs',
                           'nice', 'timeout', 'sudo', 'stdbuf', 'setsid'):
            if program in protected:
                if not all(_literal(raw) for raw in raw_argv) and not _variable_read(argv, raw_argv, words):
                    raise ParseError('nonliteral guarded arguments are unsupported; write the literal arguments')
                return [Command(argv, subshell, env, scope=scope)]
            if reads(argv):
                texts += (' '.join(raw_argv), ' '.join(argv))
            else:
                _reject_mentions(' '.join(raw_argv))
                _reject_mentions(' '.join(argv))
            return [Command(argv, subshell, env, scope=scope)]
        if program == 'xargs':
            _reject_mentions(' '.join(raw_argv))
        if program == 'command' and any(option in ('-v', '-V') for option in argv[1:2]):
            _reject_mentions(' '.join(raw_argv))
            return [Command(argv, subshell, env, scope=scope)]
        index = 1
        no_value = {'env': ('-i', '--ignore-environment'), 'command': ('-p',),
                    'exec': ('-c', '-l'), 'nohup': (), 'time': ('-p',),
                    'nice': (), 'timeout': ('--foreground', '--preserve-status'),
                    'sudo': ('-n', '-E', '-H'), 'stdbuf': (), 'setsid': ('-f', '-w'),
                    'xargs': ('-0', '-r', '-t', '-p', '-x', '--null', '--no-run-if-empty')}
        with_value = {'env': ('-u', '--unset'), 'exec': ('-a',),
                      'nice': ('-n', '--adjustment'), 'timeout': ('-s', '-k'),
                      'sudo': ('-u', '-g'), 'stdbuf': ('-i', '-o', '-e'),
                      'xargs': ('-I', '-n', '-P', '-L', '-s', '-d', '-E',
                                '--replace', '--max-args', '--max-procs', '--delimiter')}
        while index < len(argv) and argv[index].startswith('-'):
            option = argv[index]
            index += 1
            if option == '--':
                break
            if option in no_value[program]:
                if program == 'env' and option in ('-i', '--ignore-environment'):
                    env.clear()
                continue
            value_options = with_value.get(program, ())
            if option in value_options:
                if index == len(argv):
                    raise ParseError(f'missing {program} option value; add the value after it, or remove the option')
                if program == 'env':
                    env.pop(argv[index], None)
                index += 1
            elif not any(option.startswith(flag + '=') if flag.startswith('--')
                         else option.startswith(flag) and len(option) > len(flag)
                         for flag in value_options):
                raise ParseError(f'unsupported {program} option; drop it, or run the inner command without the wrapper')
            elif program == 'env':
                env.pop(option.partition('=')[2] if option.startswith('--') else option[2:], None)
        if program == 'timeout':
            if index == len(argv) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?[smhd]?', argv[index]):
                raise ParseError('unsupported timeout duration; write a literal duration such as 30, 5m or 1.5h before the command')
            index += 1
        _reject_mentions(' '.join(raw_argv[:index]))
        argv = argv[index:]
        raw_argv = raw_argv[index:]
        if program == 'xargs':
            subshell = True
            if not argv:
                return [Command(['echo'], True, env)]
            expanded = _unwrap(argv, subshell, raw_argv, env, protected,
                               words=words, texts=texts, scope=scope, scope_ids=scope_ids,
                               variables=variables)
            if any(item.writes or (item.argv and PurePosixPath(item.argv[0]).name in
                                  (*protected, *_PATH_COMMANDS)) for item in expanded):
                raise ParseError('input-driven guarded arguments are unsupported; run the command directly with literal arguments instead of piping into xargs')
            return expanded
        elif not argv:
            raise ParseError(f'missing command after {program}; add the command to run, or drop the prefix')
    if any(key in env for key in ('HOME', 'OLDPWD', 'CDPATH')):
        raise ParseError('standalone directory environment assignments are unsupported; set HOME, OLDPWD or CDPATH inline on the one command that needs it, or drop it')
    return []


_INTERPRETER = r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua'
# The inline-code option letters of each interpreter other than python and pypy (-c).
_SNIPPET = {'node': 'ep', 'perl': 'eE', 'ruby': 'e', 'php': 'r', 'lua': 'e'}
# #643: what makes a python -c snippet more than a read; the leftmost match is named.
# Fails closed: any escape, run-time input (chr, argv, environ, stdin, input, lower, decode)
# or less common writer (logging handlers, archive extraction, dunders) is not a read.
# ponytail: a case-blind token scan, not a parser; switch to an ast allowlist if it keeps growing.
_SNIPPET_WRITES = re.compile(
    r"""(['"])[rbt]*[wax+][rbtwax+]*\1"""  # an open mode that writes: 'w', "a+", 'rb+'
    r'|\w*(?:write|remove|rename|replace|unlink|rmdir|mkdir|makedirs|touch|truncate|chmod|chown'
    r'|symlink|hardlink|inplace)\w*|os\.(?:link|open|fork)'
    r'|shutil|subprocess|system|popen|spawn|exec|eval|getattr|__import__|importlib|runpy|ctypes'
    r'|sqlite3|shelve|dbm|\brun\(|\bpty\b|\b(?:git|gh)\b'  # #671: a snippet that may run git or gh
    r'|\\|chr|argv|environ|stdin|input|lower|decode|logging|Handler|extract|tarfile|zipfile'
    r'|__|vars|globals'
    r'|(?<![\w/-])(?<![^\w.]\.)wuwei(?![\w/-])', re.I)  # the CLI imported; not .wuwei/ or cli/wuwei/


# Every cd, pushd and popd refusal of the state guard; the hook warns it whatever guards.enforce says.
WORKSPACE_ROOT = ('workspace guard: a top-level cd, pushd or popd may leave the workspace; '
                  'run it in a subshell, (cd <dir> && <command>), or use git -C <dir>')
# A relevant call a guard could not read; the hook logs it, never refuses it (#347, #839).
UNPARSED = ('unparsed: write the commands to a file with the Write tool and run bash <file>; '
            'a plain git or gh command stays plain')
# #616: checksum tools only read their operands and print digests; none writes or runs code.
READ_ONLY = frozenset({'ls', 'cat', 'less', 'grep', 'head', 'tail', 'sed', 'wc', 'jq', 'diff',
                       'find', 'cd', 'pushd', 'popd', 'echo', 'shasum', 'sha1sum', 'sha256sum',
                       'sha512sum', 'md5sum', 'cksum'})
# #470: git subcommands by outcome (data; tests/test_shell.py pins them); any other
# subcommand, an alias included, is unknown (spec A3).
# ponytail: reflog and symbolic-ref with extra operands edit local refs; a local ref is not
# a publish, and the pre-push hook and protected refs anchor pushes (spec 4.5).
_GIT_READS = frozenset({
    'status', 'diff', 'log', 'show', 'rev-parse', 'ls-files', 'ls-remote', 'symbolic-ref',
    'describe', 'show-ref', 'blame', 'annotate', 'grep', 'cat-file', 'ls-tree', 'rev-list',
    'for-each-ref', 'shortlog', 'name-rev', 'reflog', 'merge-base', 'range-diff',
    'merge-tree', 'check-ignore', 'count-objects', 'var', 'whatchanged', 'cherry', 'fetch',
    'help', 'version'})
# Read only when the first word after the subcommand ('' when bare) and every flag are among
# these words; any other form writes.
_GIT_READ_FORMS = {
    'branch': ('', '--list', '-l', '-a', '--all', '-r', '--remotes', '-v', '-vv',
               '--show-current'),
    'tag': ('', '--list', '-l'),
    'remote': ('', '-v', '--verbose', 'show', 'get-url'),
    'stash': ('list', 'show'),
    'worktree': ('list',),
    'config': ('--get', '--get-all', '--get-regexp', '--list', '-l'),
    'bisect': ('log',)}
_GIT_WRITES = frozenset({
    *_GIT_READ_FORMS, 'push', 'commit', 'merge', 'rebase', 'reset', 'checkout', 'switch',
    'filter-branch', 'update-ref', 'am', 'cherry-pick', 'revert', 'notes', 'submodule', 'gc',
    'prune', 'clean', 'rm', 'mv', 'apply', 'add', 'restore', 'init'})
# Options that make a read run a program.
_GIT_RUNS = ('-O', '--open-files-in-pager', '--upload-pack')
# gh subcommands (second word) that only read.
_GH_READS = ('list', 'view', 'status', 'checks', 'diff')
_FIND_ACTIONS = frozenset({'-exec', '-execdir', '-ok', '-okdir', '-delete', '-fprint', '-fprint0',
                           '-fprintf', '-fls'})


def _variable_read(argv, raw_argv, words):
    """#470: a read-only git or gh subcommand whose only nonliteral words are plain variables
    assigned in this command to single safe words, so no expansion splits into a verb or option."""
    for raw in raw_argv:
        if _literal(raw):
            continue
        name = re.fullmatch(r'"?\$\{?([A-Za-z_]\w*)\}?"?', raw)
        values = [word.split('=', 1)[1] for word in words if name and word.startswith(name[1] + '=')]
        if not values or not all(re.fullmatch(r'\w[\w./:@+-]*', value) for value in values):
            return False
    if PurePosixPath(argv[0]).name == 'git':
        return git_kind(argv[1:]) == 'read'
    return len(argv) > 2 and '$' not in argv[1] + argv[2] and argv[2] in _GH_READS


def git_runs(verb, args):
    """#470: True when an option makes git run a program; git accepts any unambiguous
    prefix of a long option, so --open= and --upload= count as well."""
    for arg in args:
        if arg.startswith('-O') or verb == 'ls-remote' and arg.startswith('-u'):
            return True
        name = arg.split('=', 1)[0]
        if name.startswith('--') and len(name) >= 5 and any(opt.startswith(name) for opt in _GIT_RUNS[1:]):
            return True
    return False


def git_kind(args):
    """#470: 'read', 'write' or 'unknown' for git's argv after the program name."""
    args = list(args)
    while args and args[0].startswith('-'):
        if args[0].startswith(('-c', '--config-env')):
            return 'unknown'  # a config value can define an alias or run a command
        args = args[2:] if args[0] in ('-C', '--git-dir', '--work-tree', '--namespace') else args[1:]
    if not args:
        return 'read'
    verb, rest = args[0], args[1:]
    if '$' in verb or git_runs(verb, rest):
        return 'unknown'
    if verb in _GIT_READS:
        return 'read'
    forms = _GIT_READ_FORMS.get(verb, ())
    if (rest[0] if rest else '') in forms and all(arg in forms for arg in rest if arg.startswith('-')):
        return 'read'
    return 'write' if verb in _GIT_WRITES else 'unknown'


def snippet_write(argv):
    """#643: the first write-like token of python [-flags] -c <code>; '' when the code only
    reads; None for any other form (attached -c<code>, -i, -W, -X, -m, a script, stdin)."""
    if not argv or not re.fullmatch(r'(?:python|pypy)[\d.]*', PurePosixPath(argv[0]).name):
        return None
    for index, word in enumerate(argv[1:], 2):
        if re.fullmatch(r'-[BEIOPSdqsu]*c', word):
            if index == len(argv):
                return None
            match = _SNIPPET_WRITES.search(argv[index])  # later words are sys.argv data
            return match[0] if match else ''
        if not re.fullmatch(r'-[BEIOPSdqsu]+', word):
            return None
    return None


def reads(argv):
    """#349: one command only reads: a READ_ONLY word (sed -n Np, find with no action) or a
    python -c snippet with no write-like token (#643). Shared by the classifier and the state guard."""
    if not argv:
        return False
    name, args = PurePosixPath(argv[0]).name, argv[1:]
    if name == 'sed':
        options = [arg for arg in args if arg.startswith('-')]
        operands = [arg for arg in args if not arg.startswith('-')]
        return options == ['-n'] and bool(operands) and bool(re.fullmatch(r'[0-9,$]+p', operands[0]))
    if name == 'find':
        return not _FIND_ACTIONS.intersection(args)
    if re.fullmatch(r'(?:python|pypy)[\d.]*', name):
        if args[:2] == ['-m', 'json.tool']:
            return len(args) < 4  # no operand reads stdin; a second operand is json.tool's outfile
        return snippet_write(argv) == ''  # #643
    return name in READ_ONLY


def inline_code(argv):
    """#349: an interpreter runs code given inline (-c, -e, --eval, ...)."""
    name = PurePosixPath(argv[0]).name if argv else ''
    if not re.fullmatch(_INTERPRETER, name):
        return False
    flags = 'c' if name.startswith(('python', 'pypy')) else _SNIPPET[name]
    return any(re.fullmatch(r'-[a-zA-Z]*?[' + flags + r'][\s\S]*', arg)
               or arg == '--eval' or arg.startswith('--eval=') for arg in argv[1:])


