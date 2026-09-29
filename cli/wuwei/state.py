"""The single writer for day state and append-only events."""

from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path

from wuwei import workspace


PHASES = {
    'planned': ('spec', 'implement', 'parked', 'escalated'),
    'spec': ('implement', 'parked', 'escalated'),
    'implement': ('gate', 'parked', 'escalated'),
    'gate': ('raised', 'fix', 'parked', 'escalated'),
    'fix': ('delta', 'parked', 'escalated'),
    'delta': ('raised', 'fix', 'parked', 'escalated'),
    'raised': ('fix', 'merged', 'parked', 'escalated'),
    'parked': ('planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta'),
    'escalated': ('planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta'),
    'merged': (),
}
BUILD_PHASES = ('spec', 'implement', 'fix')
STATUSES = ('queued', 'running', 'blocked', 'done')
DAY_DEFAULTS = {'items': {}, 'cap': 1, 'seat_policy': {}, 'envelope': {},
                'claimed_prs': [], 'raised_prs': [], 'gate_verdicts': {}, 'seats': {},
                'gate_approved': False, 'approved_items': [], 'goals': []}
ITEM_DEFAULTS = {'lane': 'build', 'status': 'queued', 'phase': 'planned',
                 'flags': {'trust_surface': False, 'boundary_relevant': False,
                           'agent_surface': False}, 'gates': {}, 'note': ''}


class StateError(ValueError):
    """A schema or lifecycle finding (exit 1)."""


def _defaults(value, defaults, path):
    if not isinstance(value, dict):
        raise StateError(f'{path}: expected object')
    for key, default in defaults.items():
        value.setdefault(key, deepcopy(default))
        if type(value[key]) is not type(default):
            raise StateError(f'{path}.{key}: expected {type(default).__name__}')


def _check_transition(item, target):
    phase = item['phase']
    allowed = PHASES[phase]
    if phase in ('parked', 'escalated'):
        allowed = (item['resume_phase'],)
    if target not in allowed:
        raise StateError(f'{phase} -> {target}: legal next phases: '
                         f'{", ".join(allowed) or "none (terminal)"}'
                         + (f'; state may already be at {target}' if phase == target else ''))


def _validate(data, previous=None):
    _defaults(data, DAY_DEFAULTS, 'state')
    if data['cap'] < 1:
        raise StateError('cap: expected integer >= 1')
    if previous is not None and previous['items'].keys() - data['items'].keys():
        raise StateError('items: removing an item is not allowed')
    for field in ('raised_prs', 'claimed_prs'):
        if previous is not None and any(ref not in data[field] for ref in previous[field]):
            raise StateError(f'{field}: removing a PR is not allowed')
    for name, item in data['items'].items():
        path = f'items.{name}'
        _defaults(item, ITEM_DEFAULTS, path)
        _defaults(item['flags'], ITEM_DEFAULTS['flags'], f'{path}.flags')
        if item['status'] not in STATUSES:
            raise StateError(f'{path}.status: expected {", ".join(STATUSES)}')
        old = previous['items'].get(name) if previous is not None else None
        if previous is not None and old is None and item['phase'] != 'planned':
            raise StateError(f'{path}.phase: new items must start at planned')
        if old is not None:
            if old['phase'] != item['phase']:
                _check_transition(old, item['phase'])
                if item['phase'] in ('parked', 'escalated'):
                    item['resume_phase'] = old['phase']
                else:
                    item.pop('resume_phase', None)
            elif item.get('resume_phase') != old.get('resume_phase'):
                raise StateError(f'{path}.resume_phase: managed by transitions')
        if item['phase'] not in PHASES:
            raise StateError(f'{path}.phase: expected {", ".join(PHASES)}')
        if item['phase'] in ('parked', 'escalated'):
            if item.get('resume_phase') not in PHASES[item['phase']]:
                raise StateError(f'{path}.resume_phase: expected the prior active phase')
        elif 'resume_phase' in item:
            raise StateError(f'{path}.resume_phase: only valid while paused')
    return data


def read_state(root=None, *, directory=None):
    """Read today's state; an absent file returns fresh defaults without writes."""
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    path = directory / 'state.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        json.dumps(data, allow_nan=False)
        return _validate(data)
    except FileNotFoundError:
        return deepcopy(DAY_DEFAULTS)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{path}: {exc}') from exc


def _event_payload(kind, payload):
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError('event kind must be a nonempty string')
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise ValueError('event payload must be an object')
    json.dumps(payload, allow_nan=False)
    return payload


