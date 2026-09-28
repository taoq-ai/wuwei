"""Promote today's proposals."""

import sys

from wuwei import promotion
from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    subparsers.add_parser('promote', help='promote memory proposals').set_defaults(func=run)


def run(args):
    records = promotion.promote()
    for record in records:
        print(f"{record['status']}: {record['target']}: {record['reason']}")
    return FINDINGS if any(r['status'] == 'rejected' for r in records) else CLEAN
