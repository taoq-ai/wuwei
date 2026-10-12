"""The single writer for day state and append-only events."""

import fcntl
import json
import os
from pathlib import Path
from time import monotonic as _monotonic, sleep as _sleep

from wuwei import workspace
from wuwei.exits import DAMAGED, RACE


def lock_ex(lock, name, timeout=30):
    """Bound state and brief lock waits so an abandoned holder prints a reason."""
    deadline = _monotonic() + timeout
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if _monotonic() >= deadline:
                raise TimeoutError(f'{name} remained locked for {timeout}s; retry after the other wuwei command finishes') from None
            _sleep(0.1)


PHASES = {
    'planned': ('spec', 'implement', 'raised', 'parked', 'escalated'),
    'spec': ('implement', 'parked', 'escalated'),
    'implement': ('gate', 'parked', 'escalated'),
    'gate': ('raised', 'fix', 'parked', 'escalated'),
    'fix': ('delta', 'merged', 'parked', 'escalated'),
    'delta': ('raised', 'fix', 'merged', 'parked', 'escalated'),
    'raised': ('fix', 'merged', 'parked', 'escalated'),
    'parked': ('planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta'),
    'escalated': ('planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta'),
    'merged': (),
}
BUILD_PHASES = ('spec', 'implement', 'fix')
STATUSES = ('queued', 'running', 'blocked', 'done')
DAY_DEFAULTS = {'items': {}, 'cap': 1, 'cap_bound': '', 'seat_policy': {}, 'envelope': {},
                'claimed_prs': [], 'raised_prs': [], 'gate_verdicts': {}, 'seats': {},
                'gate_approved': False, 'approved_items': [], 'goals': []}
ITEM_DEFAULTS = {'lane': 'build', 'status': 'queued', 'phase': 'planned',
                 'flags': {'trust_surface': False, 'boundary_relevant': False,
                           'agent_surface': False}, 'gates': {}, 'note': ''}


class StateError(ValueError):
    """A schema or lifecycle finding (exit 1)."""


def _defaults(value, defaults, path):
    if not isinstance(value, dict):
        raise StateError(f'{path}: expected object; {DAMAGED}')
    for key, default in defaults.items():
        if key not in value:
            value[key] = workspace.copy_data(default)
        if type(value[key]) is not type(default):
            raise StateError(f'{path}.{key}: expected {type(default).__name__}; {DAMAGED}')


def _validate(data, previous=None):
    _defaults(data, DAY_DEFAULTS, 'state')
    if data['cap'] < 1:
        raise StateError('cap: expected integer >= 1; pass a cap of 1 or more')
    if previous is not None and previous['items'].keys() - data['items'].keys():
        raise StateError('items: removing an item is not allowed; run bin/wuwei plan park <item> to set an item aside instead')
    for field in ('raised_prs', 'claimed_prs'):
        if previous is not None and any(ref not in data[field] for ref in previous[field]):
            raise StateError(f'{field}: removing a PR is not allowed; run bin/wuwei plan park <item> to set the item aside instead')
    for name, item in data['items'].items():
        path = f'items.{name}'
        _defaults(item, ITEM_DEFAULTS, path)
        _defaults(item['flags'], ITEM_DEFAULTS['flags'], f'{path}.flags')
        if item['status'] not in STATUSES:
            raise StateError(f'{path}.status: expected {", ".join(STATUSES)}; {DAMAGED}')
        old = previous['items'].get(name) if previous is not None else None
        if previous is not None and old is None and item['phase'] != 'planned':
            raise StateError(f'{path}.phase: new items must start at planned; {DAMAGED}')
        if old is not None:
            if old['phase'] != item['phase']:
                if item['phase'] in ('parked', 'escalated'):
                    item['resume_phase'] = old['phase']
                else:
                    item.pop('resume_phase', None)
            elif item.get('resume_phase') != old.get('resume_phase'):
                raise StateError(f'{path}.resume_phase: managed by transitions; {DAMAGED}')
        if item['phase'] not in PHASES:
            raise StateError(f'{path}.phase: expected {", ".join(PHASES)}; {DAMAGED}')
        if item['phase'] in ('parked', 'escalated'):
            if item.get('resume_phase') not in PHASES[item['phase']]:
                raise StateError(f'{path}.resume_phase: expected the prior active phase; {DAMAGED}')
        elif 'resume_phase' in item:
            raise StateError(f'{path}.resume_phase: only valid while paused; {DAMAGED}')
    return data