def append_event(kind, payload=None, root=None, *, directory=None):
    """Append one event using the shared clock, never a caller timestamp."""
    payload = _event_payload(kind, payload)
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    directory.parent.mkdir(exist_ok=True)
    directory.mkdir(exist_ok=True)
    with (directory / 'state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _append_event(kind, payload, directory)


def _append_event(kind, payload, directory):
    """Append validated event data while the caller holds state.lock."""
    record = {'kind': kind, 'payload': payload,
              'ts': workspace.now().isoformat()}
    _append_jsonl(directory / 'events.jsonl', record)


def append_jsonl(path, record):
    """Append a JSON record under the same lock used by events and state."""
    path = Path(path)
    path.parent.parent.mkdir(exist_ok=True)
    path.parent.mkdir(exist_ok=True)
    with (path.parent / 'state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _append_jsonl(path, record)


def _append_jsonl(path, record):
    """Write one line under state.lock, leaving events and traces read-only."""
    encoded = (json.dumps(record, allow_nan=False) + '\n').encode('utf-8')
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
                    raise OSError(f'short event write to {path.name}')
            except OSError:
                # Discard only the failed append while holding the shared writer lock.
                os.ftruncate(fd, previous_size)
                raise
        finally:
            os.close(fd)
    finally:
        if path.is_file():
            path.chmod(0o444)


def _write_state(update, root=None, *, reserved=True, kind='state.write', payload=None, directory=None):
    """Apply a callback that mutates fresh state while holding the writer lock."""
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    payload = _event_payload(kind, payload)
    directory.parent.mkdir(exist_ok=True)
    directory.mkdir(exist_ok=True)
    # ponytail: POSIX-only sidecar flock; add a platform adapter if Windows is required.
    with (directory / 'state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = read_state(directory=directory)
        previous = deepcopy(data) if (directory / 'state.json').exists() else None
        trusted_before = _reserved(data)
        update(data)
        if reserved and _reserved(data) != trusted_before:
            raise StateError('reserved state fields require a dedicated producer')
        data = _validate(data, previous)
        encoded = json.dumps(data, allow_nan=False) + '\n'
        workspace.atomic_write(directory / 'state.json', encoded, mode=0o444)
        _append_event(kind, {**payload, 'prs_seen': bool(data['raised_prs'] or data['claimed_prs'])},
                      directory)
        return data


# Features add only the namespaces they own.
RESERVED = {'seats', 'fast_checks', 'reply_acks', 'channel_posts', 'decision_outcomes',
            'gate_approved', 'approved_items', 'goals', 'cap', 'seat_policy', 'envelope', 'watch',
            'planner_session_id'}


def _reserved(data, path=()):
    records = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if key in RESERVED and (key not in {'cap', 'seat_policy', 'envelope'} or data.get('gate_approved')):
                records[(*path, key)] = deepcopy(value)
            else:
                records.update(_reserved(value, (*path, key)))
    elif isinstance(data, (list, tuple)):
        for index, value in enumerate(data):
            records.update(_reserved(value, (*path, index)))
    return records


def write_state(update, root=None, *, kind='state.write', payload=None):
    """Generic writes cannot change namespaces reserved by dedicated producers."""
    return _write_state(update, root, kind=kind, payload=payload)


def _parts(path):
    parts = path.split('.')
    if not all(parts):
        raise ValueError('path must contain nonempty dot-separated keys')
    return parts


def get_state(path=None, root=None):
    value = read_state(root)
    if path is not None:
        for key in _parts(path):
            if not isinstance(value, dict) or key not in value:
                raise KeyError(f'no state path: {path}')
            value = value[key]
    return value


def set_state(path, value, root=None):
    parts = _parts(path)
    if RESERVED.intersection(parts) and (not RESERVED.intersection(parts) <= {'cap', 'seat_policy', 'envelope'}
                                        or read_state(root).get('gate_approved')):
        raise StateError('reserved state path requires a dedicated producer')

    def update(data):
        parent = data
        for key in parts[:-1]:
            if not isinstance(parent, dict):
                raise ValueError(f'non-object parent in path: {path}')
            parent = parent.setdefault(key, {})
        if not isinstance(parent, dict):
            raise ValueError(f'non-object parent in path: {path}')
        parent[parts[-1]] = value

    return write_state(update, root, kind='state.set', payload={'path': path, 'value': value})


def transition(item, phase, root=None):
    def update(data):
        if item not in data['items']:
            raise KeyError(f'no state item: {item}')
        current = data['items'][item]
        _check_transition(current, phase)
        current['phase'] = phase

    return write_state(update, root, kind='state.transition',
                       payload={'item': item, 'phase': phase})


def stop_seat(name, root=None, *, directory=None):
    """Release a reservation while preserving the used brief and seat identity."""
    def update(data):
        data['seats'][name]['status'] = 'stopped'
    return _write_state(update, root, reserved=False, kind='seat stopped',
                        payload={'name': name}, directory=directory)
