"""The single writer for day state and append-only events."""

import fcntl
import json
import os
from pathlib import Path
from time import monotonic as _monotonic, sleep as _sleep

from wuwei import workspace


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
    'planned': ('spec', 'implement', 'parked', 'escalated'),
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
        value.setdefault(key, workspace.copy_data(default))
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


SNAPSHOT = 'state.snapshot.json'
RECOVER = 'run wuwei state recover in a host terminal'


def _load(text):
    data = json.loads(text)
    json.dumps(data, allow_nan=False)
    return _validate(data)


def read_state(root=None, *, directory=None):
    """Read today's state; an absent file returns fresh defaults without writes."""
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    path = directory / 'state.json'
    try:
        return _load(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        if (directory / SNAPSHOT).exists():
            raise ValueError(f'{path}: day state missing while {SNAPSHOT} exists; {RECOVER}') from None
        return workspace.copy_data(DAY_DEFAULTS)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{path}: {exc}; {RECOVER}') from exc


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
        lock_ex(lock, 'state.lock')
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
        lock_ex(lock, 'state.lock')
        _append_jsonl(path, record)


def _append_jsonl(path, record):
    """Write one line under state.lock, leaving events and traces read-only."""
    from wuwei.redact import known_values
    encoded = (json.dumps(known_values(record), allow_nan=False) + '\n').encode('utf-8')
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
        lock_ex(lock, 'state.lock')
        data = read_state(directory=directory)
        previous = workspace.copy_data(data) if (directory / 'state.json').exists() else None
        before = workspace.copy_data(data) if reserved else None
        update(data)
        if reserved:
            protected = _protected(before, before)
            changed = _protected(data, before)
            for key in protected.keys() | changed.keys():
                if (key not in protected or key not in changed
                        or json.dumps(protected[key], sort_keys=True)
                        != json.dumps(changed[key], sort_keys=True)):
                    raise _producer_error((key,))
        data = _validate(data, previous)
        encoded = json.dumps(data, allow_nan=False) + '\n'
        workspace.atomic_write(directory / 'state.json', encoded, mode=0o444)
        workspace.atomic_write(directory / SNAPSHOT, encoded, mode=0o444)
        changes = {name: item['phase'] for name, item in data['items'].items()
                   if previous is not None and name in previous['items']
                   and item['phase'] != previous['items'][name]['phase']}
        _append_event(kind, {**payload, 'prs_seen': bool(data['raised_prs'] or data['claimed_prs']),
                             **({'phase_changes': changes} if changes else {})}, directory)
        return data


# Only these root settings are tunable, and only before morning approval.
OWNER_FIELDS = frozenset({'cap', 'seat_policy'})
STATE_PRODUCERS = {
    'drafts': 'wuwei drafts and outward adapters',
    'mcp': 'wuwei mcp check or owner host decision',
    'integrity': 'wuwei integrity check', 'integrity_failed': 'wuwei integrity check',
    'integrity_confirmation': 'owner host re-confirmation',
    'cap': 'wuwei plan approve', 'seat_policy': 'wuwei plan approve',
    'envelope': 'wuwei plan approve', 'items': 'wuwei plan approve',
    'gate_approved': 'wuwei plan approve', 'approved_items': 'wuwei plan approve',
    'goals': 'wuwei plan approve', 'planner_session_id': 'wuwei plan session',
    'builds': 'wuwei build and seat hooks',
    'seats': 'wuwei hook PreToolUse or wuwei dispatch opinion', 'fast_checks': 'wuwei fast-checks',
    'reply_acks': 'wuwei reply', 'decision_outcomes': ('wuwei decision route or wuwei build or wuwei plan carry or park '
                          'or owner host wuwei doctor --fix or wuwei listen (two-way DM answer)'),
    'decision_routes': 'wuwei decision route',
    'channel_posts': 'wuwei pr ping',
    'pr_reviewers': 'wuwei pr raise or ping',
    'author_logins': 'wuwei pr raise, ping or reviewers',
    'scanner_decisions': 'wuwei sweep',
    'watch': 'wuwei watch or wuwei listen', 'pr_dispositions': 'wuwei pr disposition',
    'pr_action_done': 'wuwei pr act', 'pr_reply_drafts': 'wuwei pr act',
    'pr_action_decisions': 'wuwei pr act',
    'close_requested': 'wuwei close', 'merges': 'wuwei merge',
    'merge_breakers': 'wuwei merge', 'gate_verdicts': 'wuwei dispatch receive',
    'brief_packs': 'wuwei brief pack', 'brief_drill': 'wuwei brief answer',
    'steward_notes': 'wuwei steward run or wuwei hook SubagentStop',
    'steward_acks': 'wuwei steward ack',
    'negotiation_loops': 'wuwei steward run or wuwei dispatch next',
    'discovery_candidates': 'wuwei dispatch discovery',
    'intraday_proposals': 'wuwei plan add',
    'sessions': 'wuwei hook SessionStart, Stop and SubagentStop, wuwei plan session, wuwei listen (remote sessions) or wuwei hook PostToolUse (gate questions)',
    'claims': 'wuwei brief builder or wuwei worktree add',
}


def _producer_error(parts):
    key = parts[0]
    producer = STATE_PRODUCERS.get(key, 'its dedicated command')
    if key == 'items' and len(parts) > 2:
        producer = {'phase': 'wuwei state transition',
                    'resume_phase': 'wuwei state transition',
                    'flags': 'wuwei plan approve', 'track': 'wuwei brief',
                    'worktree': 'wuwei brief',
                    'pr': 'wuwei pr raise or wuwei pr claim',
                    'goal': 'wuwei plan approve', 'tier': 'wuwei plan approve',
                    'gates': 'wuwei dispatch next',
                    'assumption': 'wuwei decision route --external or wuwei sweep'}.get(
                        parts[2], 'its dedicated command')
    return StateError(f'{".".join(parts)}: reserved; written by {producer}')


def _generic_allowed(parts, data):
    return ((parts[0] in OWNER_FIELDS and not data['gate_approved']
             and (len(parts) == 1 or parts[0] == 'seat_policy'))
            or (len(parts) == 3 and parts[0] == 'items' and parts[2] == 'note'
                and parts[1] in data['items']))


def _protected(data, before):
    """Everything except explicitly tunable fields is producer-owned by default."""
    result = workspace.copy_data(data)
    if not before['gate_approved']:
        for key in OWNER_FIELDS:
            result.pop(key, None)
    items = result.get('items')
    if isinstance(items, dict):
        for name in before['items']:
            if isinstance(items.get(name), dict):
                items[name].pop('note', None)
    return result


def write_state(update, root=None, *, kind='state.write', payload=None):
    """Generic writes may change only explicitly allowlisted owner fields."""
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

    def update(data):
        if not _generic_allowed(parts, data):
            raise _producer_error(parts)
        parent = data
        for key in parts[:-1]:
            if not isinstance(parent, dict):
                raise ValueError(f'non-object parent in path: {path}')
            parent = parent.setdefault(key, {})
        if not isinstance(parent, dict):
            raise ValueError(f'non-object parent in path: {path}')
        parent[parts[-1]] = value

    return write_state(update, root, kind='state.set', payload={'path': path, 'value': value})


def record_pr(root, item, ref, *, raised, head=None, reviewers=None):
    """Link one owned PR to its item in the same write as day ownership."""
    from wuwei.references import pull_request
    ref = pull_request(ref)
    def update(data):
        if item not in data['items'] or item not in data['approved_items']:
            raise StateError('PR item must be in the approved plan')
        if data['items'][item].get('pr') not in (None, ref):
            raise StateError('item already links another PR')
        if any(name != item and row.get('pr') == ref for name, row in data['items'].items()):
            raise StateError('PR already links another item')
        other = 'claimed_prs' if raised else 'raised_prs'
        if ref in data[other]:
            raise StateError('PR is already owned today')
        data['items'][item]['pr'] = ref
        field = 'raised_prs' if raised else 'claimed_prs'
        if ref not in data[field]:
            data[field].append(ref)
        if reviewers is not None:
            data.setdefault('pr_reviewers', {})[ref] = reviewers
        if raised and data['items'][item]['phase'] in ('gate', 'delta'):
            _move(data, item, 'raised')
    payload = {'pr': ref, 'item': item}
    if head is not None:
        payload['head'] = head
    if reviewers is not None:
        payload['reviewers'] = reviewers
    if raised:
        return _write_state(update, root, reserved=False, kind='pr.raised', payload=payload)
    return _write_state(update, root, reserved=False, kind='pr.claimed', payload=payload)


def _move(data, item, phase):
    current = data['items'][item]
    _check_transition(current, phase)
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

    return _write_state(update, root, reserved=False, kind='state.transition',
                       payload={'item': item, 'phase': phase})


def stop_seat(name, root=None, *, directory=None, agent_id=None):
    """Release a reservation while preserving the used brief and seat identity."""
    def update(data):
        data['seats'][name].update(status='stopped', stopped_at=workspace.now().isoformat())
        if isinstance(agent_id, str) and agent_id.strip():
            data['seats'][name]['agent_id'] = agent_id
    return _write_state(update, root, reserved=False, kind='seat stopped',
                        payload={'name': name}, directory=directory)


def recover(root=None, *, confirm):
    """Restore today's unreadable state from the writer's snapshot after host confirmation."""
    from hashlib import sha256
    directory = workspace.day_dir(root)
    path = directory / 'state.json'

    def measure():
        try:
            read_state(directory=directory)
            reason = None if path.exists() else 'state.json missing'
        except ValueError as exc:
            reason = str(exc)
        if reason is None:
            raise StateError('state.json is readable; nothing to recover')
        text = (directory / SNAPSHOT).read_text(encoding='utf-8')
        try:
            _load(text)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'unusable state snapshot: {exc}') from None
        return reason, sha256(text.encode('utf-8')).hexdigest(), text

    reason, digest, text = measure()
    if not confirm(digest[:12]):
        raise StateError('state recovery declined')
    with (directory / 'state.lock').open('a') as lock:
        lock_ex(lock, 'state.lock')
        if measure()[1] != digest:
            raise ValueError('state changed during confirmation; retry')
        workspace.atomic_write(path, text, mode=0o444)
        _append_event('state.recovered', {'snapshot': digest, 'reason': f'state recovered from snapshot {digest[:12]}',
                                           'error': reason}, directory)
    return digest
