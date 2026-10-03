"""Run the registry check or record the owner's host decision."""

import json
from pathlib import Path
import re
import sys

from wuwei import decision, mcp, workspace


def register(subparsers):
    parser = subparsers.add_parser('mcp', help='Check attached MCP servers')
    parser.add_argument('action', choices=('check', 'decide'))
    parser.add_argument('words', nargs='*', help='decide only: D-<n> <option>, or proceed-unmeasured <server>...')
    parser.add_argument('--widget', action='store_true',
                        help='check only: also print the pending decision as an AskUserQuestion widget')
    parser.set_defaults(func=run)


def run(args):
    words = args.words
    unmeasured = words[:1] == ['proceed-unmeasured'] and len(words) > 1
    answer = len(words) == 2 and re.fullmatch(decision.DECISION_ID, words[0])
    if ((args.action == 'check') == bool(words) or args.action == 'decide' and not (unmeasured or answer)
            or args.widget and args.action == 'decide'):
        print('usage: wuwei mcp check [--widget] | wuwei mcp decide D-<n> <option> | '
              'wuwei mcp decide proceed-unmeasured <server>...', file=sys.stderr)
        return 2
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    result = (mcp.check(root) if args.action == 'check' else mcp.decide(root, servers=words[1:]) if unmeasured
              else mcp.decide(root, *words))
    if result.reason:
        print(result.reason, file=sys.stderr)
    if args.widget:
        try:
            print(json.dumps(mcp.widget(root), indent=2))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'wuwei mcp check --widget: {exc}', file=sys.stderr)
            return 2
    return result.exit
