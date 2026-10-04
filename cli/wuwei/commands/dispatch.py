"""Expose planner dispatch and receive decisions."""

import json
import sys

from wuwei import dispatch
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('dispatch', help='Decide planner gate and discovery work')
    actions = parser.add_subparsers(dest='action', required=True)
    step = actions.add_parser('next')
    step.add_argument('item', nargs='?')
    step.add_argument('--all', action='store_true', help='print the launch set for every open item')
    receive = actions.add_parser('receive')
    receive.add_argument('item')
    receive.add_argument('role')
    receive.add_argument('name')
    receive.add_argument('--round', choices=('initial', 'delta'), default='initial')
    actions.add_parser('opinion').add_argument('item')
    discovery = actions.add_parser('discovery')
    discovery.add_argument('trigger', choices=('sweep', 'seat-free'))
    parser.set_defaults(func=run)


def run(args):
    from wuwei.commands.build import PortExit
    try:
        if args.action == 'next' and args.all == bool(args.item):
            raise ValueError('pass one item or --all: bin/wuwei dispatch next <item> or '
                             'bin/wuwei dispatch next --all')
        if args.action == 'next' and args.all:
            value = dispatch.launch_set()
            print(json.dumps(value))
            return FINDINGS if any(row['action'] in ('refused', 'escalate')
                                   for row in value['entries']) else CLEAN
        if args.action == 'next':
            value = dispatch.next_step(args.item)
        elif args.action == 'opinion':
            value = dispatch.opinion(args.item)
        elif args.action == 'receive':
            value = dispatch.receive(args.item, args.role, args.name, args.round)
        else:
            value = dispatch.discovery(args.trigger)
        print(json.dumps(value))
        return FINDINGS if value.get('action') == 'escalate' else CLEAN
    except dispatch.Refused as exc:
        print(f'wuwei dispatch: {exc}', file=sys.stderr)
        return FINDINGS
    except PortExit as exc:
        print(f'wuwei dispatch: {exc}', file=sys.stderr)
        return exc.code
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f'wuwei dispatch: {exc}', file=sys.stderr)
        return UNRUN
