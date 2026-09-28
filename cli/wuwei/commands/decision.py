"""Lint, route and record outcomes through the shared evaluator and state writer."""

import sys

from wuwei import state, workspace
from wuwei.decision import evaluate, lint_file, record_rejection, route, today_path


def register(subparsers):
    parser = subparsers.add_parser('decision', help='Check and route decision records')
    commands = parser.add_subparsers(dest='action', required=True)
    lint = commands.add_parser('lint', help='Lint a saved decision file')
    lint.add_argument('file')
    lint.set_defaults(func=run)
    command = commands.add_parser('route', help='Route a decision today')
    command.add_argument('id')
    command.set_defaults(func=run)


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
        return 0, target
    record = {'option': fields['Recommendation'], 'score': scores[fields['Recommendation']],
              'decided_by': 'seat', 'outcome': fields['Recommendation'],
              'reversibility': fields['Reversibility'], 'blast_radius': fields['Blast radius']}

    def update(data):
        data.setdefault('decision_outcomes', {})[args.id] = record

    state._write_state(update, root, reserved=False, kind='decision.decided',
                       payload={'id': args.id, **record})
    return 0, target


def run(args):
    code, message = lint_file(args.file) if args.action == 'lint' else decide(args)
    print(message, file=sys.stderr if code else sys.stdout)
    return code
