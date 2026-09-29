"""Steward observations and the dedicated planner acknowledgement producer."""

import json
from pathlib import Path
import re
from uuid import uuid4

from wuwei import brief, metrics, registry, state, watch, workspace


SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def pending(data, item=None):
    return [note for note in data.get('steward_notes', [])
            if note['id'] not in data.get('steward_acks', [])
            and (item is None or note['item'] == item)]


def review(root=None):
    """Record a third-round note once, without touching item state."""
    root = workspace.find_workspace(root)
    rounds = metrics.collect(root)['fix_rounds_per_item']
    if rounds == metrics.UNMEASURED:
        return []
    notes = [{'id': f'{item}-fix-3', 'item': item,
              'text': f'{item}: third fix round; reassess scope and escalation before dispatch'}
             for item, count in rounds.items() if count >= 3 and SAFE_ID.fullmatch(item)]
    existing = {note['id'] for note in state.read_state(root).get('steward_notes', [])}
    fresh = [note for note in notes if note['id'] not in existing]
    if fresh:
        state._write_state(lambda data: data.setdefault('steward_notes', []).extend(
            note for note in fresh if note['id'] not in
            {row['id'] for row in data['steward_notes']}),
                           root, reserved=False, kind='steward.notes',
                           payload={'notes': fresh})
    return notes


def acknowledge(note_id, root=None):
    """Only the planner acknowledgement command writes acknowledgement state."""
    root = workspace.find_workspace(root)
    if not SAFE_ID.fullmatch(note_id):
        raise state.StateError('invalid steward note id')

    def update(data):
        if note_id not in {note['id'] for note in data.get('steward_notes', [])}:
            raise state.StateError('unknown steward note')
        if note_id in data.get('steward_acks', []):
            raise state.StateError('steward note already acknowledged')
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
            raise ValueError('decision record must be a regular file')
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
        raise ValueError('invalid steward trigger')
    day = workspace.day_dir(root)
    notes = review(root)
    queue = decision_queue(root)
    measured = metrics.collect(root)
    body = ('# Steward review\n\nTrigger: ' + trigger + '\n'
            + 'Metrics: ' + json.dumps(measured, sort_keys=True) + '\n'
            + 'Notes: ' + json.dumps(notes) + '\n'
            + 'Decision queue: ' + json.dumps(queue) + '\n'
            + 'Propose charter and note changes in the day proposals directory. '
              'Never dispatch or change item state.\n')
    brief_relative = brief.write('steward', 'day',
                                  f'steward-{uuid4().hex}', body, root=root)
    try:
        adapter = registry.load('runtime', registry.runtime_config(
            'steward', workspace.load_config(root), root))
        result = adapter.dispatch('steward', str(root / brief_relative), str(root), True, root=root)
        if not isinstance(result, registry.Result) or type(result.exit) is not int or result.exit not in (0, 1, 2):
            raise ValueError('invalid runtime result')
        if result.exit:
            raise ValueError(result.reason or 'steward runtime could not launch')
        if not isinstance(result.data, dict) or result.data.get('error'):
            raise ValueError('steward runtime returned invalid or error data')
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
        raise ValueError('invalid steward trace checkpoint')
    due = any(row['kind'] == 'steward.due' and row['payload'].get('tool_calls', 0) > last
              for row in events)
    if count - last >= interval and not due:
        state.append_event('steward.due', {'tool_calls': count}, root)
    return 0
