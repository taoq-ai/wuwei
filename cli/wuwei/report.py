"""Build the local owner report from recorded day evidence."""

import json
import re

from wuwei import metrics, state, workspace


def decisions(day, data):
    """Every recorded decision outcome, pending ones included, seat outcomes last."""
    outcomes = {}
    for path in sorted((day / 'decisions').glob('D-*.md')):
        if path.is_symlink():
            raise ValueError('decision record must not be a symlink')
        values = re.findall(r'^Outcome:\s*(\S[^\n]*)$', path.read_text(encoding='utf-8'), re.M)
        if len(values) > 1:
            raise ValueError(f'duplicate decision outcome: {path.name}')
        if values:
            outcomes[path.stem] = values[0]
    outcomes.update({ident: record.get('outcome', 'unmeasured')
                     for ident, record in data.get('decision_outcomes', {}).items()})
    return outcomes


def build(root=None):
    root = workspace.find_workspace(root)
    day = workspace.day_dir(root)
    if not (day / 'state.json').is_file():
        raise ValueError('day state missing; report cannot infer open work')
    data = state.read_state(root)
    measured = metrics.collect(root)
    baseline = measured['baseline']

    def shown(key):
        measured_value, baseline_value = (
            json.dumps(value, sort_keys=True, allow_nan=False) if isinstance(value, dict) else value
            for value in (measured[key], baseline[key]))
        return f'{measured_value}; baseline: {baseline_value}'
    level = workspace.verbosity(workspace.load_config(root), 'report')
    headline = (('Escaped defects', 'escaped_defects'), ('Review rework', 'review_rework'),
               ('Owner intervention', 'owner_intervention'), ('Lead time', 'lead_time'))
    if level == 'brief':
        changed = [f'- {title}: {shown(key)}' for title, key in headline
                   if measured[key] != baseline[key]][:3]
        lines = ['# WUWEI report ' + day.name, '', '## Changed', *(changed or ['none'])]
    else:
        lines = ['# WUWEI report ' + day.name, '', '## Outcome',
                 *(f'- {title}: {shown(key)}' for title, key in headline)]
    lines += ['', '## Merged']
    items = data['items']
    lines.extend(f"- {name} ({item['pr']})" if item.get('pr') else f'- {name}'
                 for name, item in sorted(items.items()) if item['phase'] == 'merged')
    if lines[-1] == '## Merged':
        lines.append('none')
    lines += ['', '## Open at close']
    lines.extend(f"- {name}: {item['phase']} ({item['status']})" for name, item in sorted(items.items())
                 if item['phase'] not in ('merged', 'parked'))
    if lines[-1] == '## Open at close':
        lines.append('none')
    lines += ['', '## Parked']
    parked = [(name, item) for name, item in sorted(items.items()) if item['phase'] == 'parked']
    for name, item in parked:
        ident = item.get('decision')
        record = day / 'decisions' / f'{ident}.md' if isinstance(ident, str) else None
        if record is not None and record.is_symlink():
            raise ValueError('parked decision must not be a symlink')
        reference = f'decisions/{ident}.md' if record is not None and record.is_file() else 'unmeasured'
        lines.append(f'- {name}: decision {ident or "unmeasured"} ({reference})')
    if not parked:
        lines.append('none')
    lines += ['', '## Decisions answered']
    outcomes = {ident: outcome for ident, outcome in decisions(day, data).items()
                if outcome.lower() != 'pending'}
    path = ' (decisions/{}.md)' if level == 'full' else ''
    lines.extend(f'- {ident}: {outcome}' + path.format(ident) for ident, outcome in sorted(outcomes.items()))
    if not outcomes:
        lines.append('none')
    lines += ['', '## Carry']
    carry = [(name, item) for name, item in sorted(items.items()) if item['phase'] != 'merged']
    lines.extend(f"- {name}: {item['phase']}" for name, item in carry)
    if not carry:
        lines.append('none')
    if level == 'brief':
        return '\n'.join([*lines, ''])
    quality = measured['quality_by_band']
    lines += ['', '## Quality by band', *(
        ['unmeasured'] if quality == metrics.UNMEASURED else
        [*metrics.band_lines('Hour', quality['hour']), '',
         *metrics.band_lines('Session age', quality['session_age'])])]
    lines += ['', '## Process metrics', json.dumps(measured, sort_keys=True, allow_nan=False), '']
    return '\n'.join(lines)


def write(root=None):
    root = workspace.find_workspace(root)
    path = workspace.day_dir(root) / 'report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(path, build(root))
    return path
