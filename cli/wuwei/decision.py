"""One evaluator for decision records, saved files and routing."""

from pathlib import Path
import re

from wuwei import outward, state, workspace
from wuwei.cruise import CLASSES, CRUISE, level, running  # noqa: F401 (#283: kept light for the status line)
from wuwei.verdict import active_text
from wuwei.exits import DAMAGED


FIELDS = ('Question', 'Context', 'Options', 'Musts', 'Wants', 'Recommendation',
          'Confidence', 'Reversibility', 'Blast radius', 'Pre-mortem', 'Revisit',
          'Decided-by', 'Outcome')
DECISION_ID = r'D-[1-9][0-9]*'
# #475: classes whose options carry one line per configured lens.
ENGINEERING = ('design', 'boundary', 'refactor', 'dependency-bump')
LENSES = {'SOLID': 'Which SOLID principle does it keep or break?',
          'twelve-factor': 'Where relevant, how does it treat config, backing services, processes and dev-prod parity?',
          'YAGNI': 'What does it build that no item needs yet?',
          'ponytail': 'Is there a simpler thing that works: stdlib before custom, native before a dependency?'}
OPTION_COLUMNS = ['Option', 'Title', 'Rationale', 'Consequence']
OPTIONAL = ('Class', 'Reasoning', 'Lenses')
STATUS_QUO = r'(?i)(?:Do nothing|Defer|Keep)\b'  # #478: Keep owner-only is the status quo
# #530: two-way by definition (fix round, task round, seat procedure, parked item's next step).
ROUTINE = ('approach', 'retry', 'park', 'accept-residual')
# Design 5.8: the ambiguity threshold of cisr; the cruise margin is decisions.cruise.margin.
MARGIN = 0.2
NO_RECOMMENDATION = 'add the recommendation and the reasoning'


def lens_table(config):
    """The effective lenses: the defaults, then configured names; an empty question drops one."""
    return {name: question for name, question in
            {**LENSES, **config['decisions']['lenses']}.items() if question}


def table(text, columns, name):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows = [[cell.strip() for cell in line.removeprefix('|').removesuffix('|').split('|')]
            for line in lines]
    if len(rows) < 3 or rows[0] != columns:
        raise ValueError(f'{name}: expected columns {", ".join(columns)} and data rows; fix it in the record; bin/wuwei decision template shows a valid one')
    if (len(rows[1]) != len(columns) or
            any(not re.fullmatch(r':?-{3,}:?', cell) for cell in rows[1])):
        raise ValueError(f'{name}: invalid table separator; fix it in the record; bin/wuwei decision template shows a valid one')
    seen = set()
    for row in rows[2:]:
        if len(row) != len(columns) or not all(row):
            raise ValueError(f'{name}: missing or extra cell; fix it in the record; bin/wuwei decision template shows a valid one')
        if row[0] in seen:
            raise ValueError(f'{name}: duplicate {row[0]}; fix it in the record; bin/wuwei decision template shows a valid one')
        seen.add(row[0])
    return rows[2:]


def number(value, minimum, name):
    if not re.fullmatch(r'[0-9]{1,2}', value) or not minimum <= int(value) <= 10:
        raise ValueError(f'{name}: expected integer {minimum}..10; fix it in the record; bin/wuwei decision template shows a valid one')
    return int(value)


def options(fields):
    """Options rows; column 2 is the title (#475) or, in an earlier record, the description."""
    header = next((line for line in fields['Options'].splitlines() if line.strip()), '')
    legacy = [cell.strip() for cell in header.strip().strip('|').split('|')] == ['Option', 'Description']
    return table(fields['Options'], ['Option', 'Description'] if legacy else OPTION_COLUMNS, 'Options')


