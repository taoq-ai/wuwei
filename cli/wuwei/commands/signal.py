"""Classify one event supplied as JSON on standard input."""

import json
import sys

from wuwei import state, workspace
from wuwei.exits import CLEAN
from wuwei.signal import classify


def register(subparsers):
    parser = subparsers.add_parser('signal', help='classify attention')
    parser.add_argument('action', choices=('classify',))
    parser.set_defaults(func=run)


def run(args):
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError, RecursionError):
        event = None
    tier, lane = classify(event, {**state.read_state(), 'now': workspace.now().isoformat()})
    print(json.dumps({'tier': tier, 'lane': lane}))
    return CLEAN
