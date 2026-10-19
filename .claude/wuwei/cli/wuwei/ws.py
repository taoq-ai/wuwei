"""The workspace: config, the hash-chained ledger, traces and small caches under .wuwei/."""

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import threading
import tomllib

DIR = '.wuwei'
DEFAULTS = {'repos': [], 'owner_paths': [], 'prioritisation': 'wsjf', 'tracker': 'github', 'telemetry': True, 'models': {}}
GENESIS = '0' * 64
FORMAT = 1  # the ledger and verdict format; a later version still reads rows without 'v'
PLUGIN = Path(__file__).resolve().parents[2]


def find(start=None):
    """The directory holding .wuwei/, searching upward from start, or None."""
    path = Path(start or os.getcwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / DIR).is_dir():
            return candidate
    return None


def version():
    return json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def today():
    return now().date().isoformat()


def atomic_write(path, text, root=None):  # every folder below root and the file are reached by descriptor: no link is followed
    path = Path(path)
    if root is None:  # by default the file's own folder, made first
        root, _ = path.parent, path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = os.open(root, os.O_RDONLY | os.O_DIRECTORY), f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp'  # threads share a pid (#1121)
    try:
        for part in path.parent.relative_to(root).parts:
            with contextlib.suppress(FileExistsError):
                os.mkdir(part, dir_fd=fd)
            fd, up = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd), fd
            os.close(up)
        with contextlib.suppress(FileNotFoundError):  # a link planted at the temporary name is removed, never written through
            os.unlink(temp, dir_fd=fd)
        with open(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666, dir_fd=fd), 'wb') as out:
            out.write(text if isinstance(text, bytes) else text.encode('utf-8'))
        os.replace(temp, path.name, src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        os.close(fd)


def raw_config(root):
    path = Path(root) / DIR / 'config.toml'
    return tomllib.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def config(root):
    """The six keys, read from the 1.0 shape or a 0.34 one ([[repos]] tables, a [prioritisation]
    table, [merge] owner paths, a [telemetry] table)."""
    data = raw_config(root)
    out = {**DEFAULTS, **{key: value for key, value in data.items() if key in DEFAULTS}}
    out['repos'] = [r['name'] if isinstance(r, dict) else r for r in out['repos'] if isinstance(r, (str, dict))
                    and (isinstance(r, str) or isinstance(r.get('name'), str))]
    if isinstance(out['prioritisation'], dict):
        out['prioritisation'] = out['prioritisation'].get('framework', DEFAULTS['prioritisation'])
    if isinstance(out['tracker'], dict):
        out['tracker'] = DEFAULTS['tracker']
    if isinstance(out['telemetry'], dict):
        out['telemetry'] = out['telemetry'].get('mode', 'on') not in ('off', 'false')
    out['models'] = {k: v for k, v in out['models'].items() if isinstance(v, str) and len(v.split()) > 1} if isinstance(out['models'], dict) else {}
    merge = data.get('merge') if isinstance(data.get('merge'), dict) else {}
    if not data.get('owner_paths'):
        out['owner_paths'] = [p for key in ('owner_paths', 'never_auto_paths') for p in merge.get(key, [])
                              if isinstance(p, str)]
    return out


def retired(root):
    """Top-level keys and tables 1.0 does not read, and the 0.34 table shapes it rewrites."""
    data = raw_config(root)
    shapes = [key for key in DEFAULTS if isinstance(data.get(key), dict) and key != 'models'
              or key == 'repos' and any(isinstance(r, dict) for r in data.get('repos', []))]
    return sorted(set(data) - set(DEFAULTS)) + sorted(f'{key} (0.34 shape)' for key in shapes)


def _toml(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return '[' + ', '.join(_toml(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join(f'{json.dumps(k)} = {_toml(v)}' for k, v in value.items()) + '}'
    return json.dumps(value)


def write_config(root, data):
    atomic_write(Path(root) / DIR / 'config.toml',
                 ''.join(f'{key} = {_toml(data.get(key, DEFAULTS[key]))}\n'
                         for key in DEFAULTS if key != 'models' or data.get(key)))


def set_config(root, key, value):
    if key not in DEFAULTS:
        raise ValueError(f'unknown key {key}; the keys are {", ".join(DEFAULTS)}')
    data = config(root)
    if isinstance(DEFAULTS[key], list):
        value = [item.strip() for item in value.split(',') if item.strip()]
    elif isinstance(DEFAULTS[key], bool):
        value = value.lower() in ('1', 'true', 'on', 'yes')
    elif isinstance(DEFAULTS[key], dict):  # models: "<role>[ <tier>]=<model> <effort>, ..."
        value = {k.strip(): v.strip() for k, _, v in (part.partition('=') for part in value.split(',')) if k.strip() and len(v.split()) > 1}
    data[key] = value
    write_config(root, data)
    return data


def _digest(row):
    body = {key: value for key, value in row.items() if key != 'hash'}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def clone(root):
    """This clone's id. Each clone appends only to its own ledger file, so two sessions syncing
    through git never edit the same rows."""
    path = Path(root) / DIR / 'cache' / 'clone'
    if not path.is_file():
        atomic_write(path, os.urandom(4).hex() + '\n')
    return path.read_text(encoding='utf-8').strip()


def _ledgers(root):
    """The 0.34-era single file, then one file per clone."""
    base = Path(root) / DIR
    return [path for path in (base / 'ledger.jsonl', *sorted((base / 'ledger').glob('*.jsonl'))) if path.is_file()]


def _parse(text):
    """The well-formed rows: JSON objects whose ts and kind, where present, are strings and data an object."""
    rows = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and all(isinstance(row.get(k, t()), t) for k, t in (('ts', str), ('kind', str), ('data', dict))):
            rows.append(row)
    return rows


def ledger(root):
    """Every ledger row from every file, oldest first. A malformed row is skipped; verify() reports it."""
    return sorted((row for path in _ledgers(root) for row in _parse(path.read_text(encoding='utf-8'))), key=lambda row: row.get('ts', ''))


def record(root, kind, data):
    """Append one row to this clone's file; each row carries the hash of the one before it there."""
    path = Path(root) / DIR / 'ledger' / f'{clone(root)}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a+', encoding='utf-8') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)  # seats starting at once append in turn, each after the last (#1057)
        handle.seek(0)
        mine = _parse(handle.read())
        row = {'v': FORMAT, 'ts': now().isoformat(timespec='seconds'), 'kind': kind, 'data': data,
               'prev': next((r['hash'] for r in reversed(mine) if isinstance(r.get('hash'), str)), GENESIS)}
        row['hash'] = _digest(row)
        handle.write(json.dumps(row, sort_keys=True) + '\n')
    return row


def verify(root):
    """Where a hash chain breaks, as file:line; empty means every ledger file is intact."""
    broken = []
    for path in _ledgers(root):
        prev = GENESIS
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            try:
                row = json.loads(line)
                ok = row['prev'] == prev and row['hash'] == _digest(row)
                prev = row['hash']
            except (ValueError, KeyError, TypeError):
                ok = False
            if not ok:
                broken.append(f'{path.relative_to(Path(root) / DIR).as_posix()}:{number}')
    return broken


def rows(root, kind, day=None):
    return [row for row in ledger(root)
            if row.get('kind') == kind and (day is None or row.get('ts', '').startswith(day))]


def trace(root, row):
    path = Path(root) / DIR / 'traces.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps({'ts': now().isoformat(timespec='seconds'), **row}, sort_keys=True) + '\n')


def traces(root, day=None):
    path = Path(root) / DIR / 'traces.jsonl'
    return [row for row in _parse(path.read_text(encoding='utf-8') if path.is_file() else '')
            if day is None or row.get('ts', '').startswith(day)]


def cache_get(root, name, max_age):
    path = Path(root) / DIR / 'cache' / f'{name}.json'
    try:
        if now().timestamp() - path.stat().st_mtime <= max_age:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    return None


def cache_prune(root, max_age, *patterns):
    for path in (p for pattern in patterns for p in (Path(root) / DIR / 'cache').glob(f'{pattern}.json')):
        try:
            if now().timestamp() - path.stat().st_mtime > max_age:
                path.unlink()
        except OSError:
            pass


def cache_put(root, name, value):
    atomic_write(Path(root) / DIR / 'cache' / f'{name}.json', json.dumps(value))
    return value
