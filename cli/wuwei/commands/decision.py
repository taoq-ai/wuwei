"""Lint, route and record outcomes through the shared evaluator and state writer."""

import hashlib
import json
import sys

from wuwei import novelty, state, workspace
from wuwei.decision import (LENSES, RECORD, ROUTINE, cisr, uncalibrated, decided_record, evaluate, lens_table, lint_file, margin,
                            no_card, option_id, options, owner_confirm, owner_record, present, record_rejection,
                            record_widget, route, route_owner, seat_outcome, today_path, widget)
from wuwei.exits import RACE, SYMLINK


CONFIG_RECORD = 'wuwei config set --from-card {id}'  # #600: the answered option names the value


def register(subparsers):
    parser = subparsers.add_parser('decision', help='Check and route decision records')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('template', help='Print a valid decision record').set_defaults(func=run)
    lint = commands.add_parser('lint', help='Lint a saved decision file')
    lint.add_argument('file')
    lint.set_defaults(func=run)
    command = commands.add_parser('route', help='Route a decision today')
    command.add_argument('id')
    command.add_argument('--external', metavar='ITEM',
                         help='a confirmation from a person outside the loop; continue reversible work')
    command.set_defaults(func=run)
    outcome = commands.add_parser('outcome', help='Record an owner choice from the host terminal')
    outcome.add_argument('id')
    outcome.add_argument('option')
    outcome.add_argument('--card', '--from-card', dest='card', metavar='HASH',
                         help="the owner's answer hash on the card (#661; the CLI binds it with #599)")
    outcome.set_defaults(func=run)
    show = commands.add_parser('show', help='Print a decision at the owner verbosity level')
    show.add_argument('id')
    form = show.add_mutually_exclusive_group()
    form.add_argument('--full', action='store_true', help='Print every field')
    form.add_argument('--widget', action='store_true',
                      help='Print the decision as an AskUserQuestion widget with its recording command')
    show.set_defaults(func=run)
    undo = commands.add_parser('undo', help='Undo a cruise answer inside its window and ask the owner')
    undo.add_argument('id')
    undo.add_argument('--answer', help='the owner answer on the undo card: Keep or Undo')
    undo.set_defaults(func=run)


def decide(args):
    root = workspace.find_workspace()
    path = today_path(args.id, root)
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        return record_rejection(path, 2, f'decision: could not read {path}: {exc}', root=root)
    try:
        fields, scores = evaluate(text)
    except ValueError as exc:
        return record_rejection(path, 1, str(exc), root=root)
    from wuwei import undo
    text, fields, said = undo.correct(args.id, path, text, fields, root)  # #557: first route only
    said = '\n' + said if said else ''
    if args.external:
        from wuwei.brief import identifier
        try:
            route_owner(args.id, fields, root, item=identifier(args.external))
        except ValueError as exc:
            return 1, f'decision: {exc}'
        return 0, 'owner' + said
    config = workspace.load_config(root)
    if config['autonomy']['mode'] == 'autonomous':
        decided = mandate(args.id, path, text, fields, scores, root, config)
        if decided:
            return 0, decided + said
    target = route(fields)
    if target == 'owner':
        from wuwei import cruise
        thin = cruise.thin(root, fields, scores, config)
        route_owner(args.id, fields, root, thin=thin)
        return 0, target + said
    try:
        record = seat_outcome(fields, scores)
    except ValueError as exc:
        return record_rejection(path, 1, str(exc), root=root)

    def update(data):
        data.setdefault('decision_outcomes', {})[args.id] = record

    state._write_state(update, root, reserved=False, kind='decision.decided',
                       payload={'id': args.id, **record})
    return 0, target


