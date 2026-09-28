"""Static shell normalization for guards. Never execute or expand input text."""

from pathlib import PurePosixPath
import re
import shlex
from typing import NamedTuple


class ParseError(ValueError):
    """The command cannot be inspected safely; guards must return exit 2."""


class NonliteralPathError(ParseError):
    """A file or directory operand cannot be resolved statically."""


class Command(NamedTuple):
    argv: list[str]
    subshell: bool
    env: dict[str, str]
    writes: tuple[str, ...] = ()


# Words retain quote boundaries so expansion checks distinguish literal data.
_TOKEN = re.compile(r'(?P<space>[ \t\r]+)|(?P<comment>\#[^\n]*)|'
                    r'(?P<redirect>[0-9]*(?:<<-?|>>!?|>!|<>|>&|<&|>\||[<>])|&>>?)|'
                    r'(?P<operator>\&\&|\|\||[;&|()\n])')
_ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z_0-9]*=')
_PATH_COMMANDS = ('cd', 'pushd', 'popd', 'tee', 'cp', 'mv', 'sed', 'dd', 'truncate')
_GUARDED = re.compile(r'(?<![.\w])(?:git|gh)\b')
_QUOTED_PART = re.compile(r''' '[^']*'|"(?:\\[\s\S]|[^"\\])*"|\\[\s\S]|[^'"\\]+ ''', re.VERBOSE)


def _expands(raw):
    return any('$' in re.sub(r'\\[\s\S]', '', part[0])
               for part in _QUOTED_PART.finditer(raw)
               if not part[0].startswith(("'", '\\')))


def _reject_mentions(text):
    if _GUARDED.search(text) or _GUARDED.search(re.sub(r'''['"\\]''', '', text)):
        raise ParseError('unaccounted git/gh mention')


def _literal(raw, allow_globs=False):
    return not _expands(raw) and not any(
        re.search((r'`' if allow_globs else r'[`*?\[]') + r'|\{[^{}]*(,|\.\.)[^{}]*\}', part[0])
        for part in _QUOTED_PART.finditer(raw)
        if not part[0].startswith(("'", '"', '\\')))


def _word(raw):
    parts = list(_QUOTED_PART.finditer(raw))
    for first, second in zip(parts, parts[1:]):
        if not first[0].startswith(("'", '"', '\\')) and first[0].endswith('$') and second[0].startswith("'"):
            raise ParseError('ANSI-C quoting is unsupported')
    return ''.join(shlex.split(part[0])[0].replace('\\$', '$')
                   if part[0].startswith('"') else shlex.split(part[0])[0]
                   for part in parts)


def normalize(command: str) -> list[Command]:
    """Return argv lists with subshell scope, or raise ParseError.

    ponytail: this is a conservative simple-command parser, not a shell evaluator.
    Reject dynamic substitutions, control flow and unknown wrapper options; extend
    the supported grammar with bypass tests when a guard needs those constructs.
    """
    try:
        return _parse(command, False)
    except (ValueError, RecursionError) as exc:
        error = type(exc) if isinstance(exc, ParseError) else ParseError
        raise error((str(exc) or 'shell nesting too deep') +
                    '; run git or gh as a plain command') from exc


def _heredoc(script, position, delimiter, strip_tabs=False):
    ending = re.compile(r'^' + (r'\t*' if strip_tabs else '') +
                        re.escape(delimiter) + r'(?:\n|$)', re.MULTILINE)
    match = ending.search(script, position)
    if not match:
        raise ParseError('unterminated here-doc')
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
                raise ParseError('trailing backslash')
            raw.append(script[position:position + 2])
            position += 2
            continue
        if quote != "'" and script.startswith('$(', position):
            # Only a quoted literal cat here-doc has a statically known result.
            header = re.match(r"""\$\(cat[ \t]+<<(-?)[ \t]*(['"])([\w-]+)\2[ \t]*\n""",
                              script[position:])
            if quote != '"' or not header:
                raise ParseError('command substitution is unsupported')
            body, position = _heredoc(script, position + header.end(), header[3], bool(header[1]))
            end = re.match(r'\s*\)', script[position:])
            if not end:
                raise ParseError('command substitution contains more than a literal here-doc')
            position += end.end()
            raw.append('"' + shlex.quote(body.rstrip('\n')) + '"')
            continue
        if char == '`' and quote != "'":
            raise ParseError('command substitution is unsupported')
        if char in ("'", '"'):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        raw.append(char)
        position += 1
    if quote or not raw:
        raise ParseError('unbalanced quotes or missing word')
    return ''.join(raw), position


