"""One evaluator for decision records, saved files and routing."""

from pathlib import Path
import re

from wuwei import outward, state, workspace
from wuwei.verdict import active_text


FIELDS = ('Question', 'Context', 'Options', 'Musts', 'Wants', 'Recommendation',
          'Confidence', 'Reversibility', 'Blast radius', 'Pre-mortem', 'Revisit',
          'Decided-by', 'Outcome')
DECISION_ID = r'D-[1-9][0-9]*'
# Design 5.8.1: class -> (default cruise level, ceiling). A new class is a design amendment.
CLASSES = {'approach': (2, 3), 'retry': (2, 3), 'park': (2, 3), 'accept-residual': (2, 3),
           'defer': (0, 3), 'scope-cut': (0, 3), 're-plan': (0, 3), 'dependency-bump': (0, 3),
           'merge': (3, 3), 'message': (0, 1), 'other': (0, 1)}


def level(config, name):
    """The cruise level a class runs at; config only lowers the default."""
    # ponytail: memory/cruise.json (running level, #283) does not exist yet; the default stands in.
    cruise = config['decisions']['cruise']
    return min(CLASSES[name][0], cruise['levels'].get(name, 3)) if cruise['enabled'] else 0


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


def _scored(fields):
    """Options, the ids passing every must, the Wants rows and the weighted scores."""
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
    return options, passing, wants, scores


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
    options, passing, _, scores = _scored(fields)
    ids = [row[0] for row in options]
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


def present(identifier, fields, level):
    """The owner's view of validated fields at brief or standard; full is the record text."""
    options, passing, wants, scores = _scored(fields)
    ids = [row[0] for row in options]
    chosen = fields['Recommendation']
    others = [option for option in passing if option != chosen]
    if not others:
        reason = 'the only option that passes every must'
    else:
        other = max(others, key=scores.get)
        if scores[other] == scores[chosen]:
            reason = f'tied with {other} on score'
        else:
            lead = max(wants, key=lambda row: int(row[1]) * (
                int(row[2 + ids.index(chosen)]) - int(row[2 + ids.index(other)])))
            reason = f'ahead of {other} on {lead[0]}'
    lines = [f'{identifier}: {fields["Question"]}',
             *(f'{option}: {text} (score {scores[option]}'
               + ('' if option in passing else ', fails a must') + ')' for option, text in options),
             f'Recommended: {chosen}, {reason}.']
    if level == 'standard':
        first = {name: next(line.strip() for line in fields[name].splitlines() if line.strip())
                 for name in ('Context', 'Blast radius', 'Pre-mortem', 'Revisit')}
        lines += [f'Context: {first["Context"]}',
                  f'Confidence: {fields["Confidence"]}. Reversibility: {fields["Reversibility"]}.',
                  *(f'{name}: {first[name]}' for name in ('Blast radius', 'Pre-mortem', 'Revisit'))]
    return '\n'.join(lines)


# The command that records an owner's answer to a D-n widget; <label> is the chosen option.
RECORD = 'wuwei decision outcome {id} <label>'


def widget(question, header, options, record, *, multi=False):
    """One AskUserQuestion question (the session passes all but `record`) and the one command
    that records its answer. options: (label, description) pairs, the recommended first."""
    if len(header) > 12 or not 2 <= len(options) <= 4:
        raise ValueError(f'widget {header}: expected a header of at most 12 characters and 2 to 4 options')
    return {'question': question, 'header': header, 'multiSelect': multi,
            'options': [{'label': label, 'description': text} for label, text in options],
            'record': record}


def gate(root):
    """The morning gate citation the question guard accepts for questions without a record."""
    return f'Morning gate (days/{workspace.day_dir(root).name}/plan.md): '


def record_widget(identifier, fields, record=RECORD):
    """A validated decision as a widget: the recommendation first, the record's options."""
    chosen = fields['Recommendation']
    rows = sorted(table(fields['Options'], ['Option', 'Description'], 'Options'),
                  key=lambda row: row[0] != chosen)
    # ponytail: AskUserQuestion shows four options; the others stay answerable through Other.
    return widget(f'{identifier}: {fields["Question"]}', identifier,
                  [(option, f'Recommended. {text}' if option == chosen else text)
                   for option, text in rows[:4]], record.format(id=identifier))


def lint(text):
    try:
        fields, scores = evaluate(text)
        option = fields['Recommendation']
        found = outward.tells(text)
        return 0, f'OK: {option} ({scores[option]})' + ('\nstyle: ' + ', '.join(found) if found else '')
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