def _diff(old, new):
    """#844: the patch one write made: whole top-level values, and for object values only the
    changed entries (merge) and the removed ones (drop)."""
    patch = {}
    for key, value in new.items():
        before = old.get(key, _MISSING)
        if before == value:
            continue
        if isinstance(value, dict) and isinstance(before, dict):
            changed = {entry: row for entry, row in value.items() if before.get(entry, _MISSING) != row}
            dropped = [entry for entry in before if entry not in value]
            if changed:
                patch.setdefault('merge', {})[key] = changed
            if dropped:
                patch.setdefault('drop', {})[key] = dropped
        else:
            patch.setdefault('set', {})[key] = value
    if removed := [key for key in old if key not in new]:
        patch['del'] = removed
    return patch


_MISSING = object()


def _apply(data, patch):
    for key, value in patch.get('set', {}).items():
        data[key] = value
    for key, entries in patch.get('merge', {}).items():
        if not isinstance(data.get(key), dict):
            data[key] = {}
        data[key].update(entries)
    for key, entries in patch.get('drop', {}).items():
        for entry in entries:
            data.get(key, {}).pop(entry, None)
    for key in patch.get('del', ()):
        data.pop(key, None)


CACHE_KEYS = ('log_size', 'log_head', 'digest')


def _fingerprint(encoded):
    """A deterministic fingerprint without hashlib on the hook path (#346): Python's integer
    hash is not salted per process. ponytail: not cryptographic; it detects edits, not forgery."""
    return format(hash(int.from_bytes(b'\x01' + encoded, 'big')) & 0xFFFFFFFFFFFFFFFF, 'x')


def _digest(data):
    """The records' fingerprint the cache carries: an edit to state.json breaks it (F7)."""
    return _fingerprint(json.dumps(data, sort_keys=True, allow_nan=False).encode())


def _log_head(log):
    """The log's identity: its first line's fingerprint (F8); a replaced log has another."""
    try:
        with log.open('rb') as handle:
            return _fingerprint(handle.readline())
    except FileNotFoundError:
        return ''


def _fold(directory, cache=True):
    """#844: (the day's records, whether the day started, whether they came from outside the
    log); cache False folds the log alone. The event log is the truth and state.json its cache,
    read only when its fingerprint holds (no hand edit), it names this log (the first line) and
    the log reached its size; only the tail past that size is folded onto it. A state.json
    without a log size is an old day's records, read only while the log holds no patch; the next
    write's patch carries it into the log. A line that does not parse is a write that never
    finished (it never reached the cache) and is skipped."""
    path, log = directory / 'state.json', directory / 'events.jsonl'
    try:
        raw = json.loads(path.read_text(encoding='utf-8')) if cache else None
    except FileNotFoundError:
        raw = None
    except ValueError:
        if not day_started(directory, log_only=True):
            raise
        raw = None  # a torn cache: the log has the records
    if raw is not None and not isinstance(raw, dict):
        if not day_started(directory, log_only=True):
            raise ValueError(f'expected object; {DAMAGED}')
        raw = None
    size = log.stat().st_size if log.is_file() else 0
    if isinstance(raw, dict) and 'log_size' not in raw:
        if not day_started(directory, log_only=True):
            return raw, True, True
        raw = None  # F6: once the log holds records it wins over an edited file
    offset = -1
    if isinstance(raw, dict):
        meta = {key: raw.pop(key, None) for key in CACHE_KEYS}
        if (isinstance(meta['log_size'], int) and meta['digest'] == _digest(raw)
                and meta['log_head'] == _log_head(log)):
            offset = meta['log_size']
    if offset > size:  # the log lost lines the cache holds: keep the records, never fewer
        return raw, True, True
    if offset >= 0:
        data, started = raw, True
    else:
        data, offset, started = workspace.copy_data(DAY_DEFAULTS), 0, False
    if offset < size:
        with log.open('rb') as handle:
            handle.seek(offset)
            tail = handle.read(size - offset)
        for line in tail.splitlines():
            if b'"patch"' not in line:
                continue
            try:
                patch = json.loads(line).get('patch')
            except (ValueError, AttributeError):
                continue  # F4: a torn write recorded nothing
            if isinstance(patch, dict):
                _apply(data, patch)
                started = True
    return data, started, False


