"""Weekly memory review and protected day archival."""

from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
import re

from wuwei import memory, promotion, registry, workspace
from wuwei.notes import parse_note
from wuwei.exits import SYMLINK


def note_findings(root):
    root = Path(root)
    config = workspace.load_config(root)['consolidation']
    notes = root / '.wuwei/memory/notes'
    findings = memory.lint(root)
    active = []
    for path in sorted(notes.glob('*.md')):
        if path.is_symlink():
            raise ValueError(f'note must not be a symlink; {SYMLINK}')
        fields, body = parse_note(path.read_text(encoding='utf-8'))
        if fields['status'] == 'active':
            active.append((path.stem, fields['summary'], body))
    for index, (left, summary, body) in enumerate(active):
        for right, other_summary, other_body in active[index + 1:]:
            ratio = SequenceMatcher(None, (summary + body).casefold(),
                                    (other_summary + other_body).casefold()).ratio()
            if ratio >= config['similarity_threshold']:
                findings.append(f'{left}, {right}: near-duplicate; propose fold with live survivor')
            elif summary.casefold() == other_summary.casefold() and body.casefold() != other_body.casefold():
                findings.append(f'{left}, {right}: potential contradiction; review shared summary')
    charters = root / '.wuwei/charters'
    if charters.is_symlink():
        raise ValueError(f'charters must not be a symlink; {SYMLINK}')
    rules = []
    if charters.is_dir():
        for path in sorted(charters.glob('*.md')):
            if path.is_symlink():
                raise ValueError(f'charter must not be a symlink; {SYMLINK}')
            for line in path.read_text(encoding='utf-8').splitlines():
                if line.startswith('- '):
                    rules.append((path.name, line[2:].strip()))
    for index, (left, rule) in enumerate(rules):
        negative = re.sub(r'^(?:do not|never)\s+', '', rule, flags=re.I)
        positive = re.sub(r'^do\s+', '', rule, flags=re.I)
        for right, other in rules[index + 1:]:
            other_negative = re.sub(r'^(?:do not|never)\s+', '', other, flags=re.I)
            other_positive = re.sub(r'^do\s+', '', other, flags=re.I)
            if ((negative != rule and other_positive != other and
                 negative.casefold() == other_positive.casefold()) or
                (positive != rule and other_negative != other and
                 positive.casefold() == other_negative.casefold())):
                findings.append(f'{left}, {right}: potential contradiction in charter rules')
            elif rule.casefold() == other.casefold():
                findings.append(f'{left}, {right}: duplicate charter rule')
            elif SequenceMatcher(None, rule.casefold(), other.casefold()).ratio() >= config['similarity_threshold']:
                findings.append(f'{left}, {right}: near-duplicate charter rules')
    for slug, loads in promotion.archive_candidates(root):
        finding = f'{slug}: archive candidate ({loads} loads)'
        if finding not in findings:
            findings.append(finding)
    return findings


def archive_days(root):
    """Move expired days through one producer and refresh their summary index."""
    root = Path(root)
    base = root / '.wuwei'
    config = workspace.load_config(root)['consolidation']
    days, archive = base / 'days', base / 'archive'
    if days.is_symlink() or archive.is_symlink() or not days.is_dir():
        raise ValueError(f'day directories must be real directories; {SYMLINK}')
    today = workspace.now().date()
    moves = []
    for source in sorted(days.iterdir()):
        if source.is_symlink():
            raise ValueError(f'day must not be a symlink: {source.name}')
        if not source.is_dir():
            continue
        try:
            dated = date.fromisoformat(source.name)
        except ValueError:
            continue
        if source.name != dated.isoformat() or (today - dated).days <= config['archive_after_days']:
            continue
        target = archive / source.name
        if target.exists() or target.is_symlink():
            raise ValueError(f'archive destination exists: {source.name}')
        moves.append((source, target))
    if not moves:
        return []
    preflight = memory.write_index(root)
    if preflight:
        raise ValueError('; '.join(preflight))
    archive.mkdir(exist_ok=True)
    for source, target in moves:
        source.rename(target)
    findings = memory.write_index(root)
    if findings:
        raise ValueError('; '.join(findings))
    paths = [path.relative_to(base).as_posix() for _, target in moves
             for path in target.rglob('*') if path.is_file()]
    paths.append('memory/index.md')
    vcs = registry.load('vcs', workspace.load_config(root))
    result = vcs.workspace_commit(base, paths, root=root)
    if result.exit:
        raise OSError(result.reason or 'could not commit archived days')
    return [source.name for source, _ in moves]
