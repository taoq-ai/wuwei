"""Launch steward reviews."""

import sys

from wuwei import state, steward


def register(subparsers):
    parser = subparsers.add_parser('steward', help='Run a steward review')
    actions = parser.add_subparsers(dest='action', required=True)
    run = actions.add_parser('run')
    run.add_argument('--trigger', choices=('sweep', 'close'), default='sweep')
    parser.set_defaults(func=command)


def command(args):
    try:
        return steward.run(trigger=args.trigger)
    except state.StateError as exc:
        print(f'wuwei steward: {exc}', file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei steward: {exc}', file=sys.stderr)
        return 2
