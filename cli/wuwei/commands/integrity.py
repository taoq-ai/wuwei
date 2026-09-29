"""Inspect plugin integrity or explicitly confirm content on the host."""

from wuwei import integrity, workspace


def register(subparsers):
    parser = subparsers.add_parser('integrity', help='Check signed plugin integrity')
    parser.add_argument('action', choices=('check', 'reconfirm'))
    parser.set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    result = (integrity.check(root) if args.action == 'check' else integrity.reconfirm(root))
    print(result.reason or 'plugin integrity: clean')
    return result.exit
