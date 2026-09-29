"""Print recorded process measurements."""

import json
import sys

from wuwei import metrics


def register(subparsers):
    parser = subparsers.add_parser('metrics', help='Show recorded process metrics')
    parser.set_defaults(func=run)


def run(args):
    try:
        print(json.dumps(metrics.collect(), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei metrics: {exc}', file=sys.stderr)
        return 2
