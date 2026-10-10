"""Tracker hygiene (5.11): open tickets, write the day's comments, move a ticket to done."""

import sys

from wuwei import tracker, workspace
from wuwei.exits import UNRUN


def register(subparsers):
    parser = subparsers.add_parser('tracker', help='Open tickets, log comments, mark done')
    actions = parser.add_subparsers(dest='action', required=True)
    create = actions.add_parser('create', help="Open the item's ticket, or a linked bug, "
                                               'triage or follow-up ticket')
    kind = create.add_mutually_exclusive_group()
    for flag, category in (('--bug', 'bugs'), ('--triage', 'triage'),
                           ('--follow-up', 'follow-ups')):
        kind.add_argument(flag, dest='category', action='store_const', const=category)
    create.add_argument('subject', help='The day item (or the subject of a triage)')
    create.add_argument('title', nargs='?', help='Ticket title; required with a class flag')
    create.add_argument('--evidence', action='append', default=[],
                        help='One evidence line, for example cli/x.py:12; repeatable')
    create.add_argument('--seat', choices=('builder', 'sentinel-arch', 'sentinel-goal', 'sentinel-quality',
                                           'sentinel-security'),
                        help='Your seat role, recorded on the event (#644)')
    actions.add_parser('log', help="Write today's decisions, progress, verdicts, PR and close "
                                   'as ticket comments')
    done = actions.add_parser('done', help="Move the item's ticket to the done state")
    done.add_argument('item')
    move = actions.add_parser('move', help="Move the item's ticket to a lifecycle state")
    move.add_argument('item')
    move.add_argument('state', choices=('in_review', 'done'))
    parser.set_defaults(func=run)


def run(args):
    try:
        root = workspace.find_workspace()
        if args.action == 'log':
            return tracker.log(root)
        if args.action in ('done', 'move'):
            from wuwei import dispatch
            action = 'done' if args.action == 'done' else args.state
            result = dispatch.tracker_call(args.item, action, root)
            reason = f'{args.item}: ticket {action}' if result.exit == 0 else result.reason
        else:
            result = tracker.create(root, args.subject, args.category or 'items', args.title,
                                    args.evidence, seat=args.seat)
            reason = result.reason
        # A created, found or drafted ticket is the answer; anything else is a reason.
        if result.exit == 0 or result.data:
            print(reason)
        else:
            print(f'wuwei tracker: {reason}', file=sys.stderr)
        return result.exit
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei tracker: {exc}', file=sys.stderr)
        return UNRUN
