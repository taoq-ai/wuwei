"""Append an event through the shared writer."""

import json
import sys

from wuwei.exits import CLEAN, FINDINGS
from wuwei.state import append_event


def register(subparsers):
    parser = subparsers.add_parser('event', help='Append a timestamped day event')
    parser.add_argument('kind')
    parser.add_argument('payload', nargs='?', default='{}')
    parser.set_defaults(func=run)


def run(args):
    if args.kind.startswith('state.'):
        print('wuwei event: state.* kinds are reserved for the state writer', file=sys.stderr)
        return FINDINGS
    append_event(args.kind, json.loads(args.payload))
    return CLEAN