def _scored(fields):
    """Options, the ids passing every must, the Wants rows and the weighted scores."""
    rows = options(fields)
    if len(rows) < 2:
        raise ValueError('Options: expected at least two options; add another option, for example a Do nothing row; bin/wuwei decision template shows a valid record')
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', row[0]) for row in rows):
        raise ValueError('Options: invalid option id; use a letter, then letters, digits, dash or underscore, such as A or defer-1')
    if not any(re.match(STATUS_QUO, row[1]) for row in rows):
        raise ValueError('Options: include Do nothing, Defer or Keep; add a row whose title starts with Do nothing, Defer or Keep to Options, Musts and Wants')
    ids = [row[0] for row in rows]
    musts = table(fields['Musts'], ['Criterion', *ids], 'Musts')
    if any(cell.lower() not in ('pass', 'fail') for row in musts for cell in row[1:]):
        raise ValueError('Musts: expected pass/fail for each option; write pass or fail in every option cell')
    passing = [option for index, option in enumerate(ids, 1)
               if all(row[index].lower() == 'pass' for row in musts)]
    wants = table(fields['Wants'], ['Criterion', 'Weight', *ids], 'Wants')
    scores = dict.fromkeys(ids, 0)
    for row in wants:
        weight = number(row[1], 1, 'Wants weight')
        for option, value in zip(ids, row[2:]):
            scores[option] += weight * number(value, 0, f'Wants score for {option}')
    return rows, passing, wants, scores


def evaluate(text, lenses=None):
    """Return validated fields and recomputed scores, or a content finding. lenses (the
    effective lens table) turns on the #475 new-record checks; history readers leave it None."""
    fields, current = {}, None
    for line in active_text(text).splitlines():
        match = re.match(r'^(?:#{1,6} )?(' + '|'.join(map(re.escape, FIELDS + OPTIONAL)) + r'):\s*(.*)$', line)
        if match:
            current, value = match.groups()
            if current in fields:
                raise ValueError(f'duplicate {current}: field; {DAMAGED}')
            fields[current] = value
        elif re.match(r'^(?:#{1,6} )?(?:Consequences|Notes)(?::|$)', line):
            current = None
        elif line.strip() and current:
            fields[current] += '\n' + line
    missing = [key for key in FIELDS if not fields.get(key, '').strip()]
    if missing:
        fix = NO_RECOMMENDATION if 'Recommendation' in missing else 'add each one'
        raise ValueError('missing fields: ' + ', '.join(missing) + f'; {fix} (bin/wuwei decision template shows them all)')
    for key in ('Question', 'Recommendation', 'Confidence', 'Reversibility', 'Decided-by',
                'Class', 'Reasoning'):
        if '\n' in fields.get(key, ''):
            raise ValueError(f'{key}: expected one line; {DAMAGED}')
    cruise = re.fullmatch(r'cruise ([a-z-]+)@L[23]', fields['Decided-by'])  # #283: a cruise answer
    for key, allowed in (('Confidence', ('high', 'medium', 'low')),
                         ('Reversibility', ('one-way', 'two-way', 'unsure')),
                         ('Decided-by', ('seat', 'owner', 'mandate'))):
        if fields[key] not in allowed and not (key == 'Decided-by' and cruise and cruise[1] in CLASSES):
            raise ValueError(f'{key}: expected {"|".join(allowed)}; fix it in the record; bin/wuwei decision template shows a valid one')
    if 'Class' in fields and fields['Class'] not in CLASSES:
        raise ValueError(f'Class: expected one of {", ".join(CLASSES)}; fix it in the record; bin/wuwei decision template shows a valid one')
    options, passing, _, scores = _scored(fields)
    ids = [row[0] for row in options]
    recommendation = fields['Recommendation']
    if recommendation not in ids:
        raise ValueError('Recommendation: must name an option id; write the id of one row in Options')
    if not passing:
        raise ValueError('Musts: no passing option; add an option that meets every Must, or ask the owner whether a Must is too strict')
    best = max(passing, key=scores.get)
    if recommendation not in passing or scores[recommendation] < scores[best]:
        reason = 'fails a must; ' if recommendation not in passing else ''
        raise ValueError(f'Recommendation {recommendation} ({scores[recommendation]}) '
                         f'{reason}requires top passing option {best} ({scores[best]}); use that option as the Recommendation, or correct the Wants scores if they are wrong')
    if lenses is not None:
        _explained(fields, options, ids, lenses)
    return fields, scores


