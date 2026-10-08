"""#557: wuwei undo runs the registered undo of a decision or a merge event; wuwei undo
rehearse <kind> exercises an undo once on a scratch target."""

import sys

from wuwei import undo, workspace


def register(subparsers):
    parser = subparsers.add_parser('undo', help='Undo a decision or a merge event, or rehearse an undo')
    parser.add_argument('target', help='D-n, an event id YYYY-MM-DD:N, or rehearse')
    parser.add_argument('kind', nargs='?', default='', help='with rehearse: commit or decision')
    parser.add_argument('--answer', help='the owner answer on the undo card: Keep or Undo')
    parser.set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    code, message = (undo.rehearse(root, args.kind) if args.target == 'rehearse'
                     else undo.run(root, args.target, args.answer))
    print(message, file=sys.stderr if code else sys.stdout)
    return code
