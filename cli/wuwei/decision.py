"""The D-n record library the learning cards and the MCP registry cards still use (parts 16, 18)."""

from pathlib import Path
import re

from wuwei import state, workspace
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
OPTIONAL = ('Class', 'Reasoning', 'Lenses', 'Role', 'Value', 'Previous')  # #600: config cards
STATUS_QUO = r'(?i)(?:Do nothing|Defer|Keep)\b'  # Keep is the status quo
CLASSES = ('approach', 'retry', 'park', 'accept-residual', 'defer', 'scope-cut', 're-plan', 'dependency-bump',
           'design', 'boundary', 'refactor', 'merge', 'message', 'other')  # design 5.8.1
NO_RECOMMENDATION = 'add the recommendation and the reasoning'


def table(text, columns, name):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows = [[cell.strip() for cell in line.removeprefix('|').removesuffix('|').split('|')]
            for line in lines]
    if len(rows) < 3 or rows[0] != columns:
        raise ValueError(f'{name}: expected columns {", ".join(columns)} and data rows; write the record again with it fixed')
    if (len(rows[1]) != len(columns) or
            any(not re.fullmatch(r':?-{3,}:?', cell) for cell in rows[1])):
        raise ValueError(f'{name}: invalid table separator; write the record again with it fixed')
    seen = set()
    for row in rows[2:]:
        if len(row) != len(columns) or not all(row):
            raise ValueError(f'{name}: missing or extra cell; write the record again with it fixed')
        if row[0] in seen:
            raise ValueError(f'{name}: duplicate {row[0]}; write the record again with it fixed')
        seen.add(row[0])
    return rows[2:]


def number(value, minimum, name):
    if not re.fullmatch(r'[0-9]{1,2}', value) or not minimum <= int(value) <= 10:
        raise ValueError(f'{name}: expected integer {minimum}..10; write the record again with it fixed')
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
        raise ValueError('Options: expected at least two options; add another option, for example a Do nothing row')
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


def evaluate(text, lenses=None, write=False):
    """Return validated fields and recomputed scores, or a content finding. lenses (the
    effective lens table) turns on the #475 new-record checks; history readers leave it None.
    write (lint, write, the scanner) refuses a #814 legacy cruise answer that a read takes as mandate."""
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
        raise ValueError('missing fields: ' + ', '.join(missing) + f'; {fix}, then write the record again')
    for key in ('Question', 'Recommendation', 'Confidence', 'Reversibility', 'Decided-by',
                'Class', 'Reasoning', 'Role', 'Previous'):
        if '\n' in fields.get(key, ''):
            raise ValueError(f'{key}: expected one line; {DAMAGED}')
    if not write and re.fullmatch(r'cruise [a-z-]+@L[23]', fields['Decided-by']):
        fields['Decided-by'] = 'mandate'  # #814: a record written before the upgrade
    for key, allowed in (('Confidence', ('high', 'medium', 'low')),
                         ('Reversibility', ('one-way', 'two-way', 'unsure')),
                         ('Decided-by', ('seat', 'owner', 'mandate'))):
        if fields[key] not in allowed:
            raise ValueError(f'{key}: expected {"|".join(allowed)}; write the record again with it fixed')
    if 'Class' in fields and fields['Class'] not in CLASSES:
        raise ValueError(f'Class: expected one of {", ".join(CLASSES)}; write the record again with it fixed')
    from wuwei.commands.agents import ROLES
    if 'Role' in fields and fields['Role'] not in ROLES:
        raise ValueError(f'Role: expected one of {", ".join(ROLES)}; write the record again with it fixed')
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
    hint = 'write the record again with it fixed'
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


def card_hash(identifier, fields):
    """#599: the card the owner saw (Question and Options), as the widget's record command carries it."""
    from wuwei.sessions import card_topic
    return card_topic(identifier, f'{fields["Question"]}\n{fields["Options"]}').split('=', 1)[1][:12]


