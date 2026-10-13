"""Build the local owner report from recorded day evidence."""

from collections import Counter
from datetime import timedelta
import json

from wuwei import metrics, signal, state, watch, workspace

FALSE_POSITIVE_AFTER = 3  # A form refused more often than this with no later page is a candidate.


def shadow_lines(directories):
    """Shadow refusals in day directories, oldest first: per guard its count and three most
    frequent forms, then the forms refused more than FALSE_POSITIVE_AFTER times with no
    page-tier event after their first refusal. [] when there are none."""
    guards, forms, first, last_page = Counter(), {}, {}, -1
    events = [event for directory in directories for event in watch.records(directory / 'events.jsonl')]
    for position, event in enumerate(events):
        if event['kind'] != 'guard.would_refuse':
            if signal.classify(event, {})[0] == 'page':
                last_page = position
            continue
        guard = str(event['payload'].get('guard'))
        form = ' '.join(str(event['payload'].get('target', '')).split()[:3])
        guards[guard] += 1
        forms.setdefault(guard, Counter())[form] += 1
        first.setdefault((guard, form), position)
    if not guards:
        return []
    lines = [f'- {guard}: {count} (' + ', '.join(f'{form}: {times}' for form, times
                                               in forms[guard].most_common(3)) + ')'
             for guard, count in guards.most_common()]
    candidates = [f'- {guard}: {form} ({forms[guard][form]} times, no later incident)'
                  for (guard, form), position in first.items()
                  if forms[guard][form] > FALSE_POSITIVE_AFTER and last_page < position]
    return [*lines, '', 'Candidates for a guard fix or a calibration proposal:', *(candidates or ['none'])]


def round_lines(rows):
    """#623: fix rounds per item today, and the items whose rounds reached their cap."""
    opened = [row['payload'] for row in rows if row['kind'] == 'build.fix_opened']
    lines = []
    for item in sorted({str(row.get('item')) for row in opened}):
        mine = [row for row in opened if str(row.get('item')) == item]
        hits = [row['cap'] for row in mine if isinstance(row.get('round'), int)
                and isinstance(row.get('cap'), int) and row['round'] >= row['cap']]
        lines.append(f'- {item}: {len(mine)} fix round{"s" if len(mine) > 1 else ""}'
                     + (f', round cap {hits[-1]} reached' if hits else ''))
    return lines


def seat_lines(data):
    """#622: reviewer seats per tiered item, its gate set and the tier reasons. A delta continues
    a seat, so it counts once; a second opinion is its own seat."""
    from wuwei import brief, dispatch
    seats = brief.seats(data).values()
    lines = []
    for name, item in sorted(data['items'].items()):
        if not item.get('gates'):
            continue
        count = sum(seat['item'] == name and seat['role'].startswith('sentinel-') for seat in seats)
        lines.append(f"- {name}: {count} reviewer seat{'' if count == 1 else 's'} "
                     f"({', '.join(dispatch.gate_set(item))}); tier {item['gates'].get('tier')}: "
                     + '; '.join(item['gates'].get('reasons') or ['none recorded']))
    return lines


def cycle_lines(root):
    """#567: median cycle minutes per tier against its target, then one line per merged item."""
    rows = metrics.cycles(root)
    tiers = metrics.cycle_by_tier(rows)
    if tiers == metrics.UNMEASURED:
        return ['unmeasured']
    gates = lambda value: value if value == metrics.UNMEASURED else f'{value:.0f} minutes'
    return [*(f"- {tier}: median {row['median_minutes']:.0f} minutes over {row['items']} items"
              + (f" (target {row['target']})" if 'target' in row else '') for tier, row in tiers.items()),
            *(f"- {row['item']} ({row['tier']}): {row['cycle_minutes']:.0f} minutes, gates "
              f"{gates(row['gate_minutes'])}" for row in rows)]


def dora_lines(rows):
    """#586: the DORA table, one row per key in metrics.DORA order."""
    def cells(label, form, row):
        value = row['value'] if row['value'] == metrics.UNMEASURED else form.format(row['value'])
        return f"| {label} | {value} | {row.get('source', row.get('reason', '')).replace('|', '/')} |"
    return ['| Key | Value | Source |', '| --- | --- | --- |',
            *(cells(label, form, rows[key]) for key, label, form in metrics.DORA)]


