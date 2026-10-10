"""Generated memory index and session payload."""

from datetime import date, timedelta
import json
import re
from pathlib import Path

from wuwei import state, workspace
from wuwei.notes import SLUG_RE, parse_note
from wuwei.exits import DAMAGED, SYMLINK


def estimated_tokens(text):
    # ponytail: characters / 4 is a rough estimator; replace if real token budgets need precision.
    return (len(text) + 3) // 4


def write_index(root=None):
    """Write a deterministic index and return its findings, if any."""
    root = workspace.find_workspace() if root is None else Path(root)
    memory = root / '.wuwei/memory'
    notes = memory / 'notes'
    if (memory.is_symlink() or notes.is_symlink() or not notes.is_dir()
            or not notes.resolve().is_relative_to(root)):
        raise ValueError(f'memory notes directory must be inside the workspace and not a symlink; {SYMLINK}')
    maximum = workspace.load_config(root)['memory']['max_notes']
    lines = []
    findings = []
    active = 0
    for path in sorted(notes.glob('*.md')):
        slug = path.stem
        if path.is_symlink():
            raise ValueError(f'note must not be a symlink: {path}')
        try:
            if not SLUG_RE.fullmatch(slug):
                raise ValueError(f'invalid slug; {DAMAGED}')
            content = path.read_text(encoding='utf-8')
            fields, _ = parse_note(content)
        except (ValueError, UnicodeError) as exc:
            display = repr(slug) if not SLUG_RE.fullmatch(slug) else slug
            lines.append(f'INVALID {display}: {exc}')
            findings.append(f'INVALID {display}: {exc}')
            continue
        if fields['status'] == 'active':
            active += 1
            lines.append(f'{slug} | {fields["type"]} | {fields["summary"]} | '
                         f'{estimated_tokens(content)} tokens')
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
    if active > maximum:
        findings.append(f'memory.max_notes overflow: {active - maximum}')
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
    """Return payload text, UTF-8 byte count and estimated token count: digests, then rules,
    then today; over memory.budget_tokens today is left out with one line saying so."""
    root = workspace.find_workspace() if root is None else Path(root)
    memory = root / '.wuwei/memory'
    spine = (memory / 'spine.md').read_text(encoding='utf-8')
    index = (memory / 'index.md').read_text(encoding='utf-8').splitlines()
    budget = workspace.load_config(root)['memory']['budget_tokens']
    from wuwei.digest import latest
    from wuwei.promotion import last_run
    promote_line = last_run(root)
    digests = [path.read_text(encoding='utf-8').rstrip() + '\n\n' for path in latest(root) if path]
    days = [line for line in index if re.match(r'\d{4}-\d{2}-\d{2} \|', line)]
    notes = [line for line in index if line not in days]
    kept = (('Digests:\n' + ''.join(digests)) if digests else '') + (
        f'Rules:\nSpine:\n{spine.rstrip()}\n\nNotes:\n' + ''.join(f'{line}\n' for line in notes) + '\n')
    content = kept + ('Today:\n' + ''.join(f'{line}\n' for line in days)
                      + f'Full day state: wuwei state get\n{promote_line}\n')
    if estimated_tokens(content) > budget:
        content = (kept + f'Memory budget: {estimated_tokens(content)} of {budget} estimated tokens; '
                   'today left out (wuwei state get, wuwei memory status).\n')
    return content, len(content.encode('utf-8')), estimated_tokens(content)


EXPORT_START, EXPORT_END = '<!-- wuwei:memory:start -->', '<!-- wuwei:memory:end -->'