def route_owner(identifier, fields, root, item=None):
    """Record an owner route once; a repeat route is a no-op. An item marks an external wait."""
    def mark(data):
        data.setdefault('decision_routes', {}).setdefault(identifier, {
            'reversibility': fields['Reversibility'], 'recommendation': fields['Recommendation']})
        if item is not None:
            if item not in data['items']:
                raise state.StateError(f'unknown item: {item}')
            data['items'][item]['assumption'] = {
                'kind': 'external', 'decision': identifier, 'day': workspace.day_dir(root).name,
                'since': workspace.now().isoformat(), 'status': 'waiting'}

    data = state.read_state(root)
    if identifier in data.get('decision_routes', {}) and (
            item is None or data['items'].get(item, {}).get('assumption', {}).get('decision') == identifier):
        return
    payload = {'id': identifier, 'reversibility': fields['Reversibility']}
    state._write_state(mark, root, reserved=False, kind='decision.routed',
                       payload=payload if item is None else {**payload, 'item': item})


def weekday_hours(start, end, zone):
    """Whole hours from start to end that begin Monday to Friday in zone."""
    # ponytail: hourly steps; a wait spanning months walks a few thousand hours.
    from datetime import timedelta, timezone
    hour, end, count = start.astimezone(timezone.utc), end.astimezone(timezone.utc), 0
    while hour + timedelta(hours=1) <= end:
        count += hour.astimezone(zone).weekday() < 5
        hour += timedelta(hours=1)
    return count


def waits(root):
    """Design 5.8.2 time box: past wait_hours, confirm a two-way door or park the item."""
    from datetime import datetime
    config = workspace.load_config(root)
    now, changed = workspace.now(), 0
    for name, item in state.read_state(root)['items'].items():
        wait = item.get('assumption')
        if not isinstance(wait, dict) or wait.get('status') != 'waiting':
            continue
        directory = Path(root) / '.wuwei/days' / wait['day']
        path = directory / 'decisions' / f'{wait["decision"]}.md'
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', wait['day']) or path.is_symlink():
            raise ValueError(f'{name}: invalid external wait record')
        if (answered(state.read_state(directory=directory), wait['decision']) is not None
                or weekday_hours(datetime.fromisoformat(wait['since']), now, workspace.zone(config))
                < config['decisions']['wait_hours']):
            continue
        fields, _ = evaluate(path.read_text(encoding='utf-8'))
        confirm = (fields['Reversibility'] == 'two-way' and item.get('goal') != 'unplanned'
                   and not item['flags']['trust_surface'])
        outcome = 'confirmed' if confirm else 'parked'

        def update(data, name=name, outcome=outcome):
            current = data['items'][name]
            current['assumption']['status'] = outcome
            if outcome == 'parked' and current['phase'] not in ('parked', 'escalated', 'merged'):
                current.update(phase='parked', status='blocked', decision=wait['decision'])

        payload = {'item': name, 'id': wait['decision'], 'outcome': outcome}
        if confirm:
            payload['recommendation'] = fields['Recommendation']
        state._write_state(update, root, reserved=False, kind='decision.waited', payload=payload)
        changed += 1
    return changed


def naming(directory, items):
    """Map each D-n and C-n record of a day to the items its Question: or Context: line names."""
    found = {}
    for path in sorted((Path(directory) / 'decisions').glob('[DC]-*.md')):
        if path.is_symlink() or not re.fullmatch(r'[DC]-[1-9][0-9]*', path.stem):
            continue
        lines = [line for line in active_text(path.read_text(encoding='utf-8')).splitlines()
                 if re.match(r'(?:#{1,6} )?(?:Question|Context):', line)]
        found[path.stem] = [item for item in items if any(
            re.search(r'(?<![\w-])' + re.escape(item) + r'(?![\w-])', line) for line in lines)]
    return found


def answered(data, identifier):
    """Return the owner's recorded option for a decision, or None while it is unanswered."""
    record = data.get('decision_outcomes', {}).get(identifier)
    return record.get('option') if isinstance(record, dict) and record.get('decided_by') == 'owner' else None


def seat_outcome(fields, scores):
    """Snapshot a validated seat decision, including any explicit item disposition."""
    if route(fields) != 'seat' or fields['Decided-by'] != 'seat':
        raise ValueError('Decided-by must be seat for a seat-routed decision')
    return {'option': fields['Recommendation'], 'score': scores[fields['Recommendation']],
            'decided_by': 'seat', 'outcome': fields['Recommendation'],
            'reversibility': fields['Reversibility'], 'blast_radius': fields['Blast radius'],
            'item_disposition': fields['Outcome']}


def set_outcome(text, option):
    # ponytail: rewrites the first Outcome: line; a record with an inactive example
    # Outcome: above the real field needs the active line from verdict.active_text.
    return re.sub(r'^((?:#{1,6} )?Outcome:).*$', lambda m: f'{m[1]} {option}', text, count=1, flags=re.M)


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
