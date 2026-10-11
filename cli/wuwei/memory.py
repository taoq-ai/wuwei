"""Generated memory index and session payload."""

from datetime import date
import re
from pathlib import Path

from wuwei import workspace
from wuwei.exits import SYMLINK


def estimated_tokens(text):
    # ponytail: characters / 4 is a rough estimator; replace if real token budgets need precision.
    return (len(text) + 3) // 4


def write_index(root=None):
    """Write a deterministic index and return its findings, if any."""
    root = workspace.find_workspace() if root is None else Path(root)
    memory = root / '.wuwei/memory'
    if memory.is_symlink() or not memory.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'memory directory must be inside the workspace and not a symlink; {SYMLINK}')
    lines = []
    findings = []
    today = workspace.now().date()
    days = []
    for parent in (root / '.wuwei/days', root / '.wuwei/archive'):
        if parent.is_symlink():
            raise ValueError(f'day directory must not be a symlink: {parent}')
        if not parent.exists():
            continue
        for day in parent.iterdir():
            if day.is_symlink():
                raise ValueError(f'day directory must not be a symlink: {day}')
            if not day.is_dir():
                continue
            try:
                day_date = date.fromisoformat(day.name)
            except ValueError:
                continue
            if day.name != day_date.isoformat() or day_date >= today:
                continue
            days.append(day)
    for day in sorted(days, key=lambda path: path.name):
        report = day / 'report.md'
        if report.is_symlink():
            raise ValueError(f'report must not be a symlink: {report}')
        try:
            first = report.read_text(encoding='utf-8').splitlines()[:1] if report.exists() else []
        except UnicodeError as exc:
            lines.append(f'{day.name} | INVALID report: {exc}')
            findings.append(f'INVALID report: {exc}')
            continue
        lines.append(f'{day.name} | {first[0] if first else "no report"}')
    content = '\n'.join(lines) + ('\n' if lines else '')
    workspace.atomic_write(memory / 'index.md', content, mode=0o644)
    return findings


def constraints(root, data):
    """The day's goals, plan, open decisions and running briefs, restated at every SessionStart."""
    goals = 'none'
    if data['goals']:
        from wuwei import goals as goal_file
        try:
            parsed = goal_file.parse((root / '.wuwei/memory/goals.md').read_text(encoding='utf-8'))
            goals = '; '.join(
                f'{ident} {parsed[ident]["outcome"]} (target {parsed[ident]["target"]} by '
                f'{parsed[ident]["date"]})' if ident in parsed else ident for ident in data['goals'])
        except (OSError, ValueError) as exc:
            goals = f'unmeasured: {exc}'
    plan = (f'{(workspace.day_dir(root) / "plan.md").relative_to(root).as_posix()} '
            f'(approved: {", ".join(data["approved_items"]) or "none"})'
            if data['gate_approved'] else 'not approved')
    routes = data.get('decision_routes', {})
    if routes:
        from wuwei.decision import answered
    open_ids = sorted(ident for ident in routes if answered(data, ident) is None)
    briefs = [f'{seat.get("item")} {name} {seat.get("brief")}' for name, seat in data['seats'].items()
              if seat.get('status') == 'running' and seat.get('brief')]  # #676: adhoc has none
    briefs += [f'{item} build {build.get("brief")}' for item, build in data.get('builds', {}).items()
               if build.get('status') in ('running', 'check')]
    return (f'Active constraints:\nGoals: {goals}\nPlan: {plan}\n'
            f'Open decisions: {", ".join(open_ids) or "none"}\n'
            f'Current briefs: {"; ".join(briefs) or "none"}\n')


def session_payload(root=None):
    """Return payload text, UTF-8 byte count and estimated token count: the spine, then today;
    over memory.budget_tokens today is left out with one line saying so."""
    root = workspace.find_workspace() if root is None else Path(root)
    memory = root / '.wuwei/memory'
    spine = (memory / 'spine.md').read_text(encoding='utf-8')
    index = (memory / 'index.md').read_text(encoding='utf-8').splitlines()
    budget = workspace.load_config(root)['memory']['budget_tokens']
    from wuwei.promotion import last_run
    promote_line = last_run(root)
    days = [line for line in index if re.match(r'\d{4}-\d{2}-\d{2} \|', line)]
    kept = f'Rules:\nSpine:\n{spine.rstrip()}\n\n'
    content = kept + ('Today:\n' + ''.join(f'{line}\n' for line in days)
                      + f'Full day state: wuwei state get\n{promote_line}\n')
    if estimated_tokens(content) > budget:
        content = (kept + f'Memory budget: {estimated_tokens(content)} of {budget} estimated tokens; '
                   'today left out (wuwei state get).\n')
    return content, len(content.encode('utf-8')), estimated_tokens(content)


EXPORT_START, EXPORT_END = '<!-- wuwei:memory:start -->', '<!-- wuwei:memory:end -->'


def export(root=None):
    """Write charter rules between owned markers in the harness memory file memory.export_to
    names. One way: nothing reads the block back. (path, changed)."""
    root = workspace.find_workspace() if root is None else Path(root)
    lines = [EXPORT_START, '## WUWEI rules', '',
             'Generated by wuwei memory export from the workspace charters.',
             'Change them through wuwei promote; edits here are overwritten.']
    charters = root / '.wuwei/charters'
    if charters.is_symlink():
        raise ValueError(f'charters must not be a symlink; {SYMLINK}')
    for charter in sorted(charters.glob('*.md')):
        if charter.is_symlink():
            raise ValueError(f'charter must not be a symlink: {charter.name}')
        rules = [line for line in charter.read_text(encoding='utf-8').splitlines() if line.startswith('- ')]
        if rules:
            lines += ['', f'### {charter.stem}', *rules]
    block = '\n'.join([*lines, EXPORT_END]) + '\n'
    return write_block(root, EXPORT_START, EXPORT_END, block, 'bin/wuwei memory export --claude')


def write_block(root, start, end, block, fix, write=True, raw=None):
    """Put block (start marker through end marker, newline-terminated) into the file
    memory.export_to names, replacing the one block between start and end and keeping all
    other text. fix: the command named when the markers are damaged; raw: config text read in
    place of config.toml (init --upgrade passes its repaired text). (path, changed)."""
    root = Path(root)
    raw = workspace.load_config(root, raw=raw)['memory']['export_to']
    relative = Path(raw)
    if (not raw or relative.is_absolute() or '..' in relative.parts
            or relative.parts[0] == '.wuwei'):
        raise ValueError(f'memory.export_to must be a workspace-relative path outside .wuwei: {raw}')
    path = root / relative
    if any(part.is_symlink() for part in (path, *list(path.parents)[:-len(root.parts)])):
        raise ValueError(f'memory.export_to must not use a symlink: {raw}')
    existing = path.read_text(encoding='utf-8') if path.exists() else ''
    starts = existing.count(start)
    if starts > 1 or (starts and end not in existing.split(start, 1)[1]):
        raise ValueError(f'{raw}: expected one {start} with its {end}; restore the '
                         f'markers or remove the block, then run {fix}')
    if not block and not starts:
        return path, False
    if starts:
        before, rest = existing.split(start, 1)
        after = rest.split(end, 1)[1].removeprefix('\n')
        updated = before + block + after
    else:
        updated = existing.rstrip('\n') + '\n\n' + block if existing.strip() else block
    if updated == existing:
        return path, False
    if write:
        workspace.atomic_write(path, updated, mode=0o644)
    return path, True
