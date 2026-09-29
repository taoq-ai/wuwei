"""Dedicated producer for externally verified PR dispositions."""

import json

from wuwei import pr_actions, workspace


def register(subparsers):
    parser = subparsers.add_parser('pr', help='Measure owned PRs or record a verified disposition')
    commands = parser.add_subparsers(dest='action', required=True)
    status = commands.add_parser('state', help='Fresh state and dispatch data for owned PRs')
    status.add_argument('refs', nargs='*')
    status.set_defaults(func=run_state)
    record = commands.add_parser('disposition')
    record.add_argument('ref')
    record.add_argument('kind', choices=('parked', 'carried'))
    record.add_argument('--decision', required=True)
    record.add_argument('--comment', type=int, required=True)
    record.set_defaults(func=run)


def run(args):
    return pr_actions.record_disposition(workspace.find_workspace(), args.ref, args.kind,
                                         args.decision, args.comment)


def run_state(args):
    code, rows = pr_actions.evaluate(workspace.find_workspace(), args.refs or None)
    print(json.dumps(rows, sort_keys=True))
    return code
