"""The workspace: config, the hash-chained ledger, traces and small caches under .wuwei/."""

import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import tomllib

if os.name == 'nt':
    import ctypes
    import msvcrt
    import winreg
else:
    import fcntl
    import pwd

DIR = '.wuwei'
DEFAULTS = {'repos': [], 'owner_paths': [], 'prioritisation': 'wsjf', 'tracker': 'github', 'telemetry': True, 'models': {}}
GENESIS = '0' * 64
FORMAT = 1  # the ledger and verdict format; a later version still reads rows without 'v'
PLUGIN = Path(__file__).resolve().parents[2]
try:  # the harness's transcripts; never HOME or USERPROFILE, which a caller sets
    if os.name == 'nt':  # the profile Windows set at logon
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Volatile Environment') as key:
            PROJECTS = Path(winreg.QueryValueEx(key, 'USERPROFILE')[0]) / '.claude' / 'projects'
    else:
        PROJECTS = Path(pwd.getpwuid(os.getuid()).pw_dir) / '.claude' / 'projects'
except (KeyError, OSError):  # no account entry: nothing lies under /dev/null, so answers and stops record as unconfirmed
    PROJECTS = Path('/dev/null/.claude/projects')
SESSIONS = PROJECTS.parent.parent / '.codex' / 'sessions'


def find(start=None):
    """The directory holding .wuwei/, searching upward from start, or None."""
    path = Path(start or os.getcwd()).resolve()
    return next((candidate for candidate in (path, *path.parents) if (candidate / DIR).is_dir()), None)


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
    if os.mkdir not in os.supports_dir_fd:
        return _write_by_name(path, text, Path(root))
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


def _write_by_name(path, text, root):  # Windows has no dir_fd: each folder below root is held, then checked for a link
    folder, temp, held = root, f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp', []
    try:
        for part in path.parent.relative_to(root).parts:
            folder = folder / part
            with contextlib.suppress(FileExistsError):
                folder.mkdir()
            held.append(_hold(folder))
            if folder.is_symlink() or getattr(os.lstat(folder), 'st_file_attributes', 0) & 0x400:  # a reparse point: a junction
                raise OSError(f'{folder} is a link; WUWEI writes only into real folders')
        with contextlib.suppress(FileNotFoundError):  # a link planted at the temporary name is removed, never written through
            os.unlink(folder / temp)
        with open(os.open(folder / temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o666), 'wb') as out:
            out.write(text if isinstance(text, bytes) else text.encode('utf-8'))
        for wait in (0.01, 0.05, 0.2, 1, None):  # Windows refuses a replace while another writer replaces the same name
            try:
                os.replace(folder / temp, folder / path.name)
                break
            except PermissionError:
                if wait is None:
                    raise
                time.sleep(wait)
    finally:
        for handle in filter(None, held):
            _kernel().CloseHandle(ctypes.c_void_p(handle))


def _kernel():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    return kernel


def _hold(folder):  # Windows: a handle that shares no delete, so the folder is never renamed or swapped for a link while held
    if os.name != 'nt':
        return None
    handle = _kernel().CreateFileW(str(folder), 0x81, 3, None, 3, 0x02200000, None)  # list access, so its share mode binds; the link itself
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


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
    if (path := _cached(root, 'clone', '')) is None:  # the id names the ledger file: never read through a link
        raise OSError(f'{Path(root) / DIR / "cache"} or its clone entry is a link; remove the link so WUWEI can record')
    if not path.is_file() or not path.read_text(encoding='utf-8').strip().isalnum():  # a planted ../ is replaced, never followed
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


@contextlib.contextmanager
def _locked(handle):
    if os.name != 'nt':
        fcntl.flock(handle, fcntl.LOCK_EX)  # released when the handle closes
        yield
        return
    for _ in range(3):  # one byte far past the rows, so readers never block; each try waits up to 10 seconds
        os.lseek(handle.fileno(), 1 << 40, os.SEEK_SET)
        with contextlib.suppress(OSError):
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            break
    else:
        raise OSError(f'{handle.name} stayed locked; retry once the other WUWEI process ends')
    try:
        yield
    finally:
        handle.flush()
        os.lseek(handle.fileno(), 1 << 40, os.SEEK_SET)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def take(root, path):
    """Remove path as one caller's claim on it, under the ledger lock: two racing unlinks can both succeed on Windows."""
    ledger = Path(root) / DIR / 'ledger' / f'{clone(root)}.jsonl'
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, 'a+', encoding='utf-8', newline='') as handle, _locked(handle):
        Path(path).unlink()


