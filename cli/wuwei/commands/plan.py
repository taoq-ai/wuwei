"""CLI for morning proposal and approval."""

import json
from pathlib import Path
import sys

from wuwei import plan, state
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('plan', help='Propose or approve the morning plan')
    actions = parser.add_subparsers(dest='action', required=True)
    session = actions.add_parser('session', help='Register the planner session for wake delivery')
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
        if args.action == 'session':
            plan.session(args.session_id)
        elif args.action == 'propose':
            print(plan.propose(json.loads(args.input.read_text(encoding='utf-8'))))
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
