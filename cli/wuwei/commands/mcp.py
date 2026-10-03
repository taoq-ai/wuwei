"""Run the registry check or record the owner's host decision."""

import json
from pathlib import Path
import sys

from wuwei import mcp, workspace


def register(subparsers):
    parser = subparsers.add_parser('mcp', help='Check attached MCP servers')
    parser.add_argument('action', choices=('check', 'decide'))
    parser.add_argument('words', nargs='*', help='decide only: proceed-unmeasured <server>...')
    parser.add_argument('--widget', action='store_true',
                        help='check only: also print the pending decision as an AskUserQuestion widget')
    parser.set_defaults(func=run)


def run(args):
    if (args.words and (args.action == 'check' or args.words[0] != 'proceed-unmeasured' or len(args.words) < 2)
            or args.widget and args.action == 'decide'):
        print('usage: wuwei mcp check [--widget] | wuwei mcp decide [proceed-unmeasured <server>...]',
              file=sys.stderr)
        return 2
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    result = mcp.check(root) if args.action == 'check' else mcp.decide(root, servers=args.words[1:] or None)
    if result.reason:
        print(result.reason, file=sys.stderr)
    if args.widget:
        try:
            print(json.dumps(mcp.widget(root), indent=2))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'wuwei mcp check --widget: {exc}', file=sys.stderr)
            return 2
    return result.exit
