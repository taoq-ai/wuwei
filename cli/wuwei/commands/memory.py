"""The harness export of the charter rules."""

import sys

from wuwei import memory
from wuwei.exits import CLEAN, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('memory', help='export the charter rules')
    actions = parser.add_subparsers(dest='memory_action', required=True)
    export = actions.add_parser('export', help='write the rules block into the harness memory file')
    export.add_argument('--claude', action='store_true', required=True)
    export.set_defaults(func=run_export)


def run_export(args):
    try:
        path, changed = memory.export()
    except (OSError, ValueError) as exc:
        print(f'wuwei memory export: {exc}', file=sys.stderr)
        return UNRUN
    print(f'export: {path} {"written" if changed else "unchanged"}')
    return CLEAN
