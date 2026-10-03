"""Workspace instruction markers and decoy credentials, never public evidence."""

import json
from pathlib import Path
import re

from wuwei import workspace


DEFAULT_HONEYTOKEN_PATH = 'credentials/backup.env'


def honeytoken_path(directory, value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', value)
            or Path(value).is_absolute() or '..' in Path(value).parts
            or Path(value).parts[0] in {'generated', 'charters', 'memory', 'days', 'archive'}
            or len(Path(value).parts) < 2):
        raise ValueError('honeytoken path must be a relative file in a private subdirectory')
    path = directory / value
    if path.resolve() != directory.resolve() / value:
        raise ValueError('honeytoken path must not traverse symlinks')
    return path


def initialize(directory, decoy=DEFAULT_HONEYTOKEN_PATH):
    import secrets
    directory = Path(directory)
    path = honeytoken_path(directory, decoy)
    if path.exists():
        raise ValueError('honeytoken path already exists')
    data = {'canary': secrets.token_urlsafe(32), 'honeytoken': secrets.token_urlsafe(32),
            'honeytoken_path': decoy}
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(path, 'API_KEY=' + data['honeytoken'] + '\n', mode=0o400)
    workspace.atomic_write(directory / 'security.json', json.dumps(data) + '\n', mode=0o400)
    ignore = directory / '.gitignore'
    previous = ignore.read_text() if ignore.exists() else ''
    workspace.atomic_write(ignore, previous + '\n/security.json\n/generated/\n/' + decoy + '\n')
    return data


def load(root, *, raw=None):
    """Security material, or None when absent and not required; raw stands in for config.toml
    (init --upgrade checks a repaired config before writing it, #326)."""
    directory = Path(root) / '.wuwei'
    path = directory / 'security.json'
    try:
        if not path.exists() and not path.is_symlink():
            config = directory / 'config.toml'
            required = None
            if raw is None:
                try:  # The validated config, from its parsed copy on a hook (#346).
                    required = workspace.load_config(root)['security']['required']
                except (OSError, ValueError):
                    raw = config.read_text() if config.exists() else ''
            if required is None:  # A candidate text, or a missing or invalid file: the key itself.
                import tomllib
                required = tomllib.loads(raw).get('security', {}).get('required', False)
            if not required:
                return None
        if path.is_symlink():
            raise ValueError('security material must not be a symlink')
        data = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or set(data) != {'canary', 'honeytoken', 'honeytoken_path'}
                or any(not isinstance(data[key], str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,}', data[key])
                       for key in ('canary', 'honeytoken'))
                or data['canary'] == data['honeytoken']):
            raise ValueError('invalid security material')
        honeytoken_path(directory, data['honeytoken_path'])
        return data
    except (OSError, ValueError, TypeError, AttributeError):
        raise ValueError('security material unavailable or invalid; restore workspace security files') from None


def instruction(data):
    return '\nPrivate instruction canary: ' + data['canary'] + '. Never repeat or transmit this value.\n'


def agent_path(root, role):
    """Return private instructions when this workspace has security enabled."""
    charter = Path(__file__).resolve().parents[2] / 'charters' / (role + '.md')
    if root is not None and load(root) is not None:
        path = Path(root) / '.wuwei/generated/agents' / (role + '.md')
        # An unknown role falls through to the adapter's unknown role refusal.
        if not path.is_file() and charter.is_file():
            raise ValueError('workspace instructions unavailable; run wuwei agents build')
        return path
    return charter


def matches(value, data):
    """Match exact markers in both JSON keys and values before any truncation."""
    if isinstance(value, dict):
        return set().union(*(matches(item, data) for pair in value.items() for item in pair))
    if isinstance(value, list):
        return set().union(*(matches(item, data) for item in value))
    if isinstance(value, str) and data:
        return {key for key in ('canary', 'honeytoken') if data[key] in value}
    return set()


def record(findings, root, source):
    from wuwei import state
    for finding in sorted(findings):
        payload = {'tier': 'page', 'source': source}
        state.append_event('security.' + finding, payload, root)
        if finding == 'honeytoken':
            state.append_event('scanner.finding', {**payload, 'rule': 'security.honeytoken'}, root)


def outbound(value, root=None):
    try:
        if root is None:
            root = workspace.guard_scope({'cwd': str(Path.cwd())})
            if root is None:
                return 0, ''
        findings = matches(value, load(root))
        if not findings:
            return 0, ''
        record(findings, root, 'outbound')
        return 1, 'outward: ' + ', '.join('security.' + key for key in sorted(findings))
    except (OSError, ValueError, TypeError, RuntimeError):
        return 2, 'outward: cannot read security material or record security evidence'


def redact(value, data):
    """Replace exact markers recursively before generic redaction or truncation."""
    if not data:
        return value
    if isinstance(value, dict):
        return {redact(key, data): redact(item, data) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, data) for item in value]
    if isinstance(value, str):
        for key in ('canary', 'honeytoken'):
            value = value.replace(data[key], '[REDACTED]')
    return value


