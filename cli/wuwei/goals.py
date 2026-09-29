"""Read the owner-edited goal list with line-numbered errors."""

from datetime import date
import re


FIELDS = ('outcome', 'measure', 'target', 'date', 'priority')


def parse(text):
    if not isinstance(text, str):
        raise ValueError('goals: expected text')
    goals = {}
    current = None
    start = 0
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line == '# Goals':
            continue
        if line.startswith('## '):
            if current is not None:
                missing = [field for field in FIELDS if field not in goals[current]]
                if missing:
                    raise ValueError(f'goals line {start}: {current} missing {missing[0]}')
            current = line[3:].strip()
            if not re.fullmatch(r'G-[1-9][0-9]*', current) or current in goals:
                raise ValueError(f'goals line {number}: invalid or duplicate id')
            goals[current] = {}
            start = number
            continue
        if current is None or ':' not in line:
            raise ValueError(f'goals line {number}: expected goal field')
        key, value = (part.strip() for part in line.split(':', 1))
        if key not in FIELDS or not value or key in goals[current]:
            raise ValueError(f'goals line {number}: invalid {key}')
        if key == 'priority':
            try:
                value = int(value)
                if value < 1:
                    raise ValueError()
            except ValueError as exc:
                raise ValueError(f'goals line {number}: invalid priority') from exc
        if key == 'date':
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f'goals line {number}: invalid date') from exc
        goals[current][key] = value
    if current is not None:
        missing = [field for field in FIELDS if field not in goals[current]]
        if missing:
            raise ValueError(f'goals line {start}: {current} missing {missing[0]}')
    if not goals:
        raise ValueError('goals line 1: no goals')
    return goals
