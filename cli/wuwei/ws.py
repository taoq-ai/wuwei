"""The workspace: config, the hash-chained ledger, traces and small caches under .wuwei/."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import tomllib

DIR = '.wuwei'
DEFAULTS = {'repos': [], 'owner_paths': [], 'prioritisation': 'wsjf', 'tracker': 'github', 'telemetry': True}
GENESIS = '0' * 64
FORMAT = 1  # the ledger and verdict format; a later version still reads rows without 'v'


def find(start=None):
    """The directory holding .wuwei/, searching upward from start, or None."""
    path = Path(start or os.getcwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / DIR).is_dir():
            return candidate
    return None


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def today():
    return now().date().isoformat()


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, path)


def raw_config(root):
    path = Path(root) / DIR / 'config.toml'
    return tomllib.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def config(root):
    """The five keys, read from the 1.0 shape or a 0.34 one ([[repos]] tables, a [prioritisation]
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
    merge = data.get('merge') if isinstance(data.get('merge'), dict) else {}
    if not data.get('owner_paths'):
        out['owner_paths'] = [p for key in ('owner_paths', 'never_auto_paths') for p in merge.get(key, [])
                              if isinstance(p, str)]
    return out


def retired(root):
    """Top-level keys and tables 1.0 does not read, and the 0.34 table shapes it rewrites."""
    data = raw_config(root)
    shapes = [key for key in DEFAULTS if isinstance(data.get(key), dict)
              or key == 'repos' and any(isinstance(r, dict) for r in data.get('repos', []))]
    return sorted(set(data) - set(DEFAULTS)) + sorted(f'{key} (0.34 shape)' for key in shapes)


def _toml(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return '[' + ', '.join(_toml(item) for item in value) + ']'
    return json.dumps(value)


def write_config(root, data):
    atomic_write(Path(root) / DIR / 'config.toml',
                 ''.join(f'{key} = {_toml(data[key])}\n' for key in DEFAULTS))


def set_config(root, key, value):
    if key not in DEFAULTS:
        raise ValueError(f'unknown key {key}; the keys are {", ".join(DEFAULTS)}')
    data = config(root)
    if isinstance(DEFAULTS[key], list):
        value = [item.strip() for item in value.split(',') if item.strip()]
    elif isinstance(DEFAULTS[key], bool):
        value = value.lower() in ('1', 'true', 'on', 'yes')
    data[key] = value
    write_config(root, data)
    return data


def _digest(row):
    body = {key: value for key, value in row.items() if key != 'hash'}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def ledger(root):
    """Every ledger row, oldest first. A row that does not parse is skipped; verify() reports it."""
    path = Path(root) / DIR / 'ledger.jsonl'
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines() if path.is_file() else ():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def record(root, kind, data):
    """Append one row; each row carries the hash of the one before it."""
    rows = ledger(root)
    row = {'v': FORMAT, 'ts': now().isoformat(timespec='seconds'), 'kind': kind, 'data': data,
           'prev': rows[-1]['hash'] if rows else GENESIS}
    row['hash'] = _digest(row)
    path = Path(root) / DIR / 'ledger.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, sort_keys=True) + '\n')
    return row


def verify(root):
    """Line numbers where the hash chain breaks; empty means the ledger is intact."""
    path = Path(root) / DIR / 'ledger.jsonl'
    broken, prev = [], GENESIS
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines() if path.is_file() else (), 1):
        try:
            row = json.loads(line)
            ok = row['prev'] == prev and row['hash'] == _digest(row)
            prev = row['hash']
        except (ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            broken.append(number)
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
    out = []
    for line in path.read_text(encoding='utf-8').splitlines() if path.is_file() else ():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if day is None or row.get('ts', '').startswith(day):
            out.append(row)
    return out


def cache_get(root, name, max_age):
    path = Path(root) / DIR / 'cache' / f'{name}.json'
    try:
        if now().timestamp() - path.stat().st_mtime <= max_age:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    return None


def cache_put(root, name, value):
    atomic_write(Path(root) / DIR / 'cache' / f'{name}.json', json.dumps(value))
    return value