def record_widget(identifier, fields, record, level='brief', *, root):
    """A decision that passed the new-record check as a widget: titles as labels, the
    recommendation first; rationale, consequence and lens lines, trimmed at brief."""
    chosen = fields['Recommendation']
    rows = sorted(options(fields), key=lambda row: row[0] != chosen)
    lenses = lens_lines(fields)
    trim = first if level == 'brief' else str.strip
    # ponytail: AskUserQuestion shows four options; the others stay answerable through Other.
    return widget(f'{identifier}: {fields["Question"]} {first(fields["Reasoning"])}',
                  identifier,
                  [(title + (' (Recommended)' if option == chosen else ''),
                    '\n'.join(trim(part) for part in (rationale, consequence, *lenses.get(option, []))))
                   for option, title, rationale, consequence in rows[:4]],
                  record.format(id=identifier, cli=workspace.owner_cli(root), card=card_hash(identifier, fields)))


def option_id(fields, label):
    """The option id a widget label (a title, maybe marked Recommended) or an id names; else
    the label unchanged, so the caller's not-in-the-record refusal fires."""
    wanted = label.removesuffix(' (Recommended)').casefold()
    return next((row[0] for row in options(fields) if wanted in (row[0].casefold(), row[1].casefold())), label)


def today_path(decision_id, root):
    if not re.fullmatch(DECISION_ID, decision_id):
        raise ValueError('record id must be D-<positive integer>; use an id such as D-1')
    directory = workspace.day_dir(Path(root).resolve()) / 'decisions'
    path = directory / f'{decision_id}.md'
    if path.resolve() != path:
        raise ValueError(f'decision {decision_id}: record must belong to today; write the record in today\'s decisions folder')
    return path


def route_owner(identifier, fields, root):
    """Record an owner route once; a repeat route is a no-op."""
    if identifier in state.read_state(root).get('decision_routes', {}):
        return
    extra = {'class': fields.get('Class'), 'at': workspace.now().isoformat()}
    data_row = {'reversibility': fields['Reversibility'], 'recommendation': fields['Recommendation'], **extra}
    state._write_state(lambda data: data.setdefault('decision_routes', {}).setdefault(identifier, data_row),
                       root, reserved=False, kind='decision.routed',
                       payload={'id': identifier, 'reversibility': fields['Reversibility'], **extra})


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


def set_outcome(text, option):
    # ponytail: rewrites the first Outcome: line; a record with an inactive example
    # Outcome: above the real field needs the active line from verdict.active_text.
    return re.sub(r'^((?:#{1,6} )?Outcome:).*$', lambda m: f'{m[1]} {option}', text, count=1, flags=re.M)


def owner_confirm(root, identifier, digest, prompt, card=None, fields=None):
    """Where the owner answered: the planner session's asked gate question, else y/N at the
    host terminal (#354); '' when declined. A card hash (#599) confirms only the asked card of
    the record as it stands and never prompts. OSError without a terminal propagates."""
    from wuwei import sessions
    if card is not None and card != card_hash(identifier, fields):
        return ''  # the record changed since its card, or not its card hash
    if identifier in sessions.gate_topics(root, sessions.caller(root, card is not None))[0]:
        return 'in the planner session'
    if card is not None:
        return ''
    from wuwei.integrity import _host_confirm
    return 'at the host terminal' if _host_confirm(digest, prompt=prompt) else ''


def no_card(identifier):
    """#599: the reason a --card record command has no card answer to confirm it."""
    return (f'decision: {identifier} has no card answer for this record from the planner session; '
            'ask its card with AskUserQuestion in the planner session, then run its record command')


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
    evaluate(text, LENSES, write=True)
    directory = workspace.day_dir(root) / 'decisions'
    directory.mkdir(parents=True, exist_ok=True)
    used = [int(path.stem[2:]) for path in directory.glob('D-*.md')
            if re.fullmatch(DECISION_ID, path.stem)]
    path = today_path(f'D-{max(used, default=0) + 1}', root)
    workspace.atomic_write(path, text, replace=False)
    return path
