"""List open owner attention with its source."""

import json
import sys

from wuwei import workspace
from wuwei.commands.status import attention


def register(subparsers):
    parser = subparsers.add_parser('nudges', help='List open nudges and pages')
    parser.set_defaults(func=run)


def run(args):
    try:
        print(json.dumps(attention(workspace.day_dir()), allow_nan=False))
        return 0
    except FileNotFoundError:
        print('[]')  # No day state yet means nothing is owed.
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei nudges: {exc}', file=sys.stderr)
        return 2
