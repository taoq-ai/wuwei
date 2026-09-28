"""Print the session memory payload."""

from wuwei import memory
from wuwei.exits import CLEAN


def register(subparsers):
    subparsers.add_parser('payload', help='print session memory payload').set_defaults(func=run)


def run(args):
    content, size, tokens = memory.session_payload()
    print(content, end='')
    print(f'Size: {size} bytes, {tokens} estimated tokens')
    return CLEAN
