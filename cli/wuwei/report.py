"""Build the local owner report from recorded day evidence."""

import re

from wuwei import metrics, state, watch, workspace


def build(root=None):
    root = workspace.find_workspace(root)
    day = workspace.day_dir(root)
    if not (day / 'state.json').is_file():
        raise ValueError('day state missing; report cannot infer open work')
    data = state.read_state(root)
    measured = metrics.collect(root)
    baseline = root / '.wuwei/memory/notes/baseline.md'
    if baseline.is_symlink():
        raise ValueError('baseline must not be a symlink')
    baseline_text = baseline.read_text(encoding='utf-8') if baseline.exists() else ''
    escaped = re.findall(r'^Escaped-defect-rate:\s*([^\n]*)$', baseline_text, re.M)
    if len(escaped) > 1 or escaped and (not re.fullmatch(r'[01](?:\.\d+)?', escaped[0].strip())
                                      or not 0 <= float(escaped[0]) <= 1):
        raise ValueError('invalid escaped defect baseline')
    expected = escaped[0].strip() if escaped else 'unmeasured'
    def baseline_value(label):
        values = re.findall(r'^' + re.escape(label) + r':\s*(\S[^\n]*)$', baseline_text, re.M)
        if len(values) > 1:
            raise ValueError(f'duplicate {label} baseline')
        return values[0] if values else 'unmeasured'
    events = watch.records(day / 'events.jsonl')
    rates = [row['payload'].get('rate') for row in events if row['kind'] == 'merge.metric']
    actual = rates[-1] if rates else 'unmeasured'
    if actual != 'unmeasured' and (type(actual) not in (int, float) or not 0 <= actual <= 1):
        raise ValueError('invalid escaped defect rate')
    lines = ['# WUWEI report ' + day.name, '', '## Outcome',
             f'- Escaped defects: {actual}; baseline: {expected}',
             f'- Review rework: unmeasured; baseline: {baseline_value("Review-rework")}',
             f'- Owner intervention: unmeasured; baseline: {baseline_value("Owner-intervention")}',
             f'- Lead time: unmeasured; baseline: {baseline_value("Lead-time")}',
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
