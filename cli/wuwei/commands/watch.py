"""Run workspace supervision continuously or for one due cycle."""

from wuwei import watch


def register(subparsers):
    parser = subparsers.add_parser('watch', help='Supervise workspace activity and owned PRs')
    parser.add_argument('--once', action='store_true', help='Run due work once and return 0/1/2')
    parser.set_defaults(func=lambda args: watch.run(once=args.once))
