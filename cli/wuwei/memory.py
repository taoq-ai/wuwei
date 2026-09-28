"""Generated memory index and session payload."""

from datetime import date
import json
from pathlib import Path

from wuwei import state, workspace
from wuwei.notes import SLUG_RE, parse_note


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
        raise ValueError('memory notes directory must be inside the workspace and not a symlink')
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
                raise ValueError('invalid slug')
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


def session_payload(root=None):
    """Return payload text, UTF-8 byte count and estimated token count."""
    root = workspace.find_workspace() if root is None else Path(root)
    memory = root / '.wuwei/memory'
    spine = (memory / 'spine.md').read_text(encoding='utf-8')
    index = (memory / 'index.md').read_text(encoding='utf-8')
    state_text = json.dumps(state.read_state(root), ensure_ascii=False, sort_keys=True)
    from wuwei.promotion import last_run
    promote_line = last_run(root)
    content = (f'Spine:\n{spine.rstrip()}\n\nIndex:\n{index.rstrip()}\n\n'
               f'Today state:\n{state_text}\n{promote_line}\n')
    return content, len(content.encode('utf-8')), estimated_tokens(content)
