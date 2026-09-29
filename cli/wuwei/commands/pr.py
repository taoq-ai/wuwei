"""Dedicated producer for externally verified PR dispositions."""

import json

from wuwei import pr_actions, shepherd, workspace


def register(subparsers):
    parser = subparsers.add_parser('pr', help='Measure owned PRs or record a verified disposition')
    commands = parser.add_subparsers(dest='action', required=True)
    status = commands.add_parser('state', help='Fresh state and dispatch data for owned PRs')
    status.add_argument('refs', nargs='*')
    status.set_defaults(func=run_state)
    raise_cmd = commands.add_parser('raise', help='Raise a prepared PR')
    raise_cmd.add_argument('repo')
    raise_cmd.add_argument('--base', required=True)
    raise_cmd.add_argument('--title', required=True)
    raise_cmd.add_argument('--body-file', required=True)
    raise_cmd.add_argument('--item', required=True)
    raise_cmd.set_defaults(func=run_raise)
    claim = commands.add_parser('claim', help='Claim an existing PR for an item')
    claim.add_argument('ref')
    claim.add_argument('--item', required=True)
    claim.set_defaults(func=run_claim)
    ping = commands.add_parser('ping', help='Request reviewers and post when gates clear')
    ping.add_argument('ref')
    ping.set_defaults(func=run_ping)
    ping_check = commands.add_parser('ping-check', help='Measure review ping gate')
    ping_check.add_argument('ref')
    ping_check.set_defaults(func=run_ping_check)
    act = commands.add_parser('act', help='Execute the next owned PR action')
    act.add_argument('ref')
    act.set_defaults(func=run_act)
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


def run_raise(args):
    from pathlib import Path
    path = Path(args.body_file)
    if path.is_symlink() or not path.is_file():
        raise ValueError('body file must be a regular file')
    return shepherd.raise_pr(workspace.find_workspace(), args.repo, args.base,
                             args.title, path.read_text(encoding='utf-8'), args.item)


def run_claim(args):
    return shepherd.claim_pr(workspace.find_workspace(), args.ref, args.item)


def run_ping(args):
    return shepherd.post_review_request(workspace.find_workspace(), args.ref)


def run_ping_check(args):
    result = shepherd.ping_gate(workspace.find_workspace(), args.ref)
    print(result.reason or 'review ping gate clear')
    return result.exit


def run_act(args):
    return pr_actions.act(workspace.find_workspace(), args.ref)
