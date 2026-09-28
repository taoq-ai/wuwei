"""Read and mutate day state through the single writer."""

import json
import sys

from wuwei import state
from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    parser = subparsers.add_parser('state', help='Read or update day state')
    actions = parser.add_subparsers(dest='action', required=True)
    get = actions.add_parser('get')
    get.add_argument('path', nargs='?')
    set_parser = actions.add_parser('set')
    set_parser.add_argument('path')
    set_parser.add_argument('value')
    transition = actions.add_parser('transition')
    transition.add_argument('item')
    transition.add_argument('phase')
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.action == 'get':
            print(json.dumps(state.get_state(args.path), allow_nan=False))
        elif args.action == 'set':
            state.set_state(args.path, json.loads(args.value))
        else:
            state.transition(args.item, args.phase)
        return CLEAN
    except state.StateError as exc:
        print(f'wuwei state: {exc}', file=sys.stderr)
        return FINDINGS
