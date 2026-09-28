"""Record evidence by executing configured checks, never caller-provided results."""

import sys

from wuwei.fast_checks import record


def register(subparsers):
    parser = subparsers.add_parser('fast-checks', help='Run and record configured fast checks')
    parser.add_argument('path', nargs='?', default='.', help='Repository checkout or linked worktree')
    parser.set_defaults(func=run)


def run(args):
    code = record(args.path)
    if code:
        print('fast checks failed' if code == 1 else 'fast checks could not run', file=sys.stderr)
    return code