def record(root, kind, data):
    """Append one row to this clone's file; each row carries the hash of the one before it there."""
    path = Path(root) / DIR / 'ledger' / f'{clone(root)}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a+', encoding='utf-8', newline='') as handle, _locked(handle):  # in turn (#1057), \n on every OS
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
    return [row for row in ledger(root) if row.get('kind') == kind and (day is None or row.get('ts', '').startswith(day))]


def answers(root, days=7):
    """({question, case and spacing aside: (ts, question, answer)}, context lines) for the owner's answers of the last days.
    The lines put the unrecorded first (pending, or unconfirmed with its reason), then the answers newest first."""
    found, left, done = {}, [], set()
    since = (now() - datetime.timedelta(days=days)).isoformat(timespec='seconds')
    recent = [(r.get('kind'), r.get('data') or {}, r.get('ts', '')) for r in ledger(root) if r.get('ts', '') >= since]
    for kind, d, ts in reversed(recent):  # newest first: a later row with its id settles a pending answer
        given = d['answers'] if kind == 'prompt' and isinstance(d.get('answers'), dict) else {}  # a ruling repeats its prompt row
        found = {' '.join(q.casefold().split()): (ts, q, str(a)) for q, a in given.items() if a} | found
        if kind == 'answer.unconfirmed' or kind == 'answer.pending' and d.get('id') not in done:
            left.append(f'{ts[:10]} unrecorded, ask again: {d.get("questions")!s:.100} ({d.get("reason", "pending")!s:.100})')
        done.add(d.get('id'))
    said = left + [f'{ts:.10} {q:.120} -> {a:.120}' for ts, q, a in sorted(found.values(), reverse=True)]
    return found, [' '.join(n.split()) for n in said]  # a line break in a question or answer adds no line


def trace(root, row):
    path = Path(root) / DIR / 'traces.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps({'ts': now().isoformat(timespec='seconds'), **row}, sort_keys=True) + '\n')


def traces(root, day=None):
    path = Path(root) / DIR / 'traces.jsonl'
    return [row for row in _parse(path.read_text(encoding='utf-8') if path.is_file() else '')
            if day is None or row.get('ts', '').startswith(day)]


def _cached(root, name, suffix='.json'):
    """The entry for name, or None when the name or a link would leave the workspace's own .wuwei/cache."""
    folder = Path(root) / DIR / 'cache'
    path = folder / f'{name}{suffix}'
    with contextlib.suppress(OSError, RuntimeError):  # a link loop: RuntimeError before Python 3.13, unresolved after
        same = folder.resolve() == Path(root).resolve() / DIR / 'cache' and not folder.is_symlink()  # resolve sees a junction
        if same and path.parent == folder and not path.is_symlink():
            return path
    return None


def cache_get(root, name, max_age):
    path = _cached(root, name)
    with contextlib.suppress(OSError, ValueError):
        if path and path.is_file() and now().timestamp() - path.stat().st_mtime <= max_age:
            return json.loads(path.read_text(encoding='utf-8'))
    return None


def read_json(path):  # None for a file that is missing or not JSON, including one nested past the parser's depth
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError):
        return None


def cache_prune(root, max_age, *patterns):
    for path in (p for pattern in patterns for p in (Path(root) / DIR / 'cache').glob(f'{pattern}.json')):
        with contextlib.suppress(OSError):  # only a regular file that is itself the entry for its name: never a link or a path out
            if _cached(root, path.stem) == path and path.is_file() and now().timestamp() - path.stat().st_mtime > max_age:
                path.unlink()


def cache_put(root, name, value):
    if path := _cached(root, name):  # a name or link leaving the cache is never written
        atomic_write(path, json.dumps(value))
    return value
