"""List memory archive candidates."""

from wuwei import promotion
from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    subparsers.add_parser('consolidate', help='list archive candidates').set_defaults(func=run)


def run(args):
    candidates = promotion.archive_candidates()
    for slug, loads in candidates:
        print(f'{slug}: archive candidate ({loads} loads)')
    return FINDINGS if candidates else CLEAN
