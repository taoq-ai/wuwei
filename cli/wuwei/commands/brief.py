"""Write a stamped brief from --body or --file."""

from pathlib import Path
import sys

from wuwei import brief, brief_pack, dispatch


def register(subparsers):
    parser = subparsers.add_parser('brief', help='Write and log a seat brief')
    for name in ('role', 'item', 'name'):
        parser.add_argument(name, nargs='?')
    parser.add_argument('--meeting', action='store_true')
    parser.add_argument('--worktree')
    parser.add_argument('--pr')
    parser.add_argument('--gate', action='store_true')
    parser.add_argument('--track')
    body = parser.add_mutually_exclusive_group()
    body.add_argument('--body', help='brief body text')
    body.add_argument('--file', help='read the brief body from PATH (- reads stdin)')
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
        if args.body is not None:
            body = args.body
        elif args.file == '-':
            body = sys.stdin.read()
        elif args.file is not None:
            body = Path(args.file).read_text(encoding='utf-8')
        else:
            raise ValueError('brief body required: pass --body TEXT or --file PATH (--file - reads stdin)')
        role = 'sentinel-' + args.role if args.role in dispatch.GATE_ROLES else args.role
        path = brief.write(role, args.item, args.name, body,
                           worktree=args.worktree, pr=args.pr, gate=args.gate, track=args.track)
    except brief.Refused as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei brief: {exc}', file=sys.stderr)
        return 2
    print(path)
    return 0
