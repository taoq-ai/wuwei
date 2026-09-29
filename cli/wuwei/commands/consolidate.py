"""Review memory and archive expired days."""

from wuwei import consolidation, workspace
from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    subparsers.add_parser('consolidate', help='review and archive workspace memory').set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    findings = consolidation.note_findings(root)
    moved = consolidation.archive_days(root)
    for day in moved:
        print(f'{day}: archived')
    for finding in findings:
        print(finding)
    return FINDINGS if findings else CLEAN
