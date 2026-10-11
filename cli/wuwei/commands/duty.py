"""Record an outward duty done (#844): the model writes the content, this records it."""

import sys

from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('duty', help='Record an outward duty wuwei next listed as done')
    parser.add_argument('item', help="The item, or day for the day's summary")
    parser.add_argument('duty', help='ping, shepherd, tracker or summary')
    how = parser.add_mutually_exclusive_group(required=True)
    how.add_argument('--evidence', help='The link or line that shows it was done')
    how.add_argument('--skipped', help='Why it cannot be done; the day report lists it (G6)')
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
        text = (args.evidence if args.skipped is None else args.skipped).strip()
        if not text:
            print('wuwei duty: pass --evidence with the link that shows it was done, or --skipped with why '
                  'it cannot be done', file=sys.stderr)
            return FINDINGS
        if args.skipped is None:
            state.append_event('duty.done', {'item': args.item, 'duty': args.duty, 'evidence': text}, root)
        else:  # listed under Skipped duties in the report, never dropped silently
            duty = {'item': args.item, 'duty': args.duty}
            state.append_event('duty.due', {**duty, 'command': f'wuwei duty {args.item} {args.duty} --evidence <link>'}, root)
            state.append_event('duty.skipped', {**duty, 'error': text}, root)
        print(f"{args.item}: {args.duty} {'recorded' if args.skipped is None else 'skipped'}")
        return CLEAN
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei duty: {exc}', file=sys.stderr)
        return UNRUN
