"""Dedicated producer for externally verified PR dispositions."""

from wuwei import pr_actions, workspace


def register(subparsers):
    parser = subparsers.add_parser('pr', help='Record a verified PR disposition')
    commands = parser.add_subparsers(dest='action', required=True)
    record = commands.add_parser('disposition')
    record.add_argument('ref')
    record.add_argument('kind', choices=('parked', 'carried'))
    record.add_argument('--decision', required=True)
    record.add_argument('--comment', type=int, required=True)
    record.set_defaults(func=run)


def run(args):
    return pr_actions.record_disposition(workspace.find_workspace(), args.ref, args.kind,
                                         args.decision, args.comment)
