"""Steward reviews at sweep and close: one fresh seat that proposes charter and note changes."""

import json
import re
from uuid import uuid4

from wuwei import brief, metrics, registry, state, watch, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED


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
    if trigger not in ('sweep', 'close'):
        raise ValueError(f'invalid steward trigger; {DAMAGED}')
    day = workspace.day_dir(root)
    if trigger == 'close':
        prior = [row['payload'] for row in watch.records(day / 'events.jsonl')
                 if row['kind'] == 'steward.run' and row['payload'].get('trigger') == 'close']
        if prior:
            print(f"steward: close review already ran today (brief {prior[0].get('brief')})")
            return 0
    elif waiting := state.mid_round(state.read_state(root)):
        print(f"steward: waits for {', '.join(waiting)} to finish the fix round")
        return 0
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
