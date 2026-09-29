"""Process measurements from recorded day state, events and traces."""

from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path

from wuwei import state, watch, workspace


UNMEASURED = 'unmeasured'


def _events(day):
    path = day / 'events.jsonl'
    if not path.exists():
        return None
    try:
        return watch.records(path)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise ValueError(f'events.jsonl: {exc}') from exc


def _state(day):
    return state.read_state(directory=day) if (day / 'state.json').exists() else None


def _traces(day):
    path = day / 'traces.jsonl'
    if not path.exists():
        return None
    rows = []
    raw = path.read_text(encoding='utf-8')
    if raw and not raw.endswith('\n'):
        raise ValueError('incomplete trace line')
    for line in raw.splitlines():
        row = json.loads(line)
        spans = row['resourceSpans']
        if not isinstance(spans, list):
            raise ValueError('invalid trace spans')
        rows.append(row)
    return rows


def _phase_time(events, now):
    entered, elapsed = {}, defaultdict(lambda: defaultdict(float))
    for event in events:
        at = datetime.fromisoformat(event['ts'])
        if event['kind'] in ('plan.approved', 'state.import'):
            planned = event['payload'].get('items', [])
            if not isinstance(planned, list):
                raise ValueError('invalid planned items')
            if event['kind'] == 'state.import':
                approved = event['payload'].get('approved_items', [])
                if not isinstance(approved, list):
                    raise ValueError('invalid approved items')
                planned += approved
            if any(not isinstance(item, str) for item in planned):
                raise ValueError('invalid planned items')
            for item in planned:
                entered.setdefault(item, ('planned', at))
        changes = event['payload'].get('phase_changes', {})
        if not isinstance(changes, dict):
            raise ValueError('invalid phase changes')
        for item, phase in changes.items():
            if not isinstance(item, str) or not isinstance(phase, str):
                raise ValueError('invalid phase change')
            if item in entered:
                old_phase, start = entered[item]
                seconds = (at - start).total_seconds()
                if seconds < 0:
                    raise ValueError('phase timestamps out of order')
                elapsed[item][old_phase] += seconds
            entered[item] = (phase, at)
    for item, (phase, start) in entered.items():
        seconds = (now - start).total_seconds()
        if seconds < 0:
            raise ValueError('phase timestamp in the future')
        elapsed[item][phase] += seconds
    return {item: dict(phases) for item, phases in elapsed.items()}


def _costs(events, key):
    totals = defaultdict(float)
    seen = False
    for row in events:
        if row['kind'] != 'seat.usage':
            continue
        payload = row['payload']
        usage = payload.get('usage')
        if not isinstance(usage, dict):
            raise ValueError('invalid seat usage')
        cost = usage.get('cost')
        if cost is None:
            continue
        if type(cost) not in (int, float) or cost < 0:
            raise ValueError('invalid seat cost')
        target = payload.get(key)
        if not isinstance(target, str) or not target:
            raise ValueError(f'missing usage {key}')
        totals[target] += cost
        seen = True
    return dict(totals) if seen else UNMEASURED


def _calibration(day, data, elapsed):
    path = day / 'proposal.json'
    if not path.exists() or data is None or elapsed == UNMEASURED:
        return UNMEASURED
    proposal = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(proposal, dict) or not isinstance(proposal.get('candidates'), list):
        raise ValueError('invalid proposal for size calibration')
    sizes = {row['id']: row.get('score', {}).get('job_size') for row in proposal['candidates']}
    return {item: {'predicted_size': sizes[item],
                   'actual_cycle_seconds': sum(phases.values())}
            for item, phases in elapsed.items() if item in sizes and sizes[item] is not None}


def collect(root=None, *, day=None):
    """Return named measurements; missing evidence never becomes a zero."""
    root = workspace.find_workspace(root)
    directory = workspace.day_dir(root) if day is None else Path(day)
    events, data = _events(directory), _state(directory)
    traces = _traces(directory)
    now = workspace.now()
    if events is None:
        event_metrics = {name: UNMEASURED for name in (
            'fix_rounds_per_item', 'handbacks_per_pr', 'time_in_phase_seconds',
            'verdict_lint_rejections', 'decisions_per_day', 'decisions_by_reversibility',
            'owner_decisions_per_day',
            'build_loop_iterations_per_item', 'stuck_parks_per_item', 'cost_per_item',
            'cost_per_role', 'cost_per_day', 'seat_decisions_owner_reversed')}
    else:
        count = lambda kind: sum(row['kind'] == kind for row in events)
        fix = Counter(item for row in events for item, phase in
                      row['payload'].get('phase_changes', {}).items() if phase == 'fix')
        # ponytail: reply acknowledgements proxy review handbacks until PR cycle events exist.
        handbacks = Counter(row['payload']['pr'] for row in events
                            if row['kind'] == 'reply: acknowledged' and 'pr' in row['payload'])
        decisions = {row['payload'].get('id'): row['payload'] for row in events
                     if row['kind'] in ('decision.decided', 'decision.routed')}
        reversibility = Counter(row.get('reversibility', 'unknown')
                                for row in decisions.values())
        iterations = Counter(row['payload']['item'] for row in events
                             if row['kind'] == 'seat.usage' and 'item' in row['payload'])
        parks = Counter(row['payload']['item'] for row in events
                        if row['kind'] == 'build.parked' and 'item' in row['payload'])
        item_cost = _costs(events, 'item')
        event_metrics = {
            'fix_rounds_per_item': dict(fix), 'handbacks_per_pr': dict(handbacks),
            'time_in_phase_seconds': _phase_time(events, now),
            'verdict_lint_rejections': count('verdict.rejected'),
            'decisions_per_day': len(decisions),
            'owner_decisions_per_day': count('decision.routed'),
            'decisions_by_reversibility': dict(reversibility),
            'build_loop_iterations_per_item': dict(iterations),
            'stuck_parks_per_item': dict(parks), 'cost_per_item': item_cost,
            'cost_per_role': _costs(events, 'role'),
            'cost_per_day': {directory.name: sum(item_cost.values())} if isinstance(item_cost, dict) else UNMEASURED,
            'seat_decisions_owner_reversed': (count('decision.reversed')
                                              if any(row['kind'] == 'decision.reversed'
                                                     for row in events) else UNMEASURED),
        }
    if data is None or not data['items']:
        event_metrics['share_unplanned_work'] = UNMEASURED
    else:
        event_metrics['share_unplanned_work'] = sum(
            item.get('goal') == 'unplanned' for item in data['items'].values()) / len(data['items'])
    event_metrics['size_calibration'] = _calibration(directory, data, event_metrics['time_in_phase_seconds'])
    event_metrics['tool_calls'] = len(traces) if traces is not None else UNMEASURED
    return event_metrics
