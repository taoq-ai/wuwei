"""Print the session memory payload."""

from wuwei import memory, state, workspace
from wuwei.exits import CLEAN


def register(subparsers):
    subparsers.add_parser('payload', help='print session memory payload').set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    constraints = memory.constraints(root, state.read_state(root))
    content = constraints + '\n' + memory.session_payload(root)[0]
    print(content, end='')
    print(f'Size: {len(content.encode("utf-8"))} bytes, {memory.estimated_tokens(content)} estimated tokens')
    return CLEAN
