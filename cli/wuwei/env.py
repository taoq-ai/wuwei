"""Literal workspace credentials, private on disk and in diagnostics."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat

from wuwei import redact
from wuwei.exits import SYMLINK


CREDENTIALS = ('LINEAR_API_KEY', 'SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN',
               'SLACK_OWNER_DM_CHANNEL', 'GREPTILE_API_KEY', 'WUWEI_CALENDAR_URL',
               'GH_TOKEN', 'GITHUB_TOKEN', 'WUWEI_TOTP_SECRET', 'SLACK_API_BASE')
PUBLIC = ('SLACK_OWNER_DM_CHANNEL',)  # identifiers: kept from seats, never redacted
_loaded = set()
_shadowed = set()  # .wuwei/env names whose value the process environment overrides


def child_environment():
    """Keep workspace and adapter credentials out of seat subprocesses."""
    return {name: value for name, value in os.environ.items()
            if name not in _loaded and name not in CREDENTIALS}


@contextmanager
def session():
    """Do not leave file credentials behind when main is called in-process."""
    previous = dict(os.environ)
    known = redact.VALUES.copy()
    loaded = _loaded.copy()
    shadowed = _shadowed.copy()
    try:
        redact.VALUES.update(previous[name] for name in CREDENTIALS
                             if previous.get(name) and name not in PUBLIC)
        yield
    finally:
        for name in _loaded - loaded:
            if name in previous:
                os.environ[name] = previous[name]
            else:
                os.environ.pop(name, None)
        _loaded.clear()
        _loaded.update(loaded)
        _shadowed.clear()
        _shadowed.update(shadowed)
        redact.VALUES.clear()
        redact.VALUES.update(known)


def load(root):
    path = Path(root) / '.wuwei/env'
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return
    except OSError:
        raise ValueError('.wuwei/env: cannot open private credentials file; create .wuwei/env as a regular file with mode 0600 (chmod 600 .wuwei/env)') from None
    try:
        with os.fdopen(fd, encoding='utf-8') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('.wuwei/env: expected a regular file with mode 0600; replace it with a regular file and run chmod 600 .wuwei/env')
            raw = stream.read(65537)
        if len(raw) > 65536 or '\0' in raw:
            raise ValueError('.wuwei/env: invalid or oversized credentials file; write one NAME=value per line, under 64 KiB')
        values = {}
        for number, line in enumerate(raw.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, separator, value = line.partition('=')
            name, value = name.strip(), value.strip()
            if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
                raise ValueError(f'.wuwei/env: invalid assignment at line {number}; write it as NAME=value')
            if value.startswith(('"', "'")):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError(f'.wuwei/env: unmatched quote at line {number}; add the closing quote')
                value = value[1:-1]
            values[name] = value
        redact.VALUES.update(value for name, value in values.items() if value and name not in PUBLIC)
        for name, value in values.items():
            if os.environ.setdefault(name, value) != value:
                _shadowed.add(name)
            _loaded.add(name)
            if os.environ[name] and name not in PUBLIC:
                redact.VALUES.add(os.environ[name])
    except (OSError, UnicodeError):
        raise ValueError('.wuwei/env: cannot read credentials file; check its permissions (chmod 600 .wuwei/env), then retry') from None


def write(root, values):
    """Set NAME=value lines in .wuwei/env (mode 0600), keeping every other line in order."""
    from wuwei import workspace
    path = Path(root) / '.wuwei/env'
    if path.is_symlink():
        raise ValueError('.wuwei/env must not be a symlink')
    for name, value in values.items():
        if name not in CREDENTIALS or not re.fullmatch(r'[^\s"\'#\\]+', value):
            raise ValueError(f'.wuwei/env: refused to write {name}')
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    lines = [line for line in lines if line.partition('=')[0].strip() not in values]
    lines += [f'{name}={value}' for name, value in values.items()]
    workspace.atomic_write(path, '\n'.join(lines) + '\n', mode=0o600)


def initialize(directory, *, dry_run=False):
    """Provision missing credentials without replacing owner values."""
    from wuwei import workspace
    directory = Path(directory)
    path, ignore = directory / 'env', directory / '.gitignore'
    if path.is_symlink() or ignore.is_symlink():
        raise ValueError(f'.wuwei/env and .gitignore must not be symlinks; {SYMLINK}')
    previous = ignore.read_text() if ignore.exists() else ''
    missing = not path.exists()
    ignored = '/env' in previous.splitlines()
    if not dry_run:
        if missing:
            workspace.atomic_write(path, '', replace=False, mode=0o600)
        if not ignored:
            workspace.atomic_write(ignore, previous.rstrip('\n') + '\n/env\n')
    return missing or not ignored
