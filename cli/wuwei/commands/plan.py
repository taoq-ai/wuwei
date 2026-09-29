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
    propose = actions.add_parser('propose')
    propose.add_argument('input', type=Path, help='Lead discovery JSON')
    approve = actions.add_parser('approve')
    approve.add_argument('--items', nargs='*', required=True)
    approve.add_argument('--goals-confirmed', action='store_true')
    approve.add_argument('--import-yesterday', action='store_true')
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.action == 'template':
            root = workspace.find_workspace()
            identifiers = list(goals.parse((root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')))
            if not identifiers:
                raise ValueError('memory/goals.md needs at least one G-n goal for plan template')
            from wuwei.commands.rank import candidate_template
            framework = workspace.load_config(root)['prioritisation']['framework']
            print(json.dumps({'goals': [identifiers[0]], 'cap': 1,
                'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
                'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 6},
                'sweep': {'manual': 'unmeasured: replace with discovery evidence'},
                'candidates': [candidate_template(identifiers[0], framework)]}, indent=2))
        elif args.action == 'session':
            plan.session(args.session_id)
        elif args.action == 'propose':
            source = sys.stdin.read() if str(args.input) == '-' else args.input.read_text(encoding='utf-8')
            print(plan.propose(json.loads(source)))
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
