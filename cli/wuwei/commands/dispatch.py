"""Expose planner dispatch and receive decisions."""

import json
import sys

from wuwei import dispatch
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('dispatch', help='Decide planner gate and discovery work')
    actions = parser.add_subparsers(dest='action', required=True)
    step = actions.add_parser('next')
    step.add_argument('item')
    receive = actions.add_parser('receive')
    receive.add_argument('item')
    receive.add_argument('role')
    receive.add_argument('name')
    receive.add_argument('--round', choices=('initial', 'delta'), default='initial')
    discovery = actions.add_parser('discovery')
    discovery.add_argument('trigger', choices=('sweep', 'seat-free'))
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.action == 'next':
            value = dispatch.next_step(args.item)
        elif args.action == 'receive':
            value = dispatch.receive(args.item, args.role, args.name, args.round)
        else:
            value = dispatch.discovery(args.trigger)
        print(json.dumps(value))
        return FINDINGS if value.get('action') == 'escalate' else CLEAN
    except dispatch.Refused as exc:
        print(f'wuwei dispatch: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei dispatch: {exc}', file=sys.stderr)
        return UNRUN
