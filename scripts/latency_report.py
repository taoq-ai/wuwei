"""Latency figures of this run against the last green main run (#562).

Usage: python scripts/latency_report.py <current.jsonl> [<last green.jsonl>]
Exit 0 every probe keeps its margin, 1 a probe is short of margin or over budget,
2 the current figures are missing or malformed.
"""

import json
import sys

MARGIN = {'cpu': 10, 'wall': 20}  # ms under the budget a quiet runner must keep


def read(path):
    """{probe: row} of a JSON lines file; the later row of a probe wins."""
    rows = {}
    with open(path, encoding='utf-8') as file:
        for line in file:
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict) or row.get('measure') not in MARGIN:
                    raise ValueError(f'malformed row: {line.strip()[:80]}')
                rows[row['probe']] = row
    return rows


def figure(row):
    return row[f'{row["measure"]}_ms']


def main(argv):
    try:
        now = read(argv[0])
    except (OSError, ValueError, KeyError, IndexError) as exc:
        print(f'latency report: current figures unreadable: {exc}', file=sys.stderr)
        return 2
    last = {}
    if len(argv) > 1:
        try:
            last = read(argv[1])
        except FileNotFoundError:
            print('no last green figures')
        except (OSError, ValueError, KeyError) as exc:
            print(f'last green figures unreadable, compared with nothing: {exc}')
    print(f'{"probe":<24} {"measure":<7} {"now":>8} {"last":>8} {"change":>14} {"budget":>6} {"margin":>7}')
    findings, moved = [], None
    for probe, row in now.items():
        value, budget = figure(row), row['budget_ms']
        before = figure(last[probe]) if probe in last else None
        change = '-' if before is None else f'{value - before:+.1f} ({(value - before) / before:+.0%})' if before else '-'
        print(f'{probe:<24} {row["measure"]:<7} {value:>8.1f} '
              f'{"-" if before is None else f"{before:.1f}":>8} {change:>14} {budget:>6} {budget - value:>7.1f}')
        if before and value > before and (moved is None or (value - before) / before > moved[0]):
            moved = ((value - before) / before, probe, value - before)
        if value >= budget:
            findings.append(f'over budget: {probe}')
        elif budget - value < MARGIN[row['measure']]:
            findings.append(f'margin short: {probe} {budget - value:.1f} ms')
    for name, rows in (('now', now), ('last green', last)):
        if rows:
            row = next(iter(rows.values()))
            print(f'{name}: floor CPU {row.get("floor_cpu_ms")} ms, wall {row.get("floor_wall_ms")} ms, '
                  f'load {row.get("load")} on {row.get("cpus")} CPUs')
    if moved:
        print(f'moved most: {moved[1]} +{moved[2]:.1f} ms (+{moved[0]:.0%})')
    print('\n'.join(findings))
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
