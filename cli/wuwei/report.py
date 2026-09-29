"""Build the local owner report from recorded day evidence."""

import re

from wuwei import metrics, state, workspace


def build(root=None):
    root = workspace.find_workspace(root)
    day = workspace.day_dir(root)
    if not (day / 'state.json').is_file():
        raise ValueError('day state missing; report cannot infer open work')
    data = state.read_state(root)
    measured = metrics.collect(root)
    baseline = measured['baseline']
    lines = ['# WUWEI report ' + day.name, '', '## Outcome',
             f'- Escaped defects: {measured["escaped_defects"]}; baseline: {baseline["escaped_defects"]}',
             f'- Review rework: {measured["review_rework"]}; baseline: {baseline["review_rework"]}',
             f'- Owner intervention: {measured["owner_intervention"]}; baseline: {baseline["owner_intervention"]}',
             f'- Lead time: {measured["lead_time"]}; baseline: {baseline["lead_time"]}',
             '', '## Open at close']
    items = data['items']
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
    outcomes = {}
    for path in sorted((day / 'decisions').glob('D-*.md')):
        if path.is_symlink():
            raise ValueError('decision record must not be a symlink')
        values = re.findall(r'^Outcome:\s*(\S[^\n]*)$', path.read_text(encoding='utf-8'), re.M)
        if len(values) > 1:
            raise ValueError(f'duplicate decision outcome: {path.name}')
        if values and values[0].lower() != 'pending':
            outcomes[path.stem] = values[0]
    outcomes.update({ident: record.get('outcome', 'unmeasured')
                     for ident, record in data.get('decision_outcomes', {}).items()})
    lines.extend(f'- {ident}: {outcome}' for ident, outcome in sorted(outcomes.items()))
    if not outcomes:
        lines.append('none')
    lines += ['', '## Carry']
    carry = [(name, item) for name, item in sorted(items.items()) if item['phase'] != 'merged']
    lines.extend(f"- {name}: {item['phase']}" for name, item in carry)
    if not carry:
        lines.append('none')
    lines += ['', '## Process metrics', str(measured), '']
    return '\n'.join(lines)


def write(root=None):
    root = workspace.find_workspace(root)
    path = workspace.day_dir(root) / 'report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(path, build(root))
    return path
