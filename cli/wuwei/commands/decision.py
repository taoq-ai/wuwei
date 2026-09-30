"""Lint, route and record outcomes through the shared evaluator and state writer."""

import hashlib
import re
import sys

from wuwei import state, workspace
from wuwei.decision import evaluate, lint_file, record_rejection, route, seat_outcome, table, today_path


def register(subparsers):
    parser = subparsers.add_parser('decision', help='Check and route decision records')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('template', help='Print a valid decision record').set_defaults(func=run)
    lint = commands.add_parser('lint', help='Lint a saved decision file')
    lint.add_argument('file')
    lint.set_defaults(func=run)
    command = commands.add_parser('route', help='Route a decision today')
    command.add_argument('id')
    command.set_defaults(func=run)
    outcome = commands.add_parser('outcome', help='Record an owner choice from the host terminal')
    outcome.add_argument('id')
    outcome.add_argument('option')
    outcome.set_defaults(func=run)


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
    target = route(fields)
    if target == 'owner':
        def mark(data):
            routed = data.setdefault('decision_routes', {})
            if args.id not in routed:
                routed[args.id] = {'reversibility': fields['Reversibility'],
                                   'recommendation': fields['Recommendation']}

        if args.id not in state.read_state(root).get('decision_routes', {}):
            state._write_state(mark, root, reserved=False, kind='decision.routed',
                               payload={'id': args.id, 'reversibility': fields['Reversibility']})
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


def owner_outcome(args):
    from wuwei.integrity import _host_confirm
    root = workspace.find_workspace()
    path = today_path(args.id, root)
    if path.is_symlink() or path.parent.is_symlink():
        return 2, 'decision: record must be a regular file'
    text = path.read_text(encoding='utf-8')
    try:
        fields, _ = evaluate(text)
    except ValueError as exc:
        return 1, str(exc)
    options = {row[0] for row in table(
        fields['Options'], ['Option', 'Description'], 'Options')}
    if args.option not in options:
        return 1, 'decision: option is not in the record'
    data = state.read_state(root)
    previous = data.get('decision_outcomes', {}).get(args.id)
    if previous and previous.get('decided_by') == 'owner':
        return 1, 'decision: already answered'
    if previous is None and args.id not in data.get('decision_routes', {}):
        return 1, 'decision: route this pending owner decision first'
    if previous is not None and previous.get('decided_by') != 'seat':
        return 1, 'decision: invalid prior outcome'
    digest = hashlib.sha256((args.id + '\n' + args.option + '\n' + text).encode()).hexdigest()
    if not _host_confirm(digest, prompt='Review the decision and chosen option on this host. To confirm, type:'):
        return 1, 'decision: owner confirmation declined'
    if path.read_text(encoding='utf-8') != text:
        return 2, 'decision: record changed during confirmation'
    reversed_choice = previous is not None and previous['option'] != args.option

    def update(current):
        if current.get('decision_outcomes', {}).get(args.id) != previous:
            raise ValueError('decision changed during confirmation')
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
                       payload={'id': args.id, 'option': args.option,
                                'reversibility': fields['Reversibility']})
    # ponytail: rewrites the first Outcome: line; a record with an inactive example
    # Outcome: above the real field needs the active line from verdict.active_text.
    workspace.atomic_write(path, re.sub(r'^((?:#{1,6} )?Outcome:).*$', lambda m: f'{m[1]} {args.option}',
                                        text, count=1, flags=re.M))
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
                     owner_outcome(args) if args.action == 'outcome' else decide(args))
    print(message, file=sys.stderr if code else sys.stdout)
    return code
