"""The single writer for day state and append-only events."""

from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile

from wuwei import workspace


PHASES = {
    'planned': ('spec', 'implement', 'parked', 'escalated'),
    'spec': ('implement', 'parked', 'escalated'),
    'implement': ('gate', 'parked', 'escalated'),
    'gate': ('raised', 'fix', 'parked', 'escalated'),
    'raised': ('fix', 'merged', 'parked', 'escalated'),
    'fix': ('delta', 'parked', 'escalated'),
    'delta': ('raised', 'fix', 'parked', 'escalated'),
    'parked': ('planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta'),
    'escalated': ('planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta'),
    'merged': (),
}
STATUSES = ('queued', 'running', 'blocked', 'done')
DAY_DEFAULTS = {'items': {}, 'cap': 1, 'seat_policy': {}, 'envelope': {},
                'claimed_prs': [], 'raised_prs': [], 'gate_verdicts': {}}
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
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _append_event(kind, payload, directory)


def _append_event(kind, payload, directory):
    """Append validated event data while the caller holds state.lock."""
    record = {'kind': kind, 'payload': payload,
              'ts': workspace.now().isoformat()}
    encoded = (json.dumps(record, allow_nan=False) + '\n').encode('utf-8')
    fd = os.open(directory / 'events.jsonl', os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        if os.write(fd, encoded) != len(encoded):
            raise OSError('short event write to events.jsonl')
    finally:
        os.close(fd)


def write_state(update, root=None, *, kind='state.write', payload=None):
    """Apply a callback that mutates fresh state while holding the writer lock."""
    directory = workspace.day_dir(root)
    payload = _event_payload(kind, payload)
    directory.mkdir(parents=True, exist_ok=True)
    # ponytail: POSIX-only sidecar flock; add a platform adapter if Windows is required.
    with (directory / 'state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = read_state(directory=directory)
        previous = deepcopy(data) if (directory / 'state.json').exists() else None
        update(data)
        data = _validate(data, previous)
        encoded = json.dumps(data, allow_nan=False) + '\n'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=directory, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
                stream.flush()
                # ponytail: fsync only; add macOS F_FULLFSYNC if hardware flush is required.
                os.fsync(stream.fileno())
            os.replace(temporary, directory / 'state.json')
            fd = os.open(directory, os.O_RDONLY)
            try:
                try:
                    os.fsync(fd)
                except OSError:
                    pass  # Some platforms refuse directory fsync.
            finally:
                os.close(fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        _append_event(kind, payload, directory)
        return data


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