def day_started(directory, log_only=False):
    """#844: True once the day holds records (its log carries a patch, or an old day's
    state.json exists); replaces every state.json existence check."""
    directory = Path(directory)
    if not log_only and (directory / 'state.json').is_file():
        return True
    log = directory / 'events.jsonl'
    return log.is_file() and b'"patch"' in log.read_bytes()


def read_state(root=None, *, directory=None):
    """Read today's records, folded from the event log (#844); a day without records returns
    fresh defaults without writes."""
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    try:
        data = _fold(directory)[0]
        json.dumps(data, allow_nan=False)
        return _validate(data)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{directory / "state.json"}: {exc}; run bin/wuwei doctor') from exc


def _event_payload(kind, payload):
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError(f'event kind must be a nonempty string; {DAMAGED}')
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise ValueError(f'event payload must be an object; {DAMAGED}')
    json.dumps(payload, allow_nan=False)
    return payload


def append_event(kind, payload=None, root=None, *, directory=None, timeout=30):
    """Append one event using the shared clock, never a caller timestamp."""
    payload = _event_payload(kind, payload)
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    directory.parent.mkdir(exist_ok=True)
    directory.mkdir(exist_ok=True)
    with (directory / 'state.lock').open('a') as lock:
        lock_ex(lock, 'state.lock', timeout)
        _append_event(kind, payload, directory)


def _append_event(kind, payload, directory, patch=None):
    """Append validated event data while the caller holds state.lock. patch (#844): the
    records a state write changed, carried beside the payload."""
    row = {'kind': kind, 'payload': payload, 'ts': workspace.now().isoformat()}
    if patch is not None:
        row['patch'] = patch
    _append_jsonl(directory / 'events.jsonl', row)


def append_jsonl(path, record):
    """Append a JSON record under the same lock used by events and state."""
    path = Path(path)
    path.parent.parent.mkdir(exist_ok=True)
    path.parent.mkdir(exist_ok=True)
    with (path.parent / 'state.lock').open('a') as lock:
        lock_ex(lock, 'state.lock')
        _append_jsonl(path, record)


def _append_jsonl(path, *records):
    """Write the records' lines in one write under state.lock, leaving events and traces read-only."""
    from wuwei.redact import known_values
    encoded = ''.join(json.dumps(known_values(record), allow_nan=False) + '\n'
                      for record in records).encode('utf-8')
    if path.is_file():
        path.chmod(0o600)
    try:
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_RDWR, 0o444)
        try:
            os.fchmod(fd, 0o444)
            previous_size = os.fstat(fd).st_size
            try:
                if previous_size and os.pread(fd, 1, previous_size - 1) != b'\n':
                    encoded = b'\n' + encoded
                if os.write(fd, encoded) != len(encoded):
                    raise OSError(f'short event write to {path.name}; free disk space, then run the same command again')
            except OSError:
                # Discard only the failed append while holding the shared writer lock.
                os.ftruncate(fd, previous_size)
                raise
        finally:
            os.close(fd)
    finally:
        if path.is_file():
            path.chmod(0o444)


