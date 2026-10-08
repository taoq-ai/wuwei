"""Steward observations and the dedicated planner acknowledgement producer."""

import json
from pathlib import Path
import re
from uuid import uuid4

from wuwei import brief, metrics, registry, state, watch, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED, SYMLINK


SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def pending(data, item=None):
    return [note for note in data.get('steward_notes', [])
            if note['id'] not in data.get('steward_acks', [])
            and (item is None or note['item'] == item)]


def review(root=None):
    """Record a third-round note once, without touching item state."""
    root = workspace.find_workspace(root)
    from wuwei import budget_classes
    budget_classes.evaluate(root)  # #558: the error budget lowers, restores and warns
    rounds = metrics.collect(root)['fix_rounds_per_item']
    if rounds == metrics.UNMEASURED:
        return []
    notes = [{'id': f'{item}-fix-3', 'item': item,
              'text': f'{item}: third fix round; reassess scope and escalation before dispatch'}
             for item, count in rounds.items() if count >= 3 and SAFE_ID.fullmatch(item)]
    add_notes(root, notes)
    negotiation(root)
    return notes


class _Raised(Exception):
    """A concurrent review already recorded this item's loop."""


def negotiation(root):
    """Design 5.8.2: one negotiation.loop per item per day when exchanges exceed the budget."""
    from collections import Counter
    from datetime import datetime, timedelta
    from wuwei import decision, goals
    config = workspace.load_config(root)['steward']
    day = workspace.day_dir(root)
    data = state.read_state(root)
    items = [name for name in data['items']
             if SAFE_ID.fullmatch(name) and name not in data.get('negotiation_loops', {})]
    if not items:
        return []
    now = workspace.now()
    start = now - timedelta(hours=config['loop_window_hours'])
    exchanges = {name: [] for name in items}
    fix_rounds, briefed = Counter(), set()
    for record, named in decision.naming(day, items).items():
        # ponytail: the file mtime is the record time; records carry no timestamp field.
        when = datetime.fromtimestamp((day / 'decisions' / f'{record}.md').stat().st_mtime).astimezone()
        for name in named:
            if when >= start:
                exchanges[name].append((when, 'records', f'{record} recorded'))
    for row in watch.records(day / 'events.jsonl'):
        payload, kind = row['payload'], row['kind']
        name, role = payload.get('item'), str(payload.get('role', ''))
        if name not in exchanges:
            continue
        when = datetime.fromisoformat(row['ts'])
        entry = None
        if kind == 'gate.received':
            entry = ('verdicts', f'{role.removeprefix("sentinel-")} review {payload.get("verdict")}')
        elif kind == 'brief written' and role != 'steward':
            if (name, role) in briefed:
                entry = ('redispatches', f'{role.removeprefix("sentinel-")} restarted')
            briefed.add((name, role))
        elif kind == 'build.fix_opened':
            fix_rounds[name] += 1
            entry = ('continuations', 'fix requested')
        if entry and when >= start:
            exchanges[name].append((when, *entry))
    raised = []
    for name in items:
        counts = Counter({key: 0 for key in ('records', 'verdicts', 'redispatches', 'continuations')})
        counts.update(key for _, key, _ in exchanges[name])
        if sum(counts.values()) <= config['loop_threshold'] and fix_rounds[name] < 2:
            continue
        last = [f'{when.astimezone(now.tzinfo):%H:%M} {text}'
                for when, _, text in sorted(exchanges[name], key=lambda row: row[0])[-2:]]
        try:
            goal = goals.parse((root / '.wuwei/memory/goals.md').read_text(encoding='utf-8'))
            past_goal = goal[data['items'][name]['goal']]['date'] < now.date().isoformat()
        except (OSError, ValueError, KeyError, TypeError):
            past_goal = False
        reason = (f'{name} is going back and forth: {counts["records"]} records, '
                  f'{counts["verdicts"]} reviews, {counts["redispatches"]} restarts and '
                  f'{counts["continuations"]} fix requests in {config["loop_window_hours"]} hours, '
                  f'{fix_rounds[name]} fix rounds today' + ('; last: ' + '; '.join(last) if last else ''))
        payload = {'item': name, 'counts': dict(counts), 'fix_rounds': fix_rounds[name],
                   'last': last, 'past_goal': past_goal, 'reason': reason}

        def update(fresh, name=name, payload=payload):
            if name in fresh.get('negotiation_loops', {}):
                raise _Raised
            fresh.setdefault('negotiation_loops', {})[name] = payload

        try:
            state._write_state(update, root, reserved=False, kind='negotiation.loop', payload=payload)
            raised.append(payload)
        except _Raised:
            pass
    return raised


