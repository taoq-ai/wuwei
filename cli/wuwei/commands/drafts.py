"""List outward drafts and decide them from the owner host CLI."""

import json
import sys

from wuwei import drafts, state, workspace


def register(subparsers):
    parser = subparsers.add_parser('drafts', help='list outward drafts awaiting owner approval')
    parser.set_defaults(func=run)
    actions = parser.add_subparsers(dest='action')
    approve = actions.add_parser('approve', help='send a draft from the owner host terminal')
    approve.add_argument('id')
    approve.add_argument('--edit', action='store_true')
    drop = actions.add_parser('drop', help='drop a draft from the owner host terminal')
    drop.add_argument('id')


def run(args):
    root = workspace.find_workspace()
    if args.action:
        result = (drafts.approve(root, args.id, edit=args.edit) if args.action == 'approve'
                  else drafts.drop(root, args.id))
        print(result.reason, file=sys.stderr if result.exit else sys.stdout)
        return result.exit
    rows = drafts.read(state.read_state(root))
    print(json.dumps([row for row in rows.values() if row['status'] == 'pending'], indent=2))
    return 0
