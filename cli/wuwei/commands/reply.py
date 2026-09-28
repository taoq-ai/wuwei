"""Post and verify a shepherd reply before recording its acknowledgement."""

import sys

from wuwei import obligations


def register(subparsers):
    parser = subparsers.add_parser('reply', help='Reply to one unthreaded human obligation')
    parser.add_argument('ref', help='owner/repo#number')
    parser.add_argument('--surface', required=True, choices=('comment', 'review'))
    parser.add_argument('--id', required=True, type=int, help='Target comment or review ID')
    parser.set_defaults(func=run)


def run(args):
    return obligations.reply(args.ref, args.surface, args.id, sys.stdin.read())
