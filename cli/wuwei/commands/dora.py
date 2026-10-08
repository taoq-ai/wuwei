"""#586: print the DORA four keys, each with its source or why it is unmeasured."""

from datetime import timedelta
import sys

from wuwei import metrics, report, workspace


def register(subparsers):
    parser = subparsers.add_parser('dora', help='Show the DORA four keys with their sources')
    parser.add_argument('--window', type=int, default=metrics.DORA_WINDOW, help='days to read (default 28)')
    parser.set_defaults(func=run)


def run(args):
    if args.window < 1:
        print('wuwei dora: --window must be a positive number of days; pass --window 28', file=sys.stderr)
        return 2
    try:
        root = workspace.find_workspace()
        until = workspace.now()
        since = until - timedelta(days=args.window)
        rows = metrics.dora(root, workspace.load_config(root), since, until)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei dora: {exc}', file=sys.stderr)
        return 2
    print(f'DORA, last {args.window} days ({since.date()} to {until.date()})')
    print('\n'.join(report.dora_lines(rows)))
    failed = dict.fromkeys(row['reason'] for row in rows.values() if row.get('failed'))
    for reason in failed:
        print(f'wuwei dora: {reason}', file=sys.stderr)
    return 2 if failed else 0
