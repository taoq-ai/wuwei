"""The single writer for day state and append-only events."""

import fcntl
import json
import os
from pathlib import Path
from time import monotonic as _monotonic, sleep as _sleep

from wuwei import workspace
from wuwei.exits import DAMAGED


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


def _check_transition(item, target):
    phase = item['phase']
    allowed = PHASES[phase]
    if phase in ('parked', 'escalated'):
        allowed = (item['resume_phase'],)
    if target not in allowed:
        raise StateError((f'{phase} -> {target}: legal next phases: '
                         f'{", ".join(allowed) or "none (terminal)"}'
                         + (f'; state may already be at {target}' if phase == target else '')
                         + '; run bin/wuwei why <item> for its current phase'))


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
                _check_transition(old, item['phase'])
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


SNAPSHOT = 'state.snapshot.json'


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
            raise ValueError(f'{path}: day state missing while {SNAPSHOT} exists; run bin/wuwei state recover in a host terminal') from None
        return workspace.copy_data(DAY_DEFAULTS)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{path}: {exc}; run bin/wuwei state recover in a host terminal') from exc


def _event_payload(kind, payload):
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError(f'event kind must be a nonempty string; {DAMAGED}')
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise ValueError(f'event payload must be an object; {DAMAGED}')
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


def _append_event(kind, payload, directory, more=()):
    """Append validated event data, and any more (kind, payload) pairs in the same write,
    while the caller holds state.lock."""
    ts = workspace.now().isoformat()
    _append_jsonl(directory / 'events.jsonl',
                  *({'kind': k, 'payload': p, 'ts': ts} for k, p in ((kind, payload), *more)))


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


def _write_state(update, root=None, *, reserved=True, kind='state.write', payload=None, directory=None, more=()):
    """Apply a callback that mutates fresh state while holding the writer lock; more is
    (kind, payload) events appended with this write's event."""
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    payload = _event_payload(kind, payload)
    more = [(name, _event_payload(name, extra)) for name, extra in more]
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
        # One directory fsync, after both renames, makes both durable (#516).
        workspace.atomic_write(directory / 'state.json', encoded, mode=0o444, sync_dir=False)
        workspace.atomic_write(directory / SNAPSHOT, encoded, mode=0o444)
        changes = {name: item['phase'] for name, item in data['items'].items()
                   if previous is not None and name in previous['items']
                   and item['phase'] != previous['items'][name]['phase']}
        seen = bool(data['raised_prs'] or data['claimed_prs'])
        _append_event(kind, {**payload, 'prs_seen': seen, **({'phase_changes': changes} if changes else {})},
                      directory, [(name, {**extra, 'prs_seen': seen}) for name, extra in more])
        return data


# Only these root settings are tunable, and only before morning approval.
OWNER_FIELDS = frozenset({'cap', 'seat_policy'})
STATE_PRODUCERS = {
    'drafts': 'wuwei drafts and outward adapters',
    'mcp': 'wuwei mcp check or owner host decision',
    'integrity': 'wuwei integrity check', 'integrity_failed': 'wuwei integrity check',
    'integrity_confirmation': 'owner host re-confirmation',
    'cap': 'wuwei plan approve or wuwei dispatch next --all',
    'cap_bound': 'wuwei plan approve or wuwei dispatch next --all', 'seat_policy': 'wuwei plan approve',
    'envelope': 'wuwei plan approve', 'items': 'wuwei plan approve',
    'gate_approved': 'wuwei plan approve', 'approved_items': 'wuwei plan approve',
    'goals': 'wuwei plan approve', 'goal_seats': 'wuwei plan approve',
    'planner_session_id': 'wuwei plan session',
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
    'merge_breakers': 'wuwei merge', 'gate_verdicts': 'wuwei dispatch receive or wuwei dispatch next',
    'brief_packs': 'wuwei brief pack', 'brief_drill': 'wuwei brief answer',
    'steward_notes': 'wuwei steward run or wuwei hook SubagentStop',
    'steward_acks': 'wuwei steward ack',
    'negotiation_loops': 'wuwei steward run or wuwei dispatch next',
    'discovery_candidates': 'wuwei dispatch discovery',
    'intraday_proposals': 'wuwei plan add',
    'sessions': 'wuwei hook SessionStart, Stop and SubagentStop, wuwei plan session, wuwei listen (remote sessions) or wuwei hook PostToolUse (gate questions)',
    'claims': 'wuwei brief builder or wuwei worktree add',
    'tickets': 'wuwei plan approve, add or set, wuwei tracker create or wuwei drafts approve',
    'tracker_log': 'wuwei tracker create or log',
    'outbound_learn': 'wuwei outbound learn or wuwei decide',
    'outbound_threads': 'wuwei outbound learn',
    'grants': 'wuwei hook PreToolUse (deploy, push and PR guards), wuwei pr raise, wuwei merge or wuwei pr act, wuwei plan propose or wuwei decide',
    'cruise_cards': 'wuwei plan propose',
    'pace': 'wuwei plan approve or wuwei plan set pace=', 'pace_card': 'wuwei plan propose',
    'decision_shadows': 'wuwei decision route',
}


