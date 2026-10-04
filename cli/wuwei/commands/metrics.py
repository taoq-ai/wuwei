"""Print recorded process measurements."""

import json
import sys

from wuwei import metrics


def register(subparsers):
    parser = subparsers.add_parser('metrics', help='Show recorded process metrics')
    parser.add_argument('--week', nargs='?', const='', default=None,
                        help="a week's telemetry aggregate (YYYY-Www, the current week by default)")
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.week is not None:
            from wuwei import telemetry, workspace
            root = workspace.find_workspace()
            week = args.week or telemetry.current_week(root)
            found = telemetry.load_week(root, week) or telemetry.week_file(root, workspace.load_config(root), week)
            print(json.dumps(found, sort_keys=True))
            return 0
        print(json.dumps(metrics.collect(), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei metrics: {exc}', file=sys.stderr)
        return 2
