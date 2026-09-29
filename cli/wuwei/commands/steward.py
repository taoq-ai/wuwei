"""Launch steward reviews and acknowledge their steering notes."""

import sys

from wuwei import state, steward


def register(subparsers):
    parser = subparsers.add_parser('steward', help='Run a steward review or acknowledge steering')
    actions = parser.add_subparsers(dest='action', required=True)
    run = actions.add_parser('run')
    run.add_argument('--trigger', choices=('sweep', 'close', 'tool-calls'), default='sweep')
    ack = actions.add_parser('ack')
    ack.add_argument('id')
    parser.set_defaults(func=command)


def command(args):
    try:
        if args.action == 'run':
            return steward.run(trigger=args.trigger)
        steward.acknowledge(args.id)
        return 0
    except state.StateError as exc:
        print(f'wuwei steward: {exc}', file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei steward: {exc}', file=sys.stderr)
        return 2
