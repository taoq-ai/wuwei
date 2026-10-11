"""Record an outward duty done (#844): the model writes the content, this records it."""

import sys

from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('duty', help='Record an outward duty wuwei next listed as done')
    parser.add_argument('item', help="The item, or day for the day's summary")
    parser.add_argument('duty', help='ping, shepherd, tracker or summary')
    parser.add_argument('--evidence', required=True, help='The link or line that shows it was done')
    parser.set_defaults(func=run)


def run(args):
    from wuwei import derive, state, workspace
    try:
        root = workspace.find_workspace()
        due = {(row['item'], row['duty']) for row in derive.duties(root, workspace.load_config(root))}
        if args.duty not in derive.DUTIES or (args.item, args.duty) not in due:
            print(f'wuwei duty: {args.item} {args.duty} is not a due duty; run wuwei next for the '
                  'duties it lists', file=sys.stderr)
            return FINDINGS
        if not args.evidence.strip():
            print('wuwei duty: pass --evidence with the link or line that shows it was done', file=sys.stderr)
            return FINDINGS
        state.append_event('duty.done', {'item': args.item, 'duty': args.duty,
                                         'evidence': args.evidence.strip()}, root)
        print(f'{args.item}: {args.duty} recorded')
        return CLEAN
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei duty: {exc}', file=sys.stderr)
        return UNRUN
