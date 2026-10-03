"""Promote today's proposals."""

import sys

from wuwei import memory, promotion
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    subparsers.add_parser('promote', help='promote memory proposals').set_defaults(func=run)


def run(args):
    records = promotion.promote()
    for record in records:
        print(f"{record['status']}: {record['target']}: {record['reason']}")
    if any(r['status'] == 'landed' for r in records):
        try:
            memory.export()
        except (OSError, ValueError) as exc:
            print(f'wuwei promote: export: {exc}', file=sys.stderr)
            return UNRUN
    return FINDINGS if any(r['status'] == 'rejected' for r in records) else CLEAN
