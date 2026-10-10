"""Record the owner's answer to today's decision D-n (#354): one command for every decision."""

from pathlib import Path
import sys

from wuwei import mcp, workspace
from wuwei.commands import decision as decision_command


def register(subparsers):
    parser = subparsers.add_parser('decide', help="Record the owner's answer to a decision")
    parser.add_argument('id')
    parser.add_argument('option')
    parser.add_argument('--note', help='one line appended to the record Notes')
    parser.add_argument('--card', metavar='HASH',
                        help='the card hash from the widget record command; the owner answered it in the planner session, so it never prompts')
    parser.set_defaults(func=run)


def run(args):
    if args.note is not None and ('\n' in args.note or '\r' in args.note):
        print('wuwei decide: --note must be one line; pass a single-line note', file=sys.stderr)
        return 2
    root = workspace.find_workspace()
    waiting = mcp.pending(root)
    if waiting and Path(waiting).stem == args.id:
        result = mcp.decide(root, args.id, args.option, note=args.note, card=args.card)
        if result.reason:
            print(result.reason, file=sys.stderr)
        return result.exit
    code, message = decision_command.owner_outcome(args, args.note)
    print(message, file=sys.stderr if code else sys.stdout)
    return code
