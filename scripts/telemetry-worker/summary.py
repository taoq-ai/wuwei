"""The project's weekly summary from the telemetry dataset: workspaces and integer sums per week.

Usage: python3 summary.py <dataset>/data
"""

import json
from pathlib import Path
import sys


def _leaves(value, prefix=''):
    if isinstance(value, dict):
        return [row for key, inner in value.items() for row in _leaves(inner, f'{prefix}{key}.')]
    return [(prefix[:-1], value)]


def summarise(directory):
    """{week: {workspaces, metrics: {dotted key: sum}}} over integer leaves; one file per token."""
    found = {}
    for path in sorted(Path(directory).glob('*/*.json')):
        week = found.setdefault(path.parent.name, {'workspaces': 0, 'metrics': {}})
        week['workspaces'] += 1
        for key, value in _leaves(json.loads(path.read_text(encoding='utf-8'))['metrics']):
            if type(value) is int:
                week['metrics'][key] = week['metrics'].get(key, 0) + value
    return found


if __name__ == '__main__':
    print(json.dumps(summarise(sys.argv[1]), indent=2, sort_keys=True))