def _explained(fields, rows, ids, lenses):
    """#475: a new record carries Class, titled and explained options, Reasoning and lens lines."""
    hint = 'bin/wuwei decision template shows a valid one'
    for key in ('Class', 'Reasoning'):
        if not fields.get(key, '').strip():
            raise ValueError(f'missing fields: {key}; '
                             + (NO_RECOMMENDATION if key == 'Reasoning' else 'add it') + f' ({hint})')
    if len(rows[0]) != len(OPTION_COLUMNS):
        raise ValueError(f'Options: expected columns {", ".join(OPTION_COLUMNS)}; write a title, rationale and consequence for each option; {hint}')
    seen = set()
    for title in (row[1] for row in rows):
        if len(title) > 40 or re.search(r'["`$\\]', title) or title.casefold() in seen:
            raise ValueError(f'Options: title {title} must be unique, at most 40 characters, without a quote, backtick, $ or backslash; write a different title; {hint}')
        seen.add(title.casefold())
    if fields['Class'] in ENGINEERING and lenses:
        names = [row[0] for row in table(fields.get('Lenses', ''), ['Lens', *ids], 'Lenses')]
        missing = [name for name in lenses if name not in names]
        if missing:
            raise ValueError(f'Lenses: missing {", ".join(missing)}; add one line per option for each configured lens; {hint}')
        extra = [name for name in names if name not in lenses]
        if extra:
            raise ValueError(f'Lenses: unknown lens {", ".join(extra)}; remove it, the configured lenses are {", ".join(lenses)}')


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
    lenses = lens_lines(fields) if level == 'standard' else {}
    lines = [f'{identifier}: {fields["Question"]}']
    for row in options:
        option = row[0]
        lines.append(f'{option}: {row[1]} (score {scores[option]}'
                     + ('' if option in passing else ', fails a must') + ')'
                     + (f'. {row[3]}' if len(row) == 4 else ''))
        if level == 'standard' and len(row) == 4:
            lines += [f'  Rationale: {row[2]}', *(f'  {line}' for line in lenses.get(option, []))]
    lines.append(f'Recommended: {chosen}, {reason}.'
                 + (f' {fields["Reasoning"]}' if fields.get('Reasoning') else ''))
    if level == 'standard':
        first = {name: next(line.strip() for line in fields[name].splitlines() if line.strip())
                 for name in ('Context', 'Blast radius', 'Pre-mortem', 'Revisit')}
        lines += [f'Context: {first["Context"]}',
                  f'Confidence: {fields["Confidence"]}. Reversibility: {fields["Reversibility"]}.',
                  *(f'{name}: {first[name]}' for name in ('Blast radius', 'Pre-mortem', 'Revisit'))]
    return '\n'.join(lines)


# The command that records an owner's answer to a D-n widget; <label> is the chosen option.
RECORD = 'wuwei decide {id} "<label>"'


def first(text):
    """The first sentence of text."""
    return re.split(r'(?<=[.!?])\s+', text.strip(), maxsplit=1)[0]


def lens_lines(fields):
    """#475: option id -> its '<lens>: <line>' lines, for an engineering record with lenses."""
    if fields.get('Class') not in ENGINEERING or not fields.get('Lenses'):
        return {}
    ids = [row[0] for row in options(fields)]
    rows = table(fields['Lenses'], ['Lens', *ids], 'Lenses')
    return {option: [f'{row[0]}: {row[index]}' for row in rows] for index, option in enumerate(ids, 1)}


def widget(question, header, options, record, *, multi=False):
    """One AskUserQuestion question (the session passes all but `record`) and the one command
    that records its answer. options: (label, description) pairs, the recommended first."""
    if len(header) > 12 or not 2 <= len(options) <= 4:
        raise ValueError(f'widget {header}: expected a header of at most 12 characters and 2 to 4 options; pass a shorter header and 2 to 4 options')
    return {'question': question, 'header': header, 'multiSelect': multi,
            'options': [{'label': label, 'description': text} for label, text in options],
            'record': record}


def gate(root):
    """The morning gate citation the question guard accepts for questions without a record."""
    return f'Morning gate (days/{workspace.day_dir(root).name}/plan.md): '


