"""One evaluator for decision records, saved files and routing."""

from pathlib import Path
import re

from wuwei import state, workspace
from wuwei.verdict import active_text


FIELDS = ('Question', 'Context', 'Options', 'Musts', 'Wants', 'Recommendation',
          'Confidence', 'Reversibility', 'Blast radius', 'Pre-mortem', 'Revisit',
          'Decided-by', 'Outcome')
DECISION_ID = r'D-[1-9][0-9]*'


def table(text, columns, name):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows = [[cell.strip() for cell in line.removeprefix('|').removesuffix('|').split('|')]
            for line in lines]
    if len(rows) < 3 or rows[0] != columns:
        raise ValueError(f'{name}: expected columns {", ".join(columns)} and data rows')
    if (len(rows[1]) != len(columns) or
            any(not re.fullmatch(r':?-{3,}:?', cell) for cell in rows[1])):
        raise ValueError(f'{name}: invalid table separator')
    seen = set()
    for row in rows[2:]:
        if len(row) != len(columns) or not all(row):
            raise ValueError(f'{name}: missing or extra cell')
        if row[0] in seen:
            raise ValueError(f'{name}: duplicate {row[0]}')
        seen.add(row[0])
    return rows[2:]


def number(value, minimum, name):
    if not re.fullmatch(r'[0-9]{1,2}', value) or not minimum <= int(value) <= 10:
        raise ValueError(f'{name}: expected integer {minimum}..10')
    return int(value)


def evaluate(text):
    """Return validated fields and recomputed scores, or a content finding."""
    fields, current = {}, None
    for line in active_text(text).splitlines():
        match = re.match(r'^(?:#{1,6} )?(' + '|'.join(map(re.escape, FIELDS)) + r'):\s*(.*)$', line)
        if match:
            current, value = match.groups()
            if current in fields:
                raise ValueError(f'duplicate {current}: field')
            fields[current] = value
        elif re.match(r'^(?:#{1,6} )?(?:Consequences|Notes)(?::|$)', line):
            current = None
        elif line.strip() and current:
            fields[current] += '\n' + line
    missing = [key for key in FIELDS if not fields.get(key, '').strip()]
    if missing:
        raise ValueError('missing fields: ' + ', '.join(missing))
    for key in ('Question', 'Recommendation', 'Confidence', 'Reversibility', 'Decided-by'):
        if '\n' in fields[key]:
            raise ValueError(f'{key}: expected one line')
    for key, allowed in (('Confidence', ('high', 'medium', 'low')),
                         ('Reversibility', ('one-way', 'two-way', 'unsure')),
                         ('Decided-by', ('seat', 'owner'))):
        if fields[key] not in allowed:
            raise ValueError(f'{key}: expected {"|".join(allowed)}')
    options = table(fields['Options'], ['Option', 'Description'], 'Options')
    if len(options) < 2:
        raise ValueError('Options: expected at least two options')
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', row[0]) for row in options):
        raise ValueError('Options: invalid option id')
    if not any(re.match(r'(?i)(?:Do nothing|Defer)\b', row[1]) for row in options):
        raise ValueError('Options: include Do nothing or Defer')
    ids = [row[0] for row in options]
    musts = table(fields['Musts'], ['Criterion', *ids], 'Musts')
    if any(cell.lower() not in ('pass', 'fail') for row in musts for cell in row[1:]):
        raise ValueError('Musts: expected pass/fail for each option')
    passing = [option for index, option in enumerate(ids, 1)
               if all(row[index].lower() == 'pass' for row in musts)]
    wants = table(fields['Wants'], ['Criterion', 'Weight', *ids], 'Wants')
    scores = dict.fromkeys(ids, 0)
    for row in wants:
        weight = number(row[1], 1, 'Wants weight')
        for option, value in zip(ids, row[2:]):
            scores[option] += weight * number(value, 0, f'Wants score for {option}')
    recommendation = fields['Recommendation']
    if recommendation not in ids:
        raise ValueError('Recommendation: must name an option id')
    if not passing:
        raise ValueError('Musts: no passing option')
    best = max(passing, key=scores.get)
    if recommendation not in passing or scores[recommendation] < scores[best]:
        reason = 'fails a must; ' if recommendation not in passing else ''
        raise ValueError(f'Recommendation {recommendation} ({scores[recommendation]}) '
                         f'{reason}requires top passing option {best} ({scores[best]})')
    return fields, scores


