"""Generate the workspace memory index."""

import sys

from wuwei import memory, workspace
from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    subparsers.add_parser('index', help='generate memory index').set_defaults(func=run)


def run(args):
    try:
        findings = memory.write_index()
    except workspace.ConfigError as exc:
        print(f'wuwei index: {exc}', file=sys.stderr)
        return FINDINGS
    for finding in findings:
        print(f'wuwei index: {finding}', file=sys.stderr)
    return FINDINGS if findings else CLEAN