def dora_section(root, config, days=metrics.DORA_WINDOW):
    until = workspace.now()
    return [f'## DORA (last {days} days)',
            *dora_lines(metrics.dora(root, config, until - timedelta(days=days), until))]


def build(root=None):
    root = workspace.find_workspace(root)
    day = workspace.day_dir(root)
    if not state.day_started(day):
        raise ValueError('day state missing; report cannot infer open work; start the day with /wuwei:wuwei-plan')
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
    lines += ['', '## Done']
    for name, item in sorted(items.items()):
        if item['status'] != 'done' or item['phase'] == 'merged':
            continue
        if item.get('by') == 'owner':
            detail = f"{item['reason']} (owner)"
            detail += f"; branch {item['branch']}" if item.get('branch') else ''
            detail += f"; worktree {item['worktree']}" if item.get('worktree') else ''
            lines.append(f'- {name}: {detail}')
            continue
        verdicts = [f"{row['role']} {row['verdict']} ({row['file']})"
                    for key, row in data['gate_verdicts'].items()
                    if key.startswith(f'{name}:') and key.endswith(':initial')]
        lines.append(f'- {name}: ' + ('; '.join(verdicts) or 'verdict unmeasured'))
    if lines[-1] == '## Done':
        lines.append('none')
    lines += ['', '## Cycle time', *cycle_lines(root)]
    lines += ['', *dora_section(root, workspace.load_config(root))]  # #586
    lines += ['', '## Open at close']
    lines.extend(f"- {name}: {item['phase']} ({item['status']})" for name, item in sorted(items.items())
                 if item['phase'] not in ('merged', 'parked') and item['status'] != 'done')
    if lines[-1] == '## Open at close':
        lines.append('none')
    lines += ['', '## Parked']
    parked = [(name, item) for name, item in sorted(items.items())
              if item['phase'] == 'parked' and item['status'] != 'done']
    lines.extend(f"- {name}: {(item.get('disposition') or {}).get('reason') or item['phase']}"
                 for name, item in parked)
    if not parked:
        lines.append('none')
    lines += ['', '## Carry']
    carry = [(name, item) for name, item in sorted(items.items())
             if item['phase'] != 'merged' and item['status'] != 'done']
    lines.extend(f"- {name}: {item['phase']}" for name, item in carry)
    if not carry:
        lines.append('none')
    reviewed = seat_lines(data)
    if reviewed:
        lines += ['', '## Review seats', *reviewed]
    rounds = round_lines(watch.records(day / 'events.jsonl'))
    if rounds:
        lines += ['', '## Rounds', *rounds]
    shadow = shadow_lines([day])
    if shadow:
        lines += ['', '## Shadow', *shadow]
    warned = [row['payload'] for row in watch.records(day / 'events.jsonl') if row['kind'] == 'spec.warned']
    if warned:
        lines += ['', '## Spec warnings', *(f"- {row['item']}: {row['step']} ({row['where']})" for row in warned)]
    from wuwei import tracker
    skipped = tracker.skipped_duties(watch.records(day / 'events.jsonl'))  # #842: listed, never dropped
    if skipped:
        lines += ['', '## Skipped duties', *(
            f"- {row['item']}: {row['duty']} on {row['ticket'] or 'a new ticket'}: {row['error']}; "
            f"retry: bin/wuwei tracker {'create' if row['duty'] == 'tracker.create' else 'move'} "
            f"{row['item']}{'' if row['duty'] == 'tracker.create' else ' ' + row['duty'][8:]}"
            for row in skipped)]
    runs = Counter(str(row['payload'].get('trigger')) for row in watch.records(day / 'events.jsonl')
                   if row['kind'] == 'steward.run')
    lines += ['', '## Steward runs', *([f'- {trigger}: {count}' for trigger, count in sorted(runs.items())]
                                       or ['none'])]
    if level == 'brief':
        return '\n'.join([*lines, ''])
    quality = measured['quality_by_band']
    lines += ['', '## Quality by band', *(
        ['unmeasured'] if quality == metrics.UNMEASURED else
        metrics.band_lines('Hour', quality['hour']))]
    lines += ['', '## Process metrics', json.dumps(measured, sort_keys=True, allow_nan=False), '']
    return '\n'.join(lines)


def write(root=None):
    root = workspace.find_workspace(root)
    path = workspace.day_dir(root) / 'report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(path, build(root))
    return path
