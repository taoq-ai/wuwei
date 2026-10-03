"""Run the registry check or record the owner's host decision."""

from pathlib import Path
import sys

from wuwei import mcp, workspace


def register(subparsers):
    parser = subparsers.add_parser('mcp', help='Check attached MCP servers')
    parser.add_argument('action', choices=('check', 'decide'))
    parser.add_argument('words', nargs='*', help='decide only: proceed-unmeasured <server>...')
    parser.set_defaults(func=run)


def run(args):
    if args.words and (args.action == 'check' or args.words[0] != 'proceed-unmeasured' or len(args.words) < 2):
        print('usage: wuwei mcp check | wuwei mcp decide [proceed-unmeasured <server>...]', file=sys.stderr)
        return 2
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    result = mcp.check(root) if args.action == 'check' else mcp.decide(root, servers=args.words[1:] or None)
    if result.reason:
        print(result.reason, file=sys.stderr)
    return result.exit
