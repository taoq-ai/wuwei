"""Print the plugin reference the session reads at start (#476)."""

from wuwei.exits import CLEAN


def register(subparsers):
    subparsers.add_parser('guide', help='Print the plugin reference the session reads at start').set_defaults(func=run)


def run(args):
    from wuwei import guide
    print(guide.text(), end='')
    return CLEAN
