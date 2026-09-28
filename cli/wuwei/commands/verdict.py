"""Lint a saved gate verdict through the shared checker."""

import sys

from wuwei.verdict import lint_file


def register(subparsers):
    parser = subparsers.add_parser('verdict', help='Check a gate verdict')
    commands = parser.add_subparsers(dest='action', required=True)
    lint = commands.add_parser('lint', help='Lint a saved verdict file')
    lint.add_argument('file')
    lint.add_argument('--role', default='', help='Sentinel role, optionally plugin-prefixed')
    lint.set_defaults(func=run)


def run(args):
    code, message = lint_file(args.file, role=args.role)
    print(message, file=sys.stderr if code else sys.stdout)
    return code
