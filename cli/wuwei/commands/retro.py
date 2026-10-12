"""Write a local steward retro from today's evidence, or land its charter proposals."""

from pathlib import Path
import sys

from wuwei import retro, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('retro', help='Compile the steward retro or land its proposals')
    parser.add_argument('--promote', action='store_true', help="land today's charter proposals")
    parser.set_defaults(func=run)


def run(args):
    if args.promote:
        return promote()
    if workspace.guard_scope({'cwd': str(Path.cwd())}) is None:
        return 0
    print(retro.compile().relative_to(workspace.find_workspace()))
    return 0


def promote():
    from wuwei import memory, promotion
    records = promotion.promote()
    for record in records:
        print(f"{record['status']}: {record['target']}: {record['reason']}")
    if any(r['status'] == 'landed' for r in records):
        try:
            memory.export()
            memory.write_index()
        except (OSError, ValueError) as exc:
            print(f'wuwei retro --promote export: {exc}', file=sys.stderr)
            return UNRUN
    return FINDINGS if any(r['status'] == 'rejected' for r in records) else CLEAN
