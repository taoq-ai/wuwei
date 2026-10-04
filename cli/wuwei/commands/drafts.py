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
    text = approve.add_mutually_exclusive_group()
    text.add_argument('--edit', action='store_true')
    text.add_argument('--file', help='send this text instead, after the same lint')
    drop = actions.add_parser('drop', help='drop a draft from the owner host terminal')
    drop.add_argument('id')
    show = actions.add_parser('show', help='print a pending draft, or its card with --widget')
    show.add_argument('id')
    show.add_argument('--widget', action='store_true')


def run(args):
    root = workspace.find_workspace()
    if args.action == 'show':
        try:
            row = drafts._pending(state.read_state(root), args.id)
        except state.StateError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(json.dumps([drafts.widget(row, workspace.load_config(root))] if args.widget else row,
                         indent=2))
        return 0
    if args.action:
        result = (drafts.approve(root, args.id, edit=args.edit, source=args.file) if args.action == 'approve'
                  else drafts.drop(root, args.id))
        print(result.reason, file=sys.stderr if result.exit else sys.stdout)
        return result.exit
    rows = drafts.read(state.read_state(root))
    print(json.dumps([row for row in rows.values() if row['status'] == 'pending'], indent=2))
    return 0