def _write_state(update, root=None, *, kind='state.write', payload=None, directory=None, timeout=30):
    """Apply a callback that mutates fresh state while holding the writer lock."""
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    payload = _event_payload(kind, payload)
    directory.parent.mkdir(exist_ok=True)
    directory.mkdir(exist_ok=True)
    # ponytail: POSIX-only sidecar flock; add a platform adapter if Windows is required.
    with (directory / 'state.lock').open('a') as lock:
        lock_ex(lock, 'state.lock', timeout)
        data, started, legacy = _fold(directory)
        log = _fold(directory, cache=False)[0] if legacy else workspace.copy_data(data)
        data = _validate(data)
        previous = workspace.copy_data(data) if started else None
        update(data)
        data = _validate(data, previous)
        json.dumps(data, allow_nan=False)
        changes = {name: item['phase'] for name, item in data['items'].items()
                   if previous is not None and name in previous['items']
                   and item['phase'] != previous['items'][name]['phase']}
        seen = bool(data['raised_prs'] or data['claimed_prs'])
        # #844: the event carries the patch first; state.json is the cache of the fold after it.
        _append_event(kind, {**payload, 'prs_seen': seen, **({'phase_changes': changes} if changes else {})},
                      directory, patch=_diff(log, data) or None)
        log = directory / 'events.jsonl'
        encoded = json.dumps({**data, 'log_size': log.stat().st_size, 'log_head': _log_head(log),
                              'digest': _digest(data)}, allow_nan=False) + '\n'
        workspace.atomic_write(directory / 'state.json', encoded, mode=0o444)
        return data