def record_widget(identifier, fields, record=RECORD, level='brief', hidden=False):
    """A decision that passed the new-record check as a widget: titles as labels, the
    recommendation first; rationale, consequence and lens lines, trimmed at brief. hidden (the
    #283 weekly sample) keeps record order and shows neither the recommendation nor its reasons."""
    chosen = fields['Recommendation']
    rows = options(fields) if hidden else sorted(options(fields), key=lambda row: row[0] != chosen)
    lenses = {} if hidden else lens_lines(fields)
    trim = first if level == 'brief' else str.strip
    # ponytail: AskUserQuestion shows four options; the others stay answerable through Other.
    return widget(f'{identifier}: {fields["Question"]}' + ('' if hidden else f' {first(fields["Reasoning"])}'),
                  identifier,
                  [(title + (' (Recommended)' if option == chosen and not hidden else ''),
                    '\n'.join(trim(part) for part in ((consequence,) if hidden else
                                                       (rationale, consequence, *lenses.get(option, [])))))
                   for option, title, rationale, consequence in rows[:4]], record.format(id=identifier))


def option_id(fields, label):
    """The option id a widget label (a title, maybe marked Recommended) or an id names; else
    the label unchanged, so the caller's not-in-the-record refusal fires."""
    wanted = label.removesuffix(' (Recommended)').casefold()
    return next((row[0] for row in options(fields) if wanted in (row[0].casefold(), row[1].casefold())), label)


def lint(text, lenses=LENSES):
    try:
        fields, scores = evaluate(text, lenses)
        option = fields['Recommendation']
        found = outward.tells(text)
        return 0, f'OK: {option} ({scores[option]}), {cisr(fields, scores)}' + ('\nstyle: ' + ', '.join(found) if found else '')
    except ValueError as exc:
        return 1, f'{exc}\nREJECT: send back to the seat; fix what is named above and check again with bin/wuwei decision lint <file>'


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
        return 2, f'{message}\ndecision lint: could not record rejection: {exc}; run bin/wuwei doctor'
    return code, message


def clarification_fields(text):
    """Read active clarification fields in their recorded order."""
    fields, current = {}, None
    for line in active_text(text).splitlines():
        match = re.match(r'^(?:#{1,6} )?([A-Za-z][A-Za-z -]*):\s*(.*)$', line)
        if match:
            current, value = match.groups()
            if current not in ('Question', 'Context', 'Options'):
                raise ValueError(f'clarification: unexpected {current} field; remove that field or fold its text into Context')
            if current in fields and current != 'Options':
                raise ValueError(f'clarification: duplicate {current} field; write the two as one field; only Options may repeat')
            fields.setdefault(current, []).append(value)
        elif line.strip():
            if current is None or line.startswith('#'):
                raise ValueError('clarification: expected Question, Context and Options; write every line under a Question, Context or Options field')
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
        return 1, 'clarification: require one-line Question, Context and at least two Options lines; no table; write the file in that shape and save it again'
    return 0, 'OK: clarification'


def lint_file(path, *, root=None, record=True, clarification=False):
    try:
        text = Path(path).read_text(encoding='utf-8')
        if clarification:
            code, message = lint_clarification(text)
        else:
            if root is None:
                try:
                    root = workspace.find_workspace(Path(path).parent)
                except FileNotFoundError:
                    pass
            code, message = lint(text, lens_table(workspace.load_config(root)) if root else LENSES)
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        code, message = 2, f'decision lint: could not read {path}: {exc}'
    return record_rejection(path, code, message, root=root) if record else (code, message)


def today_path(decision_id, root, *, clarification=False):
    pattern = r'C-[1-9][0-9]*' if clarification else DECISION_ID
    if not re.fullmatch(pattern, decision_id):
        prefix = 'C' if clarification else 'D'
        raise ValueError(f'record id must be {prefix}-<positive integer>; use an id such as {prefix}-1')
    directory = workspace.day_dir(Path(root).resolve()) / 'decisions'
    path = directory / f'{decision_id}.md'
    if path.resolve() != path:
        raise ValueError(f'decision {decision_id}: record must belong to today; write the record in today\'s decisions folder')
    return path


def margin(fields, scores):
    """Design 5.8.1: the lead over the best other option, over the most the weights allow."""
    chosen = fields['Recommendation']
    return ((scores[chosen] - max(score for option, score in scores.items() if option != chosen))
            / (10 * sum(int(row[1]) for row in _scored(fields)[2])))


