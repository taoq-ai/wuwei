"""Run the registry check or record the owner's host decision."""

from pathlib import Path
import sys

from wuwei import mcp, workspace


def register(subparsers):
    parser = subparsers.add_parser('mcp', help='Check attached MCP servers')
    parser.add_argument('action', choices=('check', 'decide'))
    parser.set_defaults(func=run)


def run(args):
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    result = mcp.check(root) if args.action == 'check' else mcp.decide(root)
    if result.reason:
        print(result.reason, file=sys.stderr)
    return result.exit
