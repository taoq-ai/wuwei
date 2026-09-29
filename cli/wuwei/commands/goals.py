"""Owner goals commands."""

from wuwei.commands import _owner_edit


def register(subparsers):
    goals = subparsers.add_parser('goals', help='owner goals')
    actions = goals.add_subparsers(dest='action', required=True)
    _owner_edit.register(actions)