def lint(text):
    try:
        fields, scores = evaluate(text)
        option = fields['Recommendation']
        return 0, f'OK: {option} ({scores[option]})'
    except ValueError as exc:
        return 1, f'{exc}\nREJECT: send back to the seat'


def record_rejection(path, code, message, *, root=None):
    if not code:
        return code, message
    try:
        if root is None:
            try:
                root = workspace.find_workspace(Path(path).parent)
            except FileNotFoundError:
                return code, message
        state.append_event('decision.rejected', {'file': str(path),
                           'reasons': message.splitlines()}, root=root)
    except (OSError, ValueError, RuntimeError) as exc:
        return 2, f'{message}\ndecision lint: could not record rejection: {exc}'
    return code, message


def clarification_fields(text):
    """Read active clarification fields in their recorded order."""
    fields, current = {}, None
    for line in active_text(text).splitlines():
        match = re.match(r'^(?:#{1,6} )?([A-Za-z][A-Za-z -]*):\s*(.*)$', line)
        if match:
            current, value = match.groups()
            if current not in ('Question', 'Context', 'Options'):
                raise ValueError(f'clarification: unexpected {current} field')
            if current in fields and current != 'Options':
                raise ValueError(f'clarification: duplicate {current} field')
            fields.setdefault(current, []).append(value)
        elif line.strip():
            if current is None or line.startswith('#'):
                raise ValueError('clarification: expected Question, Context and Options')
            fields[current].append(line)
    return fields


def lint_clarification(text, *, fields=None):
    """Clarifications carry evidence and options, without decision scoring."""
    if fields is None:
        try:
            fields = clarification_fields(text)
        except ValueError as exc:
            return 1, str(exc)
    question = fields.get('Question', [])
    context = fields.get('Context', [])
    options = [line.strip() for line in fields.get('Options', []) if line.strip()]
    if (len(question) != 1 or not question[0].strip() or not any(line.strip() for line in context)
            or len(set(options)) < 2 or any('|' in line for line in options)):
        return 1, 'clarification: require one-line Question, Context and at least two Options lines; no table'
    return 0, 'OK: clarification'


def lint_file(path, *, root=None, record=True, clarification=False):
    try:
        check = lint_clarification if clarification else lint
        code, message = check(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        code, message = 2, f'decision lint: could not read {path}: {exc}'
    return record_rejection(path, code, message, root=root) if record else (code, message)


def today_path(decision_id, root, *, clarification=False):
    pattern = r'C-[1-9][0-9]*' if clarification else DECISION_ID
    if not re.fullmatch(pattern, decision_id):
        raise ValueError('record id must be ' + ('C' if clarification else 'D') + '-<positive integer>')
    directory = workspace.day_dir(Path(root).resolve()) / 'decisions'
    path = directory / f'{decision_id}.md'
    if path.resolve() != path:
        raise ValueError(f'decision {decision_id}: record must belong to today')
    return path


def route(fields):
    return ('seat' if fields['Reversibility'] == 'two-way'
            and fields['Blast radius'] in ('own branch', 'own PR') else 'owner')


def write(text, root):
    """Validate and allocate a numbered decision without replacing an existing record."""
    evaluate(text)
    directory = workspace.day_dir(root) / 'decisions'
    directory.mkdir(parents=True, exist_ok=True)
    used = [int(path.stem[2:]) for path in directory.glob('D-*.md')
            if re.fullmatch(DECISION_ID, path.stem)]
    path = today_path(f'D-{max(used, default=0) + 1}', root)
    workspace.atomic_write(path, text, replace=False)
    return path