def export(root=None):
    """Write charter rules and the latest week's lessons between owned markers in the harness
    memory file memory.export_to names. One way: nothing reads the block back. (path, changed)."""
    root = workspace.find_workspace() if root is None else Path(root)
    lines = [EXPORT_START, '## WUWEI rules', '',
             'Generated by wuwei memory export from the workspace charters and the latest week digest.',
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
    from wuwei.digest import latest
    week = latest(root)[1]
    if week is not None:
        section = week.read_text(encoding='utf-8').split('\n## Lessons\n', 1)[1:]
        lessons = [line for line in (section[0].split('\n## ', 1)[0] if section else '').splitlines()
                   if line.startswith('- ')]
        if lessons:
            lines += ['', f'### Lessons, {week.stem}', *lessons]
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


DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")


def _dates(text):
    dates = []
    for token in DATE_RE.findall(text):
        try:
            dates.append(date.fromisoformat(token))
        except ValueError:
            pass
    return dates


def lint(root=None):
    """Return active note findings for the session-start caller."""
    root = workspace.find_workspace() if root is None else Path(root)
    notes = root / '.wuwei/memory/notes'
    if (notes.is_symlink() or not notes.is_dir()
            or not notes.resolve().is_relative_to(root)):
        raise ValueError(f'memory notes directory must be inside the workspace and not a symlink; {SYMLINK}')
    config = workspace.load_config(root)['memory']
    findings = []
    loads = None
    for path in sorted(notes.glob('*.md')):
        if path.is_symlink():
            raise ValueError(f'note must not be a symlink: {path}')
        if not SLUG_RE.fullmatch(path.stem):
            raise ValueError(f'invalid note slug: {path.name}')
        content = path.read_text(encoding='utf-8')
        fields, body = parse_note(content)
        if fields['status'] != 'active':
            continue
        summary_dates = _dates(fields['summary'])
        body_dates = _dates(body)
        if summary_dates and body_dates and max(body_dates) > max(summary_dates):
            findings.append(f'{path.name}: stale summary; body dated {max(body_dates)}')
        count = len(content.splitlines())
        if count > config['note_line_cap']:
            findings.append(f'{path.name}: line cap {config["note_line_cap"]} exceeded ({count})')
        if path.stem == 'state' or path.stem.endswith('-state'):
            entries = sum(bool(re.match(r'^\s*(?:#{1,6}\s*)?\d{4}-\d{2}-\d{2}\b', line))
                          for line in body.splitlines())
            if entries > config['state_entry_cap']:
                findings.append(f'{path.name}: {entries} dated entries; state note is log-shaped')
        if fields.get('created'):
            created = date.fromisoformat(fields['created'])
            today = workspace.now().date()
            working_days = sum((created + timedelta(days=offset)).weekday() < 5
                               for offset in range(1, max(0, (today - created).days) + 1))
            if working_days > config['probation_days']:
                if loads is None:
                    loads = _loaded_notes(root)
                if path.resolve() not in loads:
                    findings.append(f'{path.name}: archive candidate; never loaded after probation')
        if path.stem == 'intake' or path.stem.endswith('-intake'):
            outbound = re.search(r'\[[^]]+\]\((?!#)[^)]+\)|\[\[[^]]+\]\]', body)
            if not outbound and not _promoted_intake(root, path.name):
                findings.append(f'{path.name}: unrouted intake')
    return findings


def _promoted_intake(root, name):
    ledger = root / '.wuwei/memory/ledger.jsonl'
    if ledger.is_symlink():
        raise ValueError(f'ledger must not be a symlink: {ledger}')
    if not ledger.exists():
        return False
    for line in ledger.read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f'invalid ledger record: {ledger}')
        if record.get('evidence') in (name, f'notes/{name}', f'memory/notes/{name}') and record.get('action') in ('add', 'patch', 'fold') and record.get('target'):
            return True
    return False


def _loaded_notes(root):
    loads = set()
    for parent in (root / '.wuwei/days', root / '.wuwei/archive'):
        if parent.is_symlink():
            raise ValueError(f'trace directory must not be a symlink: {parent}')
        if not parent.exists():
            continue
        for day in parent.iterdir():
            if day.is_symlink():
                raise ValueError(f'trace day must not be a symlink: {day}')
            if not day.is_dir():
                continue
            trace = day / 'traces.jsonl'
            if trace.is_symlink():
                raise ValueError(f'trace must not be a symlink: {trace}')
            if not trace.exists():
                continue
            for number, line in enumerate(trace.read_text(encoding='utf-8').splitlines(), 1):
                try:
                    record = json.loads(line)
                    for resource in record['resourceSpans']:
                        for scope in resource['scopeSpans']:
                            for span in scope['spans']:
                                attrs = {item['key']: item['value']['stringValue']
                                         for item in span['attributes']}
                                if attrs.get('gen_ai.tool.name') == 'Read' and attrs.get('gen_ai.agent.name') not in ('', 'unknown'):
                                    arguments = json.loads(attrs['gen_ai.tool.arguments'])
                                    path = arguments.get('file_path')
                                    if isinstance(path, str):
                                        loads.add(Path(path).resolve())
                except (KeyError, TypeError, ValueError, AttributeError) as exc:
                    raise ValueError(f'{trace}:{number}: invalid trace: {exc}; {DAMAGED}') from exc
    return loads
