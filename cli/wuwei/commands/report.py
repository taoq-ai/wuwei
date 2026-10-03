"""Print and save the local owner report."""

from pathlib import Path

from wuwei import report, workspace


def register(subparsers):
    subparsers.add_parser('report', help='Show the owner report').set_defaults(func=run)


def run(args):
    root = workspace.guard_scope({'cwd': str(Path.cwd())})
    if root is None:
        return 0
    if not (workspace.day_dir(root) / 'state.json').is_file():
        print('No report today: no day has started. Start one with /wuwei:wuwei-plan.')
        return 0
    print(report.write().read_text(encoding='utf-8'), end='')
    from wuwei.commands import docs
    return docs.listed('report')
