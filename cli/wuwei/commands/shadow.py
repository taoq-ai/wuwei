"""Show what the guards would have refused in shadow mode."""

from wuwei import report, watch, workspace


def register(subparsers):
    parser = subparsers.add_parser('shadow', help='Show what shadow mode would have refused')
    parser.add_argument('action', choices=('report',))
    parser.set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    since = workspace.load_config(root)['guards']['shadow_since']
    days = [day for day in reversed(watch.days(root)) if day.name >= since]
    print('\n'.join(['# WUWEI shadow report', '', *(report.shadow_lines(days) or ['none'])]))
    return 0