def add_notes(root, notes):
    """Record each note once; a repeat id is a no-op."""
    existing = {note['id'] for note in state.read_state(root).get('steward_notes', [])}
    fresh = [note for note in notes if note['id'] not in existing]
    if fresh:
        state._write_state(lambda data: data.setdefault('steward_notes', []).extend(
            note for note in fresh if note['id'] not in
            {row['id'] for row in data['steward_notes']}),
                           root, reserved=False, kind='steward.notes',
                           payload={'notes': fresh})


def acknowledge(note_id, root=None):
    """Only the planner acknowledgement command writes acknowledgement state."""
    root = workspace.find_workspace(root)
    if not SAFE_ID.fullmatch(note_id):
        raise state.StateError(f'invalid steward note id; {DAMAGED}')

    def update(data):
        if note_id not in {note['id'] for note in data.get('steward_notes', [])}:
            raise state.StateError('unknown steward note; run bin/wuwei status for the open steward notes')
        if note_id in data.get('steward_acks', []):
            raise state.StateError('steward note already acknowledged; nothing to do; run bin/wuwei status for the open ones')
        data.setdefault('steward_acks', []).append(note_id)

    return state._write_state(update, root, reserved=False, kind='steward.acknowledged',
                              payload={'id': note_id})


def decision_queue(root=None):
    """Pre-triage recorded pending owner decisions; invalid records stay visible."""
    root = workspace.find_workspace(root)
    from wuwei import decision
    day = workspace.day_dir(root)
    decided = state.read_state(root).get('decision_outcomes', {})
    queue = []
    for path in sorted((day / 'decisions').glob('D-*.md')):
        if path.is_symlink():
            raise ValueError(f'decision record must be a regular file; {SYMLINK}')
        ident = path.stem
        if ident in decided:
            continue
        body = path.read_text(encoding='utf-8')
        fields = dict(re.findall(r'^(Question|Recommendation|Reversibility|Blast radius):\s*(.+)$', body, re.M))
        code, message = decision.lint(body)
        queue.append({'id': ident, 'question': fields.get('Question', 'unmeasured'),
                      'recommendation': fields.get('Recommendation', 'unmeasured'),
                      'reversibility': fields.get('Reversibility', 'unmeasured'),
                      'blast_radius': fields.get('Blast radius', 'unmeasured'),
                      'lint': 'valid' if code == 0 else message})
    for ident, proposal in sorted(state.read_state(root).get('intraday_proposals', {}).items()):
        if proposal.get('decision') != 'owner':
            continue
        queue.append({'id': ident, 'question': f'Admit intraday item {ident}?',
                      'recommendation': 'defer', 'reversibility': 'two-way',
                      'blast_radius': proposal.get('candidate', {}).get('scope', 'unmeasured'),
                      'lint': proposal.get('reason', 'proposal pending owner')})
    workspace.atomic_write(day / 'steward-decisions.json',
                           json.dumps(queue, allow_nan=False, indent=2) + '\n')
    return queue


