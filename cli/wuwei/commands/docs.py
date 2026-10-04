"""Write the item's docs page or publish the day's report or retro (#419)."""

import sys

from wuwei import docs, state
from wuwei.exits import FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('docs', help="Write an item's docs page or publish the day's page")
    actions = parser.add_subparsers(dest='action', required=True)
    page = actions.add_parser('page', help="Write or draft the item's page from its records")
    page.add_argument('item')
    publish = actions.add_parser('publish', help="Publish today's report or retro once")
    publish.add_argument('kind', choices=('report', 'retro'))
    parser.set_defaults(func=run)


def run(args):
    return _finish(lambda: docs.page(None, args.item) if args.action == 'page'
                   else docs.publish(None, args.kind))


def listed(kind):
    """After wuwei report or wuwei retro: publish when docs.publish lists the kind."""
    return _finish(lambda: docs.published(None, kind) or (0, ''))


def _finish(call):
    try:
        code, message = call()
    except state.StateError as exc:
        code, message = FINDINGS, str(exc)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        code, message = UNRUN, f'docs: {exc}'
    if message:
        print(message, file=sys.stderr if code else sys.stdout)
    return code
