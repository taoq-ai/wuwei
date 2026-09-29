"""Print and save the local owner report."""

from pathlib import Path

from wuwei import report, workspace


def register(subparsers):
    subparsers.add_parser('report', help='Show the owner report').set_defaults(func=run)


def run(args):
    if workspace.guard_scope({'cwd': str(Path.cwd())}) is None:
        return 0
    print(report.write().read_text(encoding='utf-8'), end='')
    return 0
