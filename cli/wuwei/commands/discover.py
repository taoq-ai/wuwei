"""Report intraday discovery measurements and candidates."""

import json
import sys

from wuwei import discovery
from wuwei.exits import CLEAN, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('discover', help='Discover candidate work')
    parser.set_defaults(func=run)


def run(args):
    try:
        result = discovery.discover()
        print(json.dumps(result, sort_keys=True))
        return UNRUN if any(value == 'unmeasured' for value in result['sources'].values()) else CLEAN
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei discover: {exc}', file=sys.stderr)
        return UNRUN