def running_by_goal(data):
    """{goal: running builder seats}, goals sorted; an item without a goal is unplanned."""
    from collections import Counter
    counts = Counter(data['items'].get(seat.get('item'), {}).get('goal', 'unplanned')
                     for seat in data.get('seats', {}).values()
                     if isinstance(seat, dict) and seat.get('status') == 'running'
                     and seat.get('role') == 'builder')
    return dict(sorted(counts.items()))


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
    return sorted(rows, key=lambda row: row[0])


def in_flight_text(rows):
    return ', '.join(f'{role} {item} {at[11:16] if at else "start unrecorded"}'
                     for at, role, item in rows)


def goal_split(counts):
    return ', '.join(f'{goal} {count}' for goal, count in counts.items())


def _producer_error(parts):
    key = parts[0]
    producer = STATE_PRODUCERS.get(key, 'its dedicated command')
    if key == 'items' and len(parts) > 2:
        producer = {'phase': 'wuwei state transition',
                    'resume_phase': 'wuwei state transition',
                    'flags': 'wuwei plan approve', 'track': 'wuwei brief', 'depth': 'wuwei brief',
                    'worktree': 'wuwei brief, wuwei worktree adopt or wuwei worktree add --branch',
                    'source': 'wuwei plan add or wuwei pr claim',
                    'title': 'wuwei plan add or wuwei pr claim',
                    'pr': 'wuwei pr raise or wuwei pr claim',
                    'goal': 'wuwei plan approve', 'tier': 'wuwei plan approve',
                    'gates': 'wuwei dispatch next', 'spec': 'wuwei plan set', 'owner_merge': 'wuwei plan set',
                    'docs': 'wuwei plan set or wuwei docs page',
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
        raise ValueError('path must contain nonempty dot-separated keys; pass a dotted key such as items.DIV-1.status')
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


def record_pr(root, item, ref, *, raised, head=None, reviewers=None, draft=False):
    """Link one owned PR to its item in the same write as day ownership."""
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
        field = 'raised_prs' if raised else 'claimed_prs'
        if ref not in data[field]:
            data[field].append(ref)
        if reviewers is not None:
            data.setdefault('pr_reviewers', {})[ref] = reviewers
        if raised and data['items'][item]['phase'] in ('gate', 'delta'):
            _move(data, item, 'raised')
        if not raised and data['items'][item]['phase'] == 'planned':
            _move(data, item, 'raised')  # #510: a claimed PR is never built afresh.
    payload = {'pr': ref, 'item': item}
    if head is not None:
        payload['head'] = head
    if reviewers is not None:
        payload['reviewers'] = reviewers
    if draft:
        payload['draft'] = True
    if raised:
        return _write_state(update, root, reserved=False, kind='pr.raised', payload=payload)
    return _write_state(update, root, reserved=False, kind='pr.claimed', payload=payload)


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
    return _write_state(update, root, reserved=False, kind='worktree.adopted',
                        payload={'item': item, 'worktree': path, 'head': head})


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


def stop_seat(name, root=None, *, directory=None, agent_id=None, reason=None, by=None, session=None):
    """Release a reservation while preserving the used brief and seat identity; with a reason
    the seat is unmeasured: its report could not be recorded (#473). session (session_id, hook,
    cwd) also records the session row in the same write (#516)."""
    fields = {'reason': reason} if reason else {}
    if by:
        fields['by'] = by

    def update(data):
        seat = data['seats'][name]
        seat.pop('reason', None)
        seat.pop('by', None)
        seat.update(status='unmeasured' if reason else 'stopped', stopped_at=workspace.now().isoformat(),
                    **fields)
        if isinstance(agent_id, str) and agent_id.strip():
            seat['agent_id'] = agent_id
        if session:
            from wuwei import sessions
            sessions.record(data, **session)
    payload = {'name': name, **({'status': 'unmeasured'} if reason else {}), **fields}
    more = [('session.seen', {'session_id': session['session_id'], 'hook': session['hook']})] if session else ()
    return _write_state(update, root, reserved=False, kind='seat stopped',
                        payload=payload, directory=directory, more=more)


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
            raise StateError('state.json is readable; nothing to recover; run bin/wuwei doctor for other problems')
        text = (directory / SNAPSHOT).read_text(encoding='utf-8')
        try:
            _load(text)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'unusable state snapshot: {exc}') from None
        return reason, sha256(text.encode('utf-8')).hexdigest(), text

    reason, digest, text = measure()
    if not confirm(digest[:12]):
        raise StateError('state recovery declined; rerun bin/wuwei state recover in a host terminal and answer y')
    with (directory / 'state.lock').open('a') as lock:
        lock_ex(lock, 'state.lock')
        if measure()[1] != digest:
            raise ValueError('state changed during confirmation; retry')
        workspace.atomic_write(path, text, mode=0o444)
        _append_event('state.recovered', {'snapshot': digest, 'reason': f'state recovered from snapshot {digest[:12]}',
                                           'error': reason}, directory)
    return digest
