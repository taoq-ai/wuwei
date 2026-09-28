"""Report outbound tiers without sending or creating drafts."""

import json
import sys

from wuwei import outward, workspace
from wuwei.exits import UNRUN


def register(subparsers):
    parser = subparsers.add_parser('outbound', help='inspect outbound approval policy')
    actions = parser.add_subparsers(dest='action', required=True)
    tier = actions.add_parser('tier', help='classify one JSON message from stdin')
    tier.set_defaults(func=run)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def run(args):
    code, decision = UNRUN, 'draft'
    try:
        inputs = json.load(sys.stdin, object_pairs_hook=_unique)
        kind = inputs.pop('kind', 'chat')
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        texts, _ = outward._text(inputs)
        code, decision = outward.classify('\n'.join(texts), root, config, inputs, kind=kind)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    print(json.dumps({'tier': decision, 'exit': code}))
    if code:
        reason = 'cannot classify policy, audience or message evidence; ' if code == UNRUN else ''
        print(f'outbound: {reason}deliver as a draft for the owner to send', file=sys.stderr)
    return code
