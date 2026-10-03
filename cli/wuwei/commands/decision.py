"""Lint, route and record outcomes through the shared evaluator and state writer."""

import hashlib
import json
import sys

from wuwei import state, workspace
from wuwei.decision import (evaluate, lint_file, owner_confirm, owner_record, present, record_rejection,
                            record_widget, route, route_owner, seat_outcome, table, today_path)
from wuwei.exits import RACE, SYMLINK


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
    outcome.set_defaults(func=run)
    show = commands.add_parser('show', help='Print a decision at the owner verbosity level')
    show.add_argument('id')
    form = show.add_mutually_exclusive_group()
    form.add_argument('--full', action='store_true', help='Print every field')
    form.add_argument('--widget', action='store_true',
                      help='Print the decision as an AskUserQuestion widget with its recording command')
    show.set_defaults(func=run)


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
    if args.external:
        from wuwei.brief import identifier
        try:
            route_owner(args.id, fields, root, item=identifier(args.external))
        except ValueError as exc:
            return 1, f'decision: {exc}'
        return 0, 'owner'
    target = route(fields)
    if target == 'owner':
        route_owner(args.id, fields, root)
        return 0, target
    try:
        record = seat_outcome(fields, scores)
    except ValueError as exc:
        return record_rejection(path, 1, str(exc), root=root)

    def update(data):
        data.setdefault('decision_outcomes', {})[args.id] = record

    state._write_state(update, root, reserved=False, kind='decision.decided',
                       payload={'id': args.id, **record})
    return 0, target


def show(args):
    root = workspace.find_workspace()
    path = today_path(args.id, root)  # A symlinked record raises: it must belong to today.
    try:
        text = path.read_text(encoding='utf-8')
        fields, _ = evaluate(text)
    except FileNotFoundError:  # #362: a state answer; --widget callers read JSON, so a finding there.
        return int(bool(args.widget)), f'No {args.id} today; bin/wuwei nudges lists open decisions.'
    except (OSError, UnicodeError) as exc:
        return 2, (f'decision show: could not read {path.relative_to(root)}: {type(exc).__name__}; '
                   'check the file is readable, then run bin/wuwei doctor')
    except ValueError as exc:
        return 1, f'decision show: {exc}'
    if args.widget:
        return 0, json.dumps([record_widget(args.id, fields)], indent=2)
    level = 'full' if args.full else workspace.verbosity(workspace.load_config(root), 'decisions')
    if level == 'full':
        return 0, text.rstrip()
    return 0, present(args.id, fields, level) + f'\nFull record: wuwei decision show {args.id} --full'


def owner_outcome(args, note=None, *, root=None, where=None):
    """The one owner-outcome writer; where is given only by the DM listener for a two-way door."""
    root = workspace.find_workspace(root)
    path = today_path(args.id, root)
    if path.is_symlink() or path.parent.is_symlink():
        return 2, f'decision: record must be a regular file; {SYMLINK}'
    text = path.read_text(encoding='utf-8')
    try:
        fields, _ = evaluate(text)
    except ValueError as exc:
        return 1, str(exc)
    options = {row[0] for row in table(
        fields['Options'], ['Option', 'Description'], 'Options')}
    if args.option not in options:
        return 1, 'decision: option is not in the record; pick an option id from bin/wuwei decision show <id>'
    data = state.read_state(root)
    previous = data.get('decision_outcomes', {}).get(args.id)
    if previous and previous.get('decided_by') == 'owner':
        return 1, 'decision: already answered; read it with bin/wuwei decision show <id>; write a new decision record to change course'
    if previous is None and args.id not in data.get('decision_routes', {}):
        return 1, 'decision: route this pending owner decision first; route it with bin/wuwei decision route <id> first'
    if previous is not None and previous.get('decided_by') != 'seat':
        return 1, 'decision: invalid prior outcome; run bin/wuwei doctor, then bin/wuwei why <id>'
    digest = hashlib.sha256((args.id + '\n' + args.option + '\n' + text).encode()).hexdigest()
    if where and fields['Reversibility'] != 'two-way':
        return 1, (f'decision: only a two-way decision is decided from the DM; '
                   f'run bin/wuwei decide {args.id} {args.option} in a host terminal')
    where = where or owner_confirm(root, args.id, digest, f'{args.id}: {fields["Question"]}\nRecord {args.option}.')
    if not where:
        return 1, 'decision: owner confirmation declined; rerun bin/wuwei decide <id> <option> in a host terminal and answer y'
    if path.read_text(encoding='utf-8') != text:
        return 2, f'decision: record changed during confirmation; {RACE}'
    reversed_choice = previous is not None and previous['option'] != args.option

    def update(current):
        if current.get('decision_outcomes', {}).get(args.id) != previous:
            raise ValueError(f'decision changed during confirmation; {RACE}')
        current.setdefault('decision_outcomes', {})[args.id] = {
            'option': args.option, 'outcome': args.option, 'decided_by': 'owner',
            'reversibility': fields['Reversibility']}
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
                                'reversibility': fields['Reversibility']})
    workspace.atomic_write(path, owner_record(text, args.option, where, note))
    return 0, args.option


def run(args):
    if args.action == 'template':
        print('''Question: Which option should we take?
Context: Replace with the evidence file and reason for deciding.
Options:
| Option | Description |
| --- | --- |
| A | Make the scoped change |
| B | Defer until more evidence exists |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Outcome | 10 | 8 | 2 |
Recommendation: A
Confidence: medium
Reversibility: two-way
Blast radius: Own branch and PR.
Pre-mortem: The change misses an edge case.
Revisit: Reopen if tests fail.
Decided-by: seat
Outcome: pending''')
        return 0
    code, message = (lint_file(args.file) if args.action == 'lint' else
                     owner_outcome(args) if args.action == 'outcome' else
                     show(args) if args.action == 'show' else decide(args))
    print(message, file=sys.stderr if code else sys.stdout)
    return code
