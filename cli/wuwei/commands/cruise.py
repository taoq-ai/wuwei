"""#558: wuwei cruise budget prints the error budget of each decision class; #559: wuwei cruise
calibration prints the Brier score of each class and role (design 5.8.1)."""

import sys

from wuwei import workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('cruise', help='cruise mode: budget prints the error budget per decision class, '
                                   'calibration the confidence calibration per class and role')
    parser.add_argument('action', choices=('budget', 'calibration'))
    parser.set_defaults(func=run)


def run(args):
    from wuwei import budget_classes, calibration_scores
    try:
        root = workspace.find_workspace()
        reader = budget_classes if args.action == 'budget' else calibration_scores
        rows = reader.table(root, workspace.load_config(root))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei cruise {args.action}: {exc}', file=sys.stderr)
        return UNRUN
    if args.action == 'calibration':
        form = '{:<6} {:<16} {:>6} {:>5} {}'
        print(form.format('kind', 'name', 'scored', 'brier', 'state'))
        for row in rows:
            print(form.format(row['kind'], row['name'], row['scored'],
                              '-' if row['brier'] is None else f'{row["brier"]:.2f}', row['state']))
        return FINDINGS if any(row['state'] == 'uncalibrated' for row in rows) else CLEAN
    form = '{:<16} {:>5} {:>8} {:>5} {:>9} {:>5} {}'
    print(form.format('class', 'level', 'answered', 'spent', 'allowance', 'burn', 'state'))
    for row in rows:
        print(form.format(row['class'], f'L{row["level"]}', row['answered'], row['spent'],
                          f'{row["allowance"]:g}', f'{row["burn"]:.1f}', row['state']))
    return FINDINGS if any(row['state'] != 'ok' for row in rows) else CLEAN
