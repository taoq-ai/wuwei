"""Print and save the local owner report; then supervise merges and step the telemetry week."""

from contextlib import redirect_stdout
from pathlib import Path
import sys

from wuwei import report, state, workspace


def register(subparsers):
    parser = subparsers.add_parser('report', help='Show the owner report')
    parser.add_argument('--week', nargs='?', const='', default=None,
                        help="a week's telemetry aggregate (YYYY-Www, the current week by default)")
    parser.set_defaults(func=run)


def week(value):
    import json
    from wuwei import telemetry
    try:
        root = workspace.find_workspace()
        value = value or telemetry.current_week(root)
        found = telemetry.load_week(root, value) or telemetry.week_file(root, workspace.load_config(root), value)
        print(json.dumps(found, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei report --week: {exc}', file=sys.stderr)
        return 2


def run(args):
    if args.week is not None:
        return week(args.week)
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    if not state.day_started(workspace.day_dir(root)):
        print('No report today: no day has started. Start one with /wuwei:wuwei-plan.')
        return 0
    print(report.write().read_text(encoding='utf-8'), end='')
    # #847: the jobs the watch ran once a day; each failure is one stderr line, never the exit.
    from wuwei import merge, telemetry
    from wuwei.watch import ERRORS
    with redirect_stdout(sys.stderr):
        merge.poll(root)
    try:
        telemetry.step(root, workspace.load_config(root))
    except ERRORS as exc:
        print(f'wuwei report: telemetry unmeasured: {exc}; run bin/wuwei doctor', file=sys.stderr)
    return 0