def mandate(ident, path, text, fields, scores, root, config):
    """#530 under autonomous: who already holds ident, or 'mandate' after taking a Routine,
    Consequential or scoring Exploratory record as recommended; None for the legacy route.
    #283: a taken record whose class cruises is written with its rule and undo window."""
    data = state.read_state(root)
    if ident in data.get('decision_routes', {}):
        return 'owner'
    if ident in data.get('decision_outcomes', {}):
        return data['decision_outcomes'][ident].get('decided_by')
    from wuwei.decision import config_keys
    if config_keys(fields):
        return None  # #529: a config value is the owner's answer on its card
    novel = novelty.novel(root, workspace.load_config(root), novelty.record_keys(fields))
    if novel:  # #556: a target the workspace never touched asks once (design 5.8.1)
        route_owner(ident, fields, root)
        return 'owner\n' + novelty.line(novel)
    door = fields['Reversibility']
    if fields['Decided-by'] == 'owner' or door == 'one-way' or (door != 'two-way' and fields.get('Class') not in ROUTINE):
        return None  # one-way doors and records written for the owner still ask (review F1)
    kind = cisr(fields, scores, ambiguous=bool(uncalibrated(root, fields)))  # #559
    if kind == 'Strategic' or (kind == 'Exploratory' and margin(fields, scores) <= 0):
        return None
    from wuwei import cruise
    found = cruise.rule(root, ident, fields, scores, config, data) or {}
    record = {**seat_outcome(fields, scores, by='mandate'), 'cisr': kind, **found}

    def update(current):
        if ident in current.get('decision_routes', {}) or ident in current.get('decision_outcomes', {}):
            raise ValueError(f'decision changed during routing; {RACE}')
        current.setdefault('decision_outcomes', {})[ident] = record

    by = found.get('rule', 'mandate')
    state._write_state(update, root, reserved=False, kind='decision.decided',
                       payload={'id': ident, **record, 'decided_by': by})
    kept = fields['Outcome'].startswith(('carried ', 'parked '))  # an item disposition stays (review F2)
    workspace.atomic_write(path, decided_record(text, fields['Outcome'] if kept else record['option'], by))
    try:  # #560: what a shadow level would have answered; the live route above stands either way
        cruise.shadow(root, ident, record, fields, scores, config, data)
    except (OSError, ValueError) as exc:
        print(f'wuwei decision route: shadow not written: {exc}', file=sys.stderr)
    return 'mandate'


def show(args):
    root = workspace.find_workspace()
    path = today_path(args.id, root)  # A symlinked record raises: it must belong to today.
    config = workspace.load_config(root)
    try:
        text = path.read_text(encoding='utf-8')
        fields, _ = evaluate(text, lens_table(config) if args.widget else None)
    except FileNotFoundError:  # #362: a state answer; --widget callers read JSON, so a finding there.
        return int(bool(args.widget)), f'No {args.id} today; bin/wuwei nudges --all lists open decisions.'
    except (OSError, UnicodeError) as exc:
        return 2, (f'decision show: could not read {path.relative_to(root)}: {type(exc).__name__}; '
                   'check the file is readable, then run bin/wuwei doctor')
    except ValueError as exc:
        return 1, f'decision show: {exc}'
    level = 'full' if args.full else workspace.verbosity(config, 'decisions')
    if args.widget:  # --widget and --full exclude each other
        row = state.read_state(root).get('decision_outcomes', {}).get(args.id, {})
        if row.get('decided_by') == 'mandate':
            from wuwei import cruise
            until = cruise.window(row)
            if until:  # #283: an open undo window asks Keep or Undo
                title = next(r[1] for r in options(fields) if r[0] == row['option'])
                return 0, json.dumps([widget(
                    f'{args.id}: Taken as {title} by {row["rule"]}. Undo it before {cruise.clock(until)}?',
                    args.id, [('Keep (Recommended)', 'Leave the answer as taken.'),
                              ('Undo', 'Revert the answer and ask you instead.')],
                    f'wuwei decision undo {args.id} --answer "<label>"')], indent=2)
            return 0, '[]'  # #530: taken under the mandate, nothing to ask.
        from wuwei.decision import config_keys  # #529: a config card records through config set
        record = CONFIG_RECORD if config_keys(fields) else RECORD
        card = record_widget(args.id, fields, record, level=level)
        novel = novelty.routed(state.read_state(root), args.id)
        if novel:
            card['question'] += f' First time for {", ".join(novel)}: your answer clears it.'
        return 0, json.dumps([card], indent=2)
    if level == 'full':
        return 0, text.rstrip()
    outcome = state.read_state(root).get('decision_outcomes', {}).get(args.id, {})
    if outcome.get('decided_by') == 'mandate' and outcome.get('cisr') == 'Routine':  # #567
        return 0, (f"{args.id} (Routine, mandate): {fields['Question']} Took {outcome.get('option')}. "
                   f'Full record: wuwei decision show {args.id} --full')
    return 0, present(args.id, fields, level) + f'\nFull record: wuwei decision show {args.id} --full'


