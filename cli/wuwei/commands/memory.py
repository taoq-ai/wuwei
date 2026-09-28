"""Run read-only memory checks."""

from wuwei import memory
from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    parser = subparsers.add_parser('memory', help='check workspace memory')
    actions = parser.add_subparsers(dest='memory_action', required=True)
    actions.add_parser('lint', help='report memory findings').set_defaults(func=run_lint)


def run_lint(args):
    findings = memory.lint()
    for finding in findings:
        print(f'wuwei memory lint: {finding}')
    return FINDINGS if findings else CLEAN
