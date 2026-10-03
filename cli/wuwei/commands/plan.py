"""CLI for morning proposal and approval."""

import json
from pathlib import Path
import sys

from wuwei import goals, plan, state, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('plan', help='Propose or approve the morning plan')
    actions = parser.add_subparsers(dest='action', required=True)
    session = actions.add_parser('session', help='Register the planner session for wake delivery')
    actions.add_parser('template', help='Print valid lead JSON for this workspace')
    session.add_argument('session_id')
    session.add_argument('--take-over', action='store_true',
                         help='Hand the planner role over from the registered session')
    propose = actions.add_parser('propose')
    propose.add_argument('input', type=Path, help='Lead discovery JSON')
    approve = actions.add_parser('approve')
    approve.add_argument('--items', nargs='*', required=True)
    approve.add_argument('--goals-confirmed', action='store_true')
    approve.add_argument('--import-yesterday', action='store_true')
    add = actions.add_parser('add', help='Admit a discovered item after the morning gate')
    add.add_argument('item')
    for verb, text in (('carry', 'Carry an open item to tomorrow and record the decision'),
                       ('park', 'Park an open item and record the decision')):
        command = actions.add_parser(verb, help=text)
        command.add_argument('item')
        command.add_argument('--reason', help='Why; written into the record on one line')
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.action == 'template':
            root = workspace.find_workspace()
            text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
            goal = (next(iter(goals.parse(text))) if goals.defined(text) else
                    {'id': 'G-1', 'outcome': 'Replace with the outcome',
                     'measure': 'Replace with the measure', 'target': 'Replace with the target',
                     'date': workspace.now().date().isoformat(), 'priority': 1})
            from wuwei.commands.rank import candidate_template
            framework = workspace.load_config(root)['prioritisation']['framework']
            print(json.dumps({'goals': [goal], 'cap': 1,
                'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
                'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 6},
                'sweep': {'manual': 'unmeasured: replace with discovery evidence'},
                'candidates': [candidate_template(goal if isinstance(goal, str) else goal['id'],
                                                  framework)]}, indent=2))
        elif args.action == 'session':
            plan.session(args.session_id, take_over=args.take_over)
        elif args.action == 'propose':
            source = sys.stdin.read() if str(args.input) == '-' else args.input.read_text(encoding='utf-8')
            print(plan.propose(json.loads(source)))
        elif args.action == 'add':
            print(json.dumps(plan.add(args.item)))
        elif args.action in ('carry', 'park'):
            outcome = {'carry': 'carried', 'park': 'parked'}[args.action]
            print(f'{plan.dispose(args.item, outcome, args.reason)}: {outcome} {args.item}')
        else:
            plan.approve(args.items, goals_confirmed=args.goals_confirmed,
                         import_yesterday=args.import_yesterday)
        return CLEAN
    except state.StateError as exc:
        print(f'wuwei plan: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei plan: {exc}', file=sys.stderr)
        return UNRUN