def owner_outcome(args, note=None, *, root=None, where=None):
    """The one owner-outcome writer; where is given only by the DM listener for a two-way door."""
    root = workspace.find_workspace(root)
    path = today_path(args.id, root)
    if path.is_symlink() or path.parent.is_symlink():
        return 2, f'decision: record must be a regular file; {SYMLINK}'
    text = path.read_text(encoding='utf-8')
    try:
        fields, scores = evaluate(text)
    except ValueError as exc:
        return 1, str(exc)
    args.option = option_id(fields, args.option)
    if args.option not in {row[0] for row in options(fields)}:
        return 1, 'decision: option is not in the record; pick an option id from bin/wuwei decision show <id>'
    data = state.read_state(root)
    previous = data.get('decision_outcomes', {}).get(args.id)
    if previous and previous.get('decided_by') == 'owner':
        return 1, 'decision: already answered; read it with bin/wuwei decision show <id>; write a new decision record to change course'
    if previous is None and args.id not in data.get('decision_routes', {}):
        return 1, 'decision: route this pending owner decision first; route it with bin/wuwei decision route <id> first'
    if previous is not None and previous.get('decided_by') not in ('seat', 'mandate'):
        return 1, 'decision: invalid prior outcome; run bin/wuwei doctor, then bin/wuwei why <id>'
    digest = hashlib.sha256((args.id + '\n' + args.option + '\n' + text).encode()).hexdigest()
    if where and fields['Reversibility'] != 'two-way':
        return 1, (f'decision: only a two-way decision is decided from the DM; '
                   f'run bin/wuwei decide {args.id} {args.option} in a host terminal')
    card = getattr(args, 'card', None)
    where = where or owner_confirm(root, args.id, digest, f'{args.id}: {fields["Question"]}\nRecord {args.option}.',
                                   card, fields)
    if not where and card is not None:
        return 1, no_card(root, args.id, args.option)
    if not where:
        return 1, 'decision: owner confirmation declined; rerun bin/wuwei decide <id> <option> in a host terminal and answer y'
    if path.read_text(encoding='utf-8') != text:
        return 2, f'decision: record changed during confirmation; {RACE}'
    reversed_choice = previous is not None and previous['option'] != args.option
    learned = data.get('outbound_learn', {}).get(args.id)
    if learned is not None:  # #492: the answer writes the learned connector first.
        from wuwei.commands import outbound  # Off every other decision path.
        if outbound.apply(root, learned, args.option, args.id):
            return 1, 'decision: the learned connector was not written; run bin/wuwei config check, then answer again'
    grant = data.get('grants', {}).get(args.id)
    if grant is not None and args.option == 'always':  # #478: the standing grant line first.
        from wuwei import grants
        if grants.standing(root, grant, args.id):
            return 1, 'decision: the standing grant was not written; run bin/wuwei config check, then answer again'

    def update(current):
        if current.get('decision_outcomes', {}).get(args.id) != previous:
            raise ValueError(f'decision changed during confirmation; {RACE}')
        for key in ('outbound_learn', 'grants'):  # #492, #478: the answer is stored on its row
            if args.id in current.get(key, {}):
                current[key][args.id]['answered'] = args.option
        current.setdefault('decision_outcomes', {})[args.id] = {
            'option': args.option, 'outcome': args.option, 'decided_by': 'owner',
            'reversibility': fields['Reversibility'], 'cisr': cisr(fields, scores),
            'class': fields.get('Class'), 'recommendation': fields['Recommendation'],
            'at': workspace.now().isoformat()}
        for name, item in current['items'].items():
            linked = item.get('decision') == args.id
            if not linked and item['phase'] == 'parked':
                linked = current.get('builds', {}).get(name, {}).get('action', {}).get(
                    'decision', '').endswith('/' + args.id + '.md')
            if linked and item['status'] == 'blocked' and item['phase'] in ('parked', 'escalated'):
                item['phase'] = item['resume_phase']
                item['status'] = 'queued'

    state._write_state(update, root, reserved=False,
                       kind='decision.reversed' if reversed_choice else 'decision.decided',
                       payload={'id': args.id, 'option': args.option, 'decided_by': 'owner',
                                'reversibility': fields['Reversibility'], 'class': fields.get('Class')})
    workspace.atomic_write(path, owner_record(text, args.option, where, note))
    from wuwei import cruise
    cruise.answered(root, args.id, args.option)
    if not (grant is not None and args.option == 'keep'):  # #556: Keep owner-only leaves it novel
        try:
            for key in novelty.routed(data, args.id):
                novelty.clear(root, key, args.id)
        except (OSError, ValueError) as exc:
            return 2, f'decision: {args.id} recorded; the seen set was not updated ({exc}); run bin/wuwei doctor'
    return 0, args.option