def _parse(script, subshell, env=None):
    if not isinstance(script, str) or '\0' in script:
        raise ParseError('command must be text without NUL')
    tokens, raw_tokens, heredocs = [], [], []
    writes_at = {}
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
                        raise ParseError('only quoted here-doc delimiters are supported')
                    heredocs.append((_word(target), raw.endswith('-'), command_start))
                elif not _literal(target):
                    raise NonliteralPathError('nonliteral redirection is unsupported')
                elif '>' in raw and not ('&' in raw and re.fullmatch(r'[0-9]+-?|-', _word(target))):
                    writes_at[len(tokens)] = _word(target)
                    tokens.append(('', False))
                    raw_tokens.append('')
                _reject_mentions(script[start:position])
                continue
            if raw == '\n':
                for delimiter, strip_tabs, owner_start in heredocs:
                    body, position = _heredoc(script, position, delimiter, strip_tabs)
                    owner = tokens[owner_start] if owner_start < len(tokens) else ('', True)
                    if owner[1] or PurePosixPath(owner[0]).name not in ('git', 'gh'):
                        _reject_mentions(body)
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
            raise ParseError('normalization hides a git/gh mention')
        if not raw:
            continue
        tokens.append((raw if operator else _word(raw), operator))
        raw_tokens.append(raw)
        if operator:
            command_start = len(tokens)
    if heredocs:
        raise ParseError('missing here-doc body')

    position = 0

    def group(nested):
        nonlocal position
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
                raise ParseError('unexpected shell separator')
            if operator:
                position += 1
                current = group(True)
                if position == len(tokens) or tokens[position] != (')', True) or not current:
                    raise ParseError('unbalanced or empty subshell')
                position += 1
            else:
                argv = []
                raw_argv, writes = [], []
                while position < len(tokens) and not tokens[position][1]:
                    if position in writes_at:
                        writes.append(writes_at[position])
                    else:
                        argv.append(tokens[position][0])
                        raw_argv.append(raw_tokens[position])
                    position += 1
                current = _unwrap(argv, nested, raw_argv, env)
                if writes:
                    if not current:
                        current = [Command([], nested, dict(env or {}))]
                    current[0] = current[0]._replace(writes=tuple(writes) + current[0].writes)
            while position in writes_at:
                current[0] = current[0]._replace(writes=current[0].writes + (writes_at[position],))
                position += 1
            next_token = tokens[position] if position < len(tokens) else None
            if next_token in (('|', True), ('&', True)):
                current = [item._replace(subshell=True) for item in current]
            commands.extend(current)
            pending = None
            if next_token is None or next_token == (')', True):
                break
            if not next_token[1] or next_token[0] not in (';', '&', '&&', '||', '|', '\n'):
                raise ParseError('expected shell separator')
            pending = next_token[0]
            position += 1
        if pending in ('&&', '||', '|'):
            raise ParseError('missing command after separator')
        return commands

    result = group(subshell)
    if position != len(tokens):
        raise ParseError('unmatched closing parenthesis')
    return result