def check_running(build):
    """The build's fast-check marker while another live process runs it, else None.
    The current process is never "another": a check that raised in this process is over.
    ponytail: pid liveness; a reused pid reads as running until it exits. Upgrade: store the
    process start time with the pid and compare it."""
    marker = build.get('check') if isinstance(build, dict) else None
    if not (isinstance(marker, dict) and type(marker.get('pid')) is int and marker['pid'] > 0
            and marker['pid'] != os.getpid() and isinstance(marker.get('started_at'), str)):
        return None
    try:
        os.kill(marker['pid'], 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    return marker


def looping(build):
    """#845: a routed build's background loop (`wuwei build`) while its process lives."""
    return check_running({'check': build.get('loop')}) if isinstance(build, dict) else None


def held(data, name):
    """#648: the fix item a held build waits on while that item has not ended, else None."""
    action = (data.get('builds', {}).get(name) or {}).get('action') or {}
    fix = action.get('fix') if action.get('action') == 'wait' else None
    ended = data['items'].get(fix, {}).get('phase') in ('merged', 'parked', 'escalated')
    return fix if fix and not ended else None


def mid_round(data):
    """Items between a FIX and its delta review (#624): the steward waits for them."""
    return sorted(name for name, item in data.get('items', {}).items() if item.get('phase') in ('fix', 'delta'))


def in_flight(data):
    """(started_at, role, item) for running seats and live fast checks, oldest first."""
    rows = [(seat.get('started_at') or '', seat.get('role'), seat.get('item'))
            for seat in data.get('seats', {}).values()
            if isinstance(seat, dict) and seat.get('status') == 'running']
    rows += [(marker['started_at'], 'checks', item) for item, build in data.get('builds', {}).items()
             if (marker := check_running(build))]
    rows += [(marker['started_at'], 'builder', item) for item, build in data.get('builds', {}).items()
             if (marker := looping(build))]
    return sorted(rows, key=lambda row: row[0])


def in_flight_text(rows):
    return ', '.join(f'{role} {item} {at[11:16] if at else "start unrecorded"}'
                     for at, role, item in rows)


def record_pr(root, item, ref, *, raised, head=None, reviewers=None, draft=False, branch=None, built=False):
    """Link one owned PR to its item in the same write as day ownership. built (#901, build
    reconcile): a claimed planned item goes to implement, so its checks and gates still run."""
    from wuwei.references import pull_request
    ref = pull_request(ref)
    def update(data):
        if item not in data['items'] or item not in data['approved_items']:
            raise StateError('PR item must be in the approved plan; admit the item with bin/wuwei plan add <item> first')
        if data['items'][item].get('pr') not in (None, ref):
            raise StateError('item already links another PR; run bin/wuwei why <item> to see the linked PR')
        if any(name != item and row.get('pr') == ref for name, row in data['items'].items()):
            raise StateError('PR already links another item; run bin/wuwei pr state to see which item owns it')
        other = 'claimed_prs' if raised else 'raised_prs'
        if ref in data[other]:
            raise StateError('PR is already owned today; run bin/wuwei pr state to see its item')
        data['items'][item]['pr'] = ref
        if branch:  # #879: the claimed PR's head branch, which the edges guard keeps to the gated push
            data['items'][item]['branch'] = branch
        field = 'raised_prs' if raised else 'claimed_prs'
        if ref not in data[field]:
            data[field].append(ref)
        if reviewers is not None:
            data.setdefault('pr_reviewers', {})[ref] = reviewers
        if raised and data['items'][item]['phase'] in ('gate', 'delta'):
            _move(data, item, 'raised')
        if not raised and data['items'][item]['phase'] == 'planned':
            _move(data, item, 'implement' if built else 'raised')  # #510: a claimed PR is never built afresh.
    payload = {'pr': ref, 'item': item}
    if head is not None:
        payload['head'] = head
    if reviewers is not None:
        payload['reviewers'] = reviewers
    if draft:
        payload['draft'] = True
    if raised:
        return _write_state(update, root, kind='pr.raised', payload=payload)
    return _write_state(update, root, kind='pr.claimed', payload=payload)


def record_worktree(root, item, path, head, *, check=False):
    """Record an adopted or checked-out worktree as the item's (#510); check=True only
    reads the preconditions, before any side effect."""
    path = str(path)
    def update(data):
        if item not in data['items'] or item not in data['approved_items']:
            raise StateError('worktree item must be in the approved plan; admit the item with bin/wuwei plan add <item> first')
        recorded = data['items'][item].get('worktree')
        if recorded and Path(recorded).resolve() != Path(path).resolve():
            raise StateError(f'item already records another worktree ({recorded}); run bin/wuwei why {item}')
        other = next((name for name, row in data['items'].items() if name != item and row.get('worktree')
                      and Path(row['worktree']).resolve() == Path(path).resolve()), None)
        if other:
            raise StateError(f'item {other} already records worktree {path}; run bin/wuwei why {other}')
        data['items'][item]['worktree'] = path
    if check:
        return update(read_state(root))
    return _write_state(update, root, kind='worktree.adopted',
                        payload={'item': item, 'worktree': path, 'head': head})


def _move(data, item, phase):
    current = data['items'][item]
    if current['phase'] == 'delta' and phase == 'raised' and item in data.get('builds', {}):
        data['builds'][item]['fix_rounds'] = 0
    current['phase'] = phase
    if phase == 'merged':
        current['status'] = 'done'


def transition(item, phase, root=None):
    def update(data):
        if item not in data['items']:
            raise KeyError(f'no state item: {item}')
        _move(data, item, phase)

    return _write_state(update, root, kind='state.transition',
                       payload={'item': item, 'phase': phase})


def stop_seat(name, root=None, *, directory=None, agent_id=None, reason=None, by=None, report=None,
              expected=None):
    """Release a reservation while preserving the used brief and seat identity; with a reason
    the seat is unmeasured: its report could not be recorded (#473), and report is where it
    is kept for wuwei seat stop --verdict, with its sha256 (#905: brief.keep_report). expected: the seat record the stop read; a
    seat changed since (a relaunch, a recorded result) is left as it is."""
    fields = {'reason': reason} if reason else {}
    if by:
        fields['by'] = by
    fields.update(report or {})

    def update(data):
        seat = data['seats'][name]
        if expected is not None and seat != expected:
            raise ValueError(f'seat {name} changed during its stop; {RACE}')
        for key in ('reason', 'by', 'report', 'report_sha256'):
            seat.pop(key, None)
        seat.update(status='unmeasured' if reason else 'stopped', stopped_at=workspace.now().isoformat(),
                    **fields)
        if isinstance(agent_id, str) and agent_id.strip():
            seat['agent_id'] = agent_id
    payload = {'name': name, **({'status': 'unmeasured'} if reason else {}), **fields}
    return _write_state(update, root, kind='seat stopped', payload=payload, directory=directory)