def undo(args, *, root=None, where=None):
    """#283: revert a cruise answer inside its undo window, after the owner's Undo, and ask
    the owner; where is given only by the DM listener."""
    from wuwei import cruise, sessions
    root = workspace.find_workspace(root)
    path = today_path(args.id, root)
    if path.is_symlink() or path.parent.is_symlink():
        return 2, f'decision undo: record must be a regular file; {SYMLINK}'
    try:
        text = path.read_text(encoding='utf-8')
        fields, _ = evaluate(text)
    except (OSError, UnicodeError) as exc:
        return 2, f'decision undo: could not read {args.id}: {type(exc).__name__}; run bin/wuwei doctor'
    except ValueError as exc:
        return 1, f'decision undo: {exc}'
    row = state.read_state(root).get('decision_outcomes', {}).get(args.id)
    if not isinstance(row, dict) or row.get('decided_by') != 'mandate' or not row.get('undo_until'):
        return 1, f'{args.id} has no undo window; reverse it with wuwei decide {args.id} <option>'
    if not cruise.window(row):
        return 1, (f'undo window closed at {cruise.clock(row["undo_until"])}; '
                   f'reverse it with wuwei decide {args.id} <option>')
    answer = (args.answer or 'Undo').strip().removesuffix(' (Recommended)').strip().casefold()
    if answer == 'keep':
        return 0, 'kept'
    if answer != 'undo':
        return 1, f'decision undo: answer Keep or Undo; rerun wuwei decision undo {args.id} --answer Undo'
    digest = hashlib.sha256((args.id + '\nundo\n' + text).encode()).hexdigest()
    where = where or owner_confirm(root, sessions.card_topic(args.id, 'Undo'), digest,
                                   f'{args.id}: {fields["Question"]}\nUndo {row["rule"]}.')
    if not where:
        return 1, f'decision undo: owner confirmation declined; rerun wuwei decision undo {args.id} in a host terminal and answer y'
    if path.read_text(encoding='utf-8') != text:
        return 2, f'decision undo: record changed during confirmation; {RACE}'
    now = workspace.now().isoformat()

    def update(current):
        if current.get('decision_outcomes', {}).get(args.id) != row:
            raise ValueError(f'decision changed during confirmation; {RACE}')
        del current['decision_outcomes'][args.id]
        current.setdefault('decision_routes', {})[args.id] = {
            'reversibility': fields['Reversibility'], 'recommendation': fields['Recommendation'],
            'cisr': row['cisr'], 'class': row['class'], 'thin': False, 'at': now, 'undone': True}

    state._write_state(update, root, reserved=False, kind='decision.reversed',
                       payload={'id': args.id, 'option': row['option'], 'decided_by': 'owner', 'undo': True,
                                'rule': row['rule'], 'class': row['class'],
                                'reversibility': fields['Reversibility']})
    stamp = workspace.now().isoformat(timespec='seconds')
    workspace.atomic_write(path, decided_record(text, 'pending', 'owner').rstrip('\n')
                           + f'\nNotes: Undone at {stamp} {where}.\n')
    from wuwei import undo as undo_ledger
    undo_ledger.record(root, 'decision', 'undo')  # #557: a real undo exercises the decision kind
    return 0, f'owner: ask with wuwei decision show {args.id} --widget'


def template():
    """A valid design record with one Lenses row per effective lens and their questions."""
    try:
        lenses = lens_table(workspace.load_config(workspace.find_workspace()))
    except FileNotFoundError:
        lenses = LENSES
    rows = ''.join(f'| {name} | Replace with one line for A | Replace with one line for B |\n' for name in lenses)
    questions = ' '.join(f'{name}: {question}' for name, question in lenses.items())
    lens_block = (f'<!-- Lenses: one line per option for each. {questions} -->\n'
                  f'Lenses:\n| Lens | A | B |\n| --- | --- | --- |\n{rows}') if lenses else ''
    return f'''Question: Which option should we take?
Class: design
Role: builder
Context: Replace with the evidence file and reason for deciding; name a repository, channel, person, dependency, environment or workflow outside this item's repository as repo:<org>/<name>, channel:<id>, person:<ns>:<id>, dependency:<ecosystem>/<name>, env:<name> or workflow:<name>.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| A | Make the scoped change | Passes every must and scores 8 on Outcome. | Replace with what changes, what it costs and what it closes. |
| B | Defer | Passes every must but scores 2 on Outcome. | Nothing changes until more evidence exists. |
{lens_block}Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Outcome | 10 | 8 | 2 |
Recommendation: A
Reasoning: Outcome decided it; replace with what would flip it to B.
Confidence: medium
Reversibility: two-way
Blast radius: Own branch and PR.
Pre-mortem: The change misses an edge case.
Revisit: Reopen if tests fail.
Decided-by: seat
Outcome: pending'''


def run(args):
    if args.action == 'template':
        print(template())
        return 0
    code, message = (lint_file(args.file) if args.action == 'lint' else
                     owner_outcome(args) if args.action == 'outcome' else
                     show(args) if args.action == 'show' else
                     undo(args) if args.action == 'undo' else decide(args))
    print(message, file=sys.stderr if code else sys.stdout)
    return code
