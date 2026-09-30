"""Owner actions for the remote control plane, run in a host terminal."""

import sys

from wuwei import remote, workspace


def register(subparsers):
    parser = subparsers.add_parser('remote', help='Owner actions for the remote control plane')
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('ack', help="Acknowledge today's refused-sender pages (owner, host terminal)")
    parser.set_defaults(func=run)


def run(args):
    code, message = remote.acknowledge(workspace.find_workspace())
    print(message, file=sys.stderr if code else sys.stdout)
    return code
