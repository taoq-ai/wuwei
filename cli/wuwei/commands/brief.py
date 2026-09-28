"""Write a stamped brief from stdin."""

import sys

from wuwei import brief


def register(subparsers):
    parser = subparsers.add_parser('brief', help='Write and log a seat brief')
    for name in ('role', 'item', 'name'):
        parser.add_argument(name)
    parser.add_argument('--worktree')
    parser.add_argument('--pr')
    parser.add_argument('--gate', action='store_true')
    parser.add_argument('--track')
    parser.set_defaults(func=run)


def run(args):
    try:
        path = brief.write(args.role, args.item, args.name, sys.stdin.read(),
                           worktree=args.worktree, pr=args.pr, gate=args.gate, track=args.track)
    except brief.Refused as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        return 1
    print(path)
    return 0