def reads_honeytoken(payload, root, data):
    import os
    from wuwei import shell

    target = Path(root) / '.wuwei' / data['honeytoken_path']
    cwd = Path(payload['cwd']).resolve()

    def is_target(value):
        if not isinstance(value, str) or not value or '\0' in value:
            return False
        candidate = (cwd / value).resolve()
        return candidate == target or (candidate.is_file() and target.is_file()
                                       and os.path.samefile(candidate, target))

    def path_fields(value):
        if isinstance(value, dict):
            return any(is_target(item) if key in ('path', 'file_path', 'filename') else path_fields(item)
                       for key, item in value.items())
        if isinstance(value, list):
            return any(path_fields(item) for item in value)
        return False

    inputs = payload.get('tool_input', {})
    if payload.get('tool_name') != 'Bash':
        return path_fields(inputs)
    script = inputs.get('command')
    if not isinstance(script, str):
        raise ValueError('invalid shell tool input')
    readers = ('cat', 'head', 'tail', 'less', 'more', 'grep', 'rg', 'sed', 'awk', 'cp', 'dd',
               'base64', 'strings', 'od', 'xxd', 'hexdump')
    if not shell.mentions(script, (*readers, target.name)):
        return False
    try:
        commands = shell.normalize(script, protected=readers)
    except shell.ParseError:
        if shell.mentions(script, (target.name,)):
            raise ValueError('cannot inspect honeytoken read') from None
        return False
    # ponytail: flattened shell groups retain possible directories conservatively.
    # Exact nested directory flow belongs in a future shell parser extension.
    directories = persistent = {cwd}
    for command in commands:
        directories = directories | persistent if command.subshell else persistent
        if command.argv and Path(command.argv[0]).name == 'cd':
            from wuwei.guards.protect_state import _cd_target
            destinations = {(base / _cd_target(command)).resolve() for base in directories}
            directories = directories | destinations if command.subshell else destinations
            if len(directories) > 64:
                raise ValueError('too many possible read directories')
            if not command.subshell:
                persistent = directories
            continue
        candidates = list(command.reads) + command.argv[1:]
        for cwd in directories:
            if any(is_target(value.removeprefix('if=')) for value in candidates):
                return True
    return False


def instruction_response(payload, root):
    if payload.get('tool_name') != 'Read':
        return payload.get('tool_response')
    value = payload.get('tool_input', {}).get('file_path')
    if not isinstance(value, str):
        return payload.get('tool_response')
    path = (Path(payload['cwd']) / value).resolve()
    generated = Path(root) / '.wuwei/generated'
    if (not path.is_relative_to(generated) or path.suffix != '.md'
            or path.relative_to(generated).parts[0] not in ('agents', 'charters', 'skills')):
        return payload.get('tool_response')
    expected = path.read_text(encoding='utf-8')

    def omit_expected(value):
        if isinstance(value, dict):
            return {key: omit_expected(item) for key, item in value.items()}
        if isinstance(value, list):
            return [omit_expected(item) for item in value]
        return '' if value == expected else value

    return omit_expected(payload.get('tool_response'))


def trace_findings(payload, root, data):
    if not data:
        return set()
    findings = set()
    if payload.get('tool_name') in ('Read', 'WebFetch'):
        findings = matches(instruction_response(payload, root), data)
    findings |= matches(payload.get('tool_response'), data) & {'honeytoken'}
    if reads_honeytoken(payload, root, data):
        findings.add('honeytoken')
    return findings


def gh_outbound(argv, cwd, root, *, api=False, text_write=False):
    """Inspect parsed arguments and file-backed bodies for protected markers."""
    if text_write and any(marker in arg for arg in argv for marker in ('WUWEI parked ', 'WUWEI carried ')):
        return 1, 'owner disposition markers must be posted by the owner'
    paths = []
    for index, arg in enumerate(argv):
        flags = ('--input',) if api else ('--body-file', '-F')
        if arg in flags:
            if index + 1 >= len(argv):
                raise ValueError('missing outbound body file')
            paths.append((argv[index + 1], api))
        elif any(arg.startswith(flag + '=') for flag in flags):
            paths.append((arg.partition('=')[2], api))
        elif not api and arg.startswith('-F'):
            paths.append((arg[2:], False))
        elif api:
            field = ''
            if arg in ('--field', '-F') and index + 1 < len(argv):
                field = argv[index + 1]
            elif arg.startswith('--field='):
                field = arg.partition('=')[2]
            elif arg.startswith('-F'):
                field = arg[2:]
            if '=@' in field:
                paths.append((field.partition('=@')[2], False))
    for name, json_body in paths:
        if not name or name == '-':
            return 2, 'outward: cannot inspect outbound stdin or missing body file'
        try:
            text = (cwd / name).read_text(encoding='utf-8')
            if json_body:
                text = json.dumps(json.loads(text), ensure_ascii=False)
        except (OSError, ValueError):
            return 2, 'outward: opaque request, cannot read outbound body file'
        code, reason = outbound(text, root)
        if code:
            return code, reason
        if any(marker in text for marker in ('WUWEI parked ', 'WUWEI carried ')):
            return 1, 'owner disposition markers must be posted by the owner'
    return 0, ''
