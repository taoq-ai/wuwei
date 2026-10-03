"""Write a local steward retro from today's evidence."""

from pathlib import Path

from wuwei import retro, workspace


def register(subparsers):
    subparsers.add_parser('retro', help='Compile the steward retro').set_defaults(func=run)


def run(args):
    if workspace.guard_scope({'cwd': str(Path.cwd())}) is None:
        return 0
    print(retro.compile().relative_to(workspace.find_workspace()))
    from wuwei.commands import docs
    return docs.listed('retro')
