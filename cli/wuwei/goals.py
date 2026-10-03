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
        # Text before the first heading is the owner guide; indented lines there are examples.
        if current is None and (raw[:1].isspace() or not line.startswith('## ')):
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


def defined(text):
    """memory/goals.md has a goal heading (the template's example block is indented)."""
    return re.search(r'^## ', text, re.M) is not None


def proposed(text, goals):
    """(goals text, provisional): text, or while it has no goal heading, the lead's goal
    objects rendered as goals.md text and validated by parse."""
    if (defined(text) or not isinstance(goals, list) or not goals
            or not all(isinstance(goal, dict) for goal in goals)):
        return text, False
    blocks = ['# Goals', '']
    for goal in goals:
        if set(goal) != {'id', *FIELDS}:
            raise ValueError('proposed goals: each needs exactly id, ' + ', '.join(FIELDS))
        for key, value in goal.items():
            kind = int if key == 'priority' else str
            if type(value) is not kind or str(value).splitlines() != [str(value)]:
                raise ValueError(f'proposed goals: invalid {key}')
        blocks += [f'## {goal["id"]}', *(f'{key}: {goal[key]}' for key in FIELDS), '']
    rendered = '\n'.join(blocks)
    try:
        parse(rendered)
    except ValueError as exc:
        raise ValueError(f'proposed goals: {exc}') from exc
    return rendered, True