def _unwrap(argv, subshell, raw_argv, inherited_env=None):
    env = dict(inherited_env or {})
    while argv:
        if _ASSIGNMENT.match(argv[0]):
            _reject_mentions(raw_argv[0])
            if _expands(raw_argv[0]):
                raise ParseError('expanding environment assignment is unsupported')
            key, value = argv[0].split('=', 1)
            env[key] = value
            argv = argv[1:]
            raw_argv = raw_argv[1:]
            continue
        program = PurePosixPath(argv[0]).name or argv[0]
        if not _literal(raw_argv[0]):
            raise ParseError('nonliteral command name is unsupported')
        if program in _PATH_COMMANDS and not all(
                _literal(raw, allow_globs=program not in ('cd', 'pushd', 'popd')) for raw in raw_argv):
            raise NonliteralPathError('nonliteral file or directory arguments are unsupported')
        if program not in ('git', 'gh'):
            _reject_mentions(raw_argv[0])
        if any(char in argv[0] for char in '$`*?[]') or program in (
                'if', 'then', 'else', 'fi', 'for', 'while', 'until', 'do', 'done',
                'case', 'esac', 'function', '{', '}', '!', 'trap',
                'alias', 'unalias', '.', 'source', 'shopt', 'enable',
                'export', 'readonly', 'unset', 'declare', 'typeset'):
            raise ParseError('dynamic command or shell control flow is unsupported')
        if program in ('git', 'gh'):
            if not all(_literal(raw) for raw in raw_argv):
                raise ParseError('nonliteral guarded arguments are unsupported')
            return [Command(argv, subshell, env)]
        if program == 'eval':
            if any(_expands(raw) for raw in raw_argv[1:]):
                raise ParseError('expanding eval is unsupported')
            for raw in raw_argv[1:]:
                if len(list(_QUOTED_PART.finditer(raw))) > 1:
                    _reject_mentions(raw)
            return _parse(' '.join(argv[1:]), subshell, env)
        if program == 'busybox':
            if len(argv) < 2 or argv[1] != 'sh':
                raise ParseError('unsupported busybox applet')
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
                    raise ParseError('unsupported shell option')
                has_script |= option.startswith('-') and 'c' in option
            if not has_script or index == len(argv):
                raise ParseError('missing shell -c script')
            if _expands(raw_argv[index]):
                raise ParseError('expanding shell script is unsupported')
            if index + 1 < len(argv) and re.search(r'\$[@*0-9{]', argv[index]):
                raise ParseError('shell positional expansion is unsupported')
            _reject_mentions(' '.join(raw_argv[:index] + raw_argv[index + 1:]))
            if len(list(_QUOTED_PART.finditer(raw_argv[index]))) > 1:
                _reject_mentions(raw_argv[index])
            if len(_GUARDED.findall(re.sub(r'''['"\\]''', '', argv[index]))) > len(_GUARDED.findall(argv[index])):
                raise ParseError('obfuscated git/gh mention in shell script')
            return _parse(argv[index], True, env)
        if program not in ('env', 'command', 'exec', 'nohup', 'time', 'xargs',
                           'nice', 'timeout', 'sudo', 'stdbuf', 'setsid'):
            _reject_mentions(' '.join(raw_argv))
            _reject_mentions(' '.join(argv))
            return [Command(argv, subshell, env)]
        if program == 'xargs':
            _reject_mentions(' '.join(raw_argv))
        if program == 'command' and any(option in ('-v', '-V') for option in argv[1:2]):
            _reject_mentions(' '.join(raw_argv))
            return [Command(argv, subshell, env)]
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
                    raise ParseError(f'missing {program} option value')
                if program == 'env':
                    env.pop(argv[index], None)
                index += 1
            elif not any(option.startswith(flag + '=') if flag.startswith('--')
                         else option.startswith(flag) and len(option) > len(flag)
                         for flag in value_options):
                raise ParseError(f'unsupported {program} option')
            elif program == 'env':
                env.pop(option.partition('=')[2] if option.startswith('--') else option[2:], None)
        if program == 'timeout':
            if index == len(argv) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?[smhd]?', argv[index]):
                raise ParseError('unsupported timeout duration')
            index += 1
        _reject_mentions(' '.join(raw_argv[:index]))
        argv = argv[index:]
        raw_argv = raw_argv[index:]
        if program == 'xargs':
            subshell = True
            if not argv:
                return [Command(['echo'], True, env)]
            expanded = _unwrap(argv, subshell, raw_argv, env)
            if any(item.writes or (item.argv and PurePosixPath(item.argv[0]).name in
                                  ('git', 'gh', *_PATH_COMMANDS)) for item in expanded):
                raise ParseError('input-driven guarded arguments are unsupported')
            return expanded
        elif not argv:
            raise ParseError(f'missing command after {program}')
    if any(key in env for key in ('HOME', 'OLDPWD', 'CDPATH')):
        raise ParseError('standalone directory environment assignments are unsupported')
    return []


def is_opaque(argv: list[str]) -> bool:
    """Flag hidden git/gh argv and interpreter snippets for guard refusal.

    ponytail: constructed names such as "gi" + "t" remain opaque to this heuristic;
    the repository pre-push hook is the enforcement anchor for that residual.
    """
    if not argv:
        return False
    if any(PurePosixPath(word).name in ('git', 'gh') for word in argv[1:]):
        return True
    program = PurePosixPath(argv[0]).name or argv[0]
    if not re.fullmatch(r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua', program):
        return False
    flags = ('c' if program.startswith(('python', 'pypy')) else
             {'node': 'ep', 'perl': 'eE', 'ruby': 'e', 'php': 'r', 'lua': 'e'}[program])
    has_snippet = False
    for index, arg in enumerate(argv[1:], 1):
        match = re.fullmatch(r'-[a-zA-Z]*?[' + flags + r']([\s\S]*)', arg)
        if program == 'node' and (arg == '--eval' or arg.startswith('--eval=')):
            snippet = arg.partition('=')[2]
        elif match:
            snippet = match[1]
        else:
            continue
        has_snippet = True
        if index + 1 < len(argv):
            snippet += '\n' + argv[index + 1]
        if re.search(r'\b(?:git|gh)\b', snippet):
            return True
    # Without a snippet, only a leading path proves input is not stdin. Option
    # operands might otherwise look like paths; conservatively flag those forms.
    return not has_snippet and (len(argv) == 1 or argv[1].startswith('-'))
