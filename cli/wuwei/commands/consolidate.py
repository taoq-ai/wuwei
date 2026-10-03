"""Review memory, archive expired days, rebuild digests and propose forgetting."""

import json

from wuwei import consolidation, workspace
from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    parser = subparsers.add_parser('consolidate', help='review and archive workspace memory')
    parser.add_argument('--widget', action='store_true',
                        help='Print each pending forgetting proposal as an AskUserQuestion widget; writes nothing')
    parser.set_defaults(func=run)


def widget(root, row):
    from wuwei import decision
    what = f'{row["action"]} {row["target"].rsplit("/", 1)[-1]}'
    return decision.widget(
        decision.gate(root) + f'{row["id"]}: {row["evidence"]}. {what.capitalize()}?', row['id'],
        [('apply', f'Recommended. {what.capitalize()}; the before text stays under memory/archive.'),
         ('keep', 'Keep it; it is not proposed again.')],
        f'bin/wuwei memory forget {row["id"]} <label>')


def run(args):
    root = workspace.find_workspace()
    if getattr(args, 'widget', False):
        pending = sorted((row for row in consolidation.read_forget(root).values() if row['status'] == 'pending'),
                         key=lambda row: int(row['id'][2:]))
        print(json.dumps([widget(root, row) for row in pending], indent=2))
        return int(bool(pending))
    from wuwei import digest, memory, state
    findings = consolidation.note_findings(root)
    moved = consolidation.archive_days(root)
    # archive_days wrote and committed the digests of the days it packed.
    for kind in ('week', 'month'):
        digest.write(root, workspace.now().date(), kind)
    pending = consolidation.merge_proposals(root, consolidation.forget_proposals(root))
    memory.export(root)
    state.append_event('memory.consolidated', {'archived': len(moved), 'pending': len(pending)}, root)
    for day in moved:
        print(f'{day}: archived')
    for finding in findings:
        print(finding)
    for row in pending:
        print(f'{row["id"]}: {row["action"]} {row["target"].rsplit("/", 1)[-1]}: {row["evidence"]}')
    return FINDINGS if findings or pending else CLEAN