def previous_day_finding(root=None):
    root = workspace.find_workspace(root)
    day = workspace.day_dir(root)
    days = sorted((path for path in (root / '.wuwei/days').glob('*')
                   if path.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.name)
                   and path.name < day.name), reverse=True)
    if not days:
        return None
    path = days[0] / 'events.jsonl'
    if not path.exists():
        return f'prior day had no steward run: {days[0].name}'
    rows = watch.records(path)
    return (f'prior day had no steward run: {days[0].name}'
            if not any(row['kind'] == 'steward.run' for row in rows) else None)


def run(root=None, *, trigger='sweep'):
    """Launch one fresh steward seat through the runtime adapter and record observations."""
    root = workspace.find_workspace(root)
    if trigger not in ('sweep', 'close', 'tool-calls'):
        raise ValueError(f'invalid steward trigger; {DAMAGED}')
    day = workspace.day_dir(root)
    if trigger == 'close':
        prior = [row['payload'] for row in watch.records(day / 'events.jsonl')
                 if row['kind'] == 'steward.run' and row['payload'].get('trigger') == 'close']
        if prior:
            print(f"steward: close review already ran today (brief {prior[0].get('brief')})")
            return 0
    notes = review(root)
    queue = decision_queue(root)
    measured = metrics.collect(root)
    calibration = ''
    if trigger == 'sweep':
        from wuwei import calibrate  # Local: calibrate stays off every hook path.
        try:
            found = {'drift': calibrate.drift(root), 'baseline': {
                name: entry.get('baseline') for name, entry in calibrate.approved(root).items()}}
        except (OSError, ValueError) as exc:
            found = {'drift': f'unmeasured: {exc}'}
        calibration = 'Calibration: ' + json.dumps(found, sort_keys=True) + '\n'
    body = ('# Steward review\n\nTrigger: ' + trigger + '\n'
            + 'Metrics: ' + json.dumps(measured, sort_keys=True) + '\n'
            + 'Notes: ' + json.dumps(notes) + '\n'
            + 'Decision queue: ' + json.dumps(queue) + '\n'
            + calibration
            + 'Propose charter and note changes in the day proposals directory. '
              'Never dispatch or change item state.\n')
    brief_relative = brief.write('steward', 'day',
                                  f'steward-{uuid4().hex}', body, root=root)
    try:
        adapter = registry.load('runtime', registry.runtime_config(
            'steward', workspace.load_config(root), root))
        result = adapter.dispatch('steward', str(root / brief_relative), str(root), True, root=root)
        if not isinstance(result, registry.Result) or type(result.exit) is not int or result.exit not in (0, 1, 2):
            raise ValueError(f'invalid runtime result; {ADAPTER_DATA}')
        if result.exit:
            raise ValueError(result.reason or 'steward runtime could not launch; retry; if it repeats, run bin/wuwei doctor')
        if not isinstance(result.data, dict) or result.data.get('error'):
            raise ValueError(f'steward runtime returned invalid or error data; {ADAPTER_DATA}')
    except Exception:
        (root / brief_relative).unlink(missing_ok=True)
        raise
    trace_count = measured['tool_calls']
    state.append_event('steward.run', {'trigger': trigger, 'brief': brief_relative,
                                      'tool_calls': trace_count}, root)
    print(json.dumps({'steward_launch': result.data}, allow_nan=False))
    return 0


def maybe_run_for_tool_calls(count, root=None):
    """Notify the planner once when the trace count reaches a run boundary."""
    root = workspace.find_workspace(root)
    interval = workspace.load_config(root)['steward']['every_tool_calls']
    events = watch.records(workspace.day_dir(root) / 'events.jsonl')
    runs = [row['payload'].get('tool_calls') for row in events if row['kind'] == 'steward.run']
    last = runs[-1] if runs else 0
    if type(last) is not int or last < 0 or last > count:
        raise ValueError(f'invalid steward trace checkpoint; {DAMAGED}')
    due = any(row['kind'] == 'steward.due' and row['payload'].get('tool_calls', 0) > last
              for row in events)
    if count - last >= interval and not due:
        state.append_event('steward.due', {'tool_calls': count}, root)
    return 0