def cisr(fields, scores):
    """#530: the MIT CISR class from risk (door and blast radius) and ambiguity (confidence, margin)."""
    if fields.get('Class') in ROUTINE and fields['Reversibility'] != 'one-way':
        return 'Routine'  # two-way by definition unless the seat wrote one-way
    low_risk = (fields['Reversibility'] == 'two-way'
                and re.match(r'(?i)\s*(?:item|own branch|own pr|day)\b', fields['Blast radius']))
    clear = fields['Confidence'] != 'low' and margin(fields, scores) >= MARGIN
    return ('Routine' if clear else 'Exploratory') if low_risk else ('Consequential' if clear else 'Strategic')


def route(fields):
    return ('seat' if fields['Reversibility'] == 'two-way'
            and fields['Blast radius'] in ('own branch', 'own PR') else 'owner')


def route_owner(identifier, fields, root, item=None, thin=False):
    """Record an owner route once; a repeat route is a no-op. An item marks an external wait."""
    def mark(data):
        data.setdefault('decision_routes', {}).setdefault(identifier, data_row)
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
    from wuwei import novelty
    kind = cisr(fields, _scored(fields)[3])
    extra = {'class': fields.get('Class'), 'thin': thin, 'at': workspace.now().isoformat()}  # #283
    data_row = {'reversibility': fields['Reversibility'], 'recommendation': fields['Recommendation'],
                'cisr': kind, **extra}
    payload = {'id': identifier, 'reversibility': fields['Reversibility'], 'cisr': kind, **extra}
    novel = novelty.novel(root, workspace.load_config(root), novelty.record_keys(fields))
    if novel:  # #556: the owner's answer clears these
        data_row['novel'] = payload['novel'] = novel
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
            raise ValueError(f'{name}: invalid external wait record; {DAMAGED}')
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


def seat_outcome(fields, scores, by='seat'):
    """Snapshot a validated seat (or #530 mandate) decision, including any item disposition."""
    if by == 'seat' and (route(fields) != 'seat' or fields['Decided-by'] != 'seat'):
        raise ValueError('Decided-by must be seat for a seat-routed decision; use owner as Decided-by, or fix Reversibility and Blast radius. A seat decides only a two-way decision on its own branch or PR')
    return {'option': fields['Recommendation'], 'score': scores[fields['Recommendation']],
            'decided_by': by, 'outcome': fields['Recommendation'],
            'reversibility': fields['Reversibility'], 'blast_radius': fields['Blast radius'],
            'item_disposition': fields['Outcome'], 'cisr': cisr(fields, scores),
            'class': fields.get('Class')}


def set_outcome(text, option):
    # ponytail: rewrites the first Outcome: line; a record with an inactive example
    # Outcome: above the real field needs the active line from verdict.active_text.
    return re.sub(r'^((?:#{1,6} )?Outcome:).*$', lambda m: f'{m[1]} {option}', text, count=1, flags=re.M)


def owner_confirm(root, identifier, digest, prompt):
    """Where the owner answered: the planner session's asked gate question, else y/N at the
    host terminal (#354); '' when declined. OSError without a terminal propagates."""
    from wuwei import sessions
    if identifier in sessions.gate_topics(root, sessions.current())[0]:
        return 'in the planner session'
    from wuwei.integrity import _host_confirm
    return 'at the host terminal' if _host_confirm(digest, prompt=prompt) else ''


def decided_record(text, option, by):
    """The record with its Outcome and Decided-by lines set."""
    return re.sub(r'^((?:#{1,6} )?Decided-by:).*$', rf'\1 {by}', set_outcome(text, option), count=1, flags=re.M)


def owner_record(text, option, where, note=None):
    """The record after the owner's answer: Outcome, Decided-by: owner and one Notes line."""
    text = decided_record(text, option, 'owner')
    stamp = workspace.now().isoformat(timespec='seconds')
    return text.rstrip('\n') + f'\nNotes: Decided at {stamp} {where}.' + (f' {note}' if note else '') + '\n'


def write(text, root):
    """Validate and allocate a numbered decision without replacing an existing record."""
    evaluate(text, lens_table(workspace.load_config(root)))
    directory = workspace.day_dir(root) / 'decisions'
    directory.mkdir(parents=True, exist_ok=True)
    used = [int(path.stem[2:]) for path in directory.glob('D-*.md')
            if re.fullmatch(DECISION_ID, path.stem)]
    path = today_path(f'D-{max(used, default=0) + 1}', root)
    workspace.atomic_write(path, text, replace=False)
    return path
