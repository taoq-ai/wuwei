"""Memory checks, archived day reads, tier status, the harness export and owner forgetting."""

from datetime import date
import sys

from wuwei import memory
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('memory', help='check workspace memory')
    actions = parser.add_subparsers(dest='memory_action', required=True)
    actions.add_parser('lint', help='report memory findings').set_defaults(func=run_lint)
    show = actions.add_parser('show', help='print one day of records, raw or archived')
    show.add_argument('date', type=date.fromisoformat)
    show.set_defaults(func=run_show)
    actions.add_parser('status', help='print the size of every memory tier').set_defaults(func=run_status)
    export = actions.add_parser('export', help='write the rules block into the harness memory file')
    export.add_argument('--claude', action='store_true', required=True)
    export.set_defaults(func=run_export)
    forget = actions.add_parser('forget', help='owner answer to one forgetting proposal (host terminal)')
    forget.add_argument('id')
    forget.add_argument('label', choices=('apply', 'keep'))
    forget.set_defaults(func=run_forget)


def run_lint(args):
    findings = memory.lint()
    for finding in findings:
        print(f'wuwei memory lint: {finding}')
    return FINDINGS if findings else CLEAN


def run_show(args):
    from wuwei import consolidation, workspace
    day = args.date.isoformat()
    try:
        records = consolidation.day_records(workspace.find_workspace(), day)
    except (OSError, ValueError) as exc:
        print(f'wuwei memory show: {exc}', file=sys.stderr)
        return UNRUN
    if records is None:
        print(f'wuwei memory show: no records for {day}', file=sys.stderr)
        return FINDINGS
    for name in sorted(records):
        print(f'== {name} ==\n{records[name]}', end='' if records[name].endswith('\n') else '\n')
    return CLEAN


def _tokens(paths):
    return sum(memory.estimated_tokens(path.read_text(encoding='utf-8')) for path in paths if path.is_file())


def _bytes(paths):
    return sum(path.stat().st_size for path in paths if path.is_file())


def run_status(args):
    from wuwei import consolidation, watch, workspace
    try:
        root = workspace.find_workspace()
        base = root / '.wuwei'
        raw = watch.days(root)
        tarballs = sorted((base / 'archive').glob('*/*.tar.gz'))
        legacy = [path for path in consolidation.expired(root) if path.parent.name == 'archive']
        digests = sorted((base / 'memory/digests').glob('*.md'))
        weeks = [path for path in digests if '-W' in path.stem]
        charters = sorted((base / 'charters').glob('*.md'))
        notes = sorted((base / 'memory/notes').glob('*.md'))
        tokens = memory.session_payload(root)[2]
        last = next((day.name for day in raw if any(
            row.get('kind') == 'memory.consolidated' for row in watch.records(day / 'events.jsonl'))), 'none')
        pending = [row for row in consolidation.read_forget(root).values() if row['status'] == 'pending']
        budget = workspace.load_config(root)['memory']['budget_tokens']
        print(f'raw: {len(raw)} days, {_bytes(p for day in raw for p in day.rglob("*"))} bytes\n'
              f'archive: {len(tarballs) + len(legacy)} days, '
              f'{_bytes([*tarballs, *(p for day in legacy for p in day.rglob("*"))])} bytes\n'
              f'digests: {len(weeks)} weeks, {len(digests) - len(weeks)} months, '
              f'{_tokens(digests)} estimated tokens\n'
              f'rules: {len(charters)} charters, spine, {len(notes)} notes, '
              f'{_tokens([*charters, base / "memory/spine.md", *notes])} estimated tokens\n'
              f'payload: {tokens} of {budget} estimated tokens\n'
              f'last consolidate: {last}\n'
              f'pending proposals: {len(pending)} (wuwei consolidate --widget)')
    except (OSError, ValueError) as exc:
        print(f'wuwei memory status: {exc}', file=sys.stderr)
        return UNRUN
    return CLEAN


def run_export(args):
    try:
        path, changed = memory.export()
    except (OSError, ValueError) as exc:
        print(f'wuwei memory export: {exc}', file=sys.stderr)
        return UNRUN
    print(f'export: {path} {"written" if changed else "unchanged"}')
    return CLEAN


def run_forget(args):
    from wuwei import consolidation, workspace
    try:
        row = consolidation.forget(workspace.find_workspace(), args.id, args.label)
    except (ValueError, PermissionError) as exc:
        print(f'wuwei memory forget: {exc}', file=sys.stderr)
        return FINDINGS
    except OSError as exc:
        print(f'wuwei memory forget: {exc}', file=sys.stderr)
        return UNRUN
    print(f'{row["id"]}: {row["status"]}')
    return CLEAN
