"""Write a stamped brief from stdin."""

import sys

from wuwei import brief, brief_pack


def register(subparsers):
    parser = subparsers.add_parser('brief', help='Write and log a seat brief')
    for name in ('role', 'item', 'name'):
        parser.add_argument(name, nargs='?')
    parser.add_argument('--meeting', action='store_true')
    parser.add_argument('--worktree')
    parser.add_argument('--pr')
    parser.add_argument('--gate', action='store_true')
    parser.add_argument('--track')
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.role == 'pack' and args.item is None and args.name is None:
            print(brief_pack.pack(meeting=args.meeting))
            return 0
        if args.role == 'answer' and args.item and args.name:
            print(brief_pack.answer(int(args.item), args.name, meeting=args.meeting))
            return 0
        if not all((args.role, args.item, args.name)):
            raise ValueError('expected pack, answer NUMBER TEXT, or ROLE ITEM NAME')
        path = brief.write(args.role, args.item, args.name, sys.stdin.read(),
                           worktree=args.worktree, pr=args.pr, gate=args.gate, track=args.track)
    except brief.Refused as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei brief: {exc}', file=sys.stderr)
        return 2
    print(path)
    return 0
