"""Weekly memory review and protected day archival."""

from datetime import date, timedelta
from difflib import SequenceMatcher
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

from wuwei import memory, promotion, registry, workspace
from wuwei.notes import parse_note
from wuwei.exits import DAMAGED, SYMLINK


UNREFERENCED_DAYS = 60


def _contradicts(rule, other):
    """One says do X and the other says do not (or never) X."""
    negative = re.sub(r'^(?:do not|never)\s+', '', rule, flags=re.I)
    positive = re.sub(r'^do\s+', '', rule, flags=re.I)
    other_negative = re.sub(r'^(?:do not|never)\s+', '', other, flags=re.I)
    other_positive = re.sub(r'^do\s+', '', other, flags=re.I)
    return ((negative != rule and other_positive != other and
             negative.casefold() == other_positive.casefold()) or
            (positive != rule and other_negative != other and
             positive.casefold() == other_negative.casefold()))


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
        for right, other in rules[index + 1:]:
            if _contradicts(rule, other):
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


def day_records(root, day):
    """{relative name: text} for one date from days/, a legacy archive/<date>/ or its tarball."""
    base = Path(root) / '.wuwei'
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError(f'invalid date: {day}')
    for parent in ('days', 'archive', f'archive/{day[:4]}'):
        if (base / parent).is_symlink():
            raise ValueError(f'{parent} must not be a symlink; {SYMLINK}')
    for source in (base / 'days' / day, base / 'archive' / day):
        if source.is_symlink():
            raise ValueError(f'day must not be a symlink: {day}')
        if source.is_dir():
            records = {}
            for path in sorted(source.rglob('*')):
                if path.is_symlink():
                    raise ValueError(f'day record must not be a symlink: {path.relative_to(base)}')
                if path.is_file():
                    records[path.relative_to(source).as_posix()] = path.read_text(encoding='utf-8')
            return records
    target = base / 'archive' / day[:4] / f'{day}.tar.gz'
    if target.is_symlink():
        raise ValueError(f'archive must not be a symlink: {day}')
    if not target.is_file():
        return None
    records = {}
    try:
        with tarfile.open(target, 'r:gz') as tar:
            for member in tar.getmembers():
                parts = PurePosixPath(member.name).parts
                if (member.name.startswith('/') or '..' in parts or not parts or parts[0] != day
                        or not (member.isdir() or (member.isfile() and len(parts) > 1))):
                    raise ValueError(f'unsafe archive member in {day}: {member.name}')
                if member.isfile():
                    records['/'.join(parts[1:])] = tar.extractfile(member).read().decode('utf-8')
    except (tarfile.TarError, EOFError, UnicodeError) as exc:
        raise ValueError(f'unreadable archive {day}: {exc}') from exc
    return records


def expired(root):
    """Raw days older than consolidation.archive_after_days, then every legacy archive/<date>/."""
    base = Path(root) / '.wuwei'
    window = workspace.load_config(root)['consolidation']['archive_after_days']
    today = workspace.now().date()
    found = []
    for parent in (base / 'days', base / 'archive'):
        if parent.is_symlink():
            raise ValueError(f'day directories must be real directories; {SYMLINK}')
        for source in sorted(parent.iterdir()) if parent.is_dir() else ():
            if source.is_symlink():
                raise ValueError(f'day must not be a symlink: {source.name}')
            try:
                dated = date.fromisoformat(source.name)
            except ValueError:
                continue
            if (source.is_dir() and source.name == dated.isoformat()
                    and (parent.name == 'archive' or (today - dated).days > window)):
                found.append(source)
    return found


def archive_days(root):
    """Pack expired days into archive/<year>/<date>.tar.gz through one producer."""
    root = Path(root)
    base = root / '.wuwei'
    days, archive = base / 'days', base / 'archive'
    if days.is_symlink() or archive.is_symlink() or not days.is_dir():
        raise ValueError(f'day directories must be real directories; {SYMLINK}')
    moves = []
    for source in expired(root):
        target = archive / source.name[:4] / f'{source.name}.tar.gz'
        if target.exists() or target.is_symlink() or target.parent.is_symlink():
            raise ValueError(f'archive destination exists: {source.name}')
        if any(path.is_symlink() for path in source.rglob('*')):
            raise ValueError(f'day contains a symlink: {source.name}')
        moves.append((source, target))
    if not moves:
        return []
    preflight = memory.write_index(root)
    if preflight:
        raise ValueError('; '.join(preflight))
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        files = {f'{source.name}/{path.relative_to(source).as_posix()}': path.read_bytes()
                 for path in source.rglob('*') if path.is_file()}
        try:
            with tarfile.open(target, 'x:gz') as tar:
                tar.add(source, arcname=source.name)
            with tarfile.open(target, 'r:gz') as tar:
                packed = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
            if packed != files:
                raise ValueError(f'archive does not match its day: {source.name}')
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        shutil.rmtree(source)
    findings = memory.write_index(root)
    if findings:
        raise ValueError('; '.join(findings))
    from wuwei import digest
    periods = {}
    for source, _ in moves:
        for kind in ('week', 'month'):
            periods.setdefault(digest.period(date.fromisoformat(source.name), kind)[0],
                               (date.fromisoformat(source.name), kind))
    written = [digest.write(root, day, kind) for day, kind in periods.values()]
    paths = [path.relative_to(base).as_posix()
             for path in [*(target for _, target in moves), *filter(None, written)]]
    paths.append('memory/index.md')
    vcs = registry.load('vcs', workspace.load_config(root))
    result = vcs.workspace_commit(base, paths, root=root)
    if result.exit:
        raise OSError(result.reason or 'could not commit archived days; retry with bin/wuwei consolidate; if it repeats, run bin/wuwei doctor')
    return [source.name for source, _ in moves]


def forget_proposals(root):
    """Forgetting proposals (design 5.14): unreferenced notes, duplicate notes, superseded and
    contradicted local charter rules. Only WUWEI-authored files are targets."""
    from wuwei import decision
    from wuwei.notes import OWNER_NOTES
    root = Path(root)
    base = root / '.wuwei'
    config = workspace.load_config(root)
    threshold = config['consolidation']['similarity_threshold']
    today = workspace.now().date()
    since = today - timedelta(days=UNREFERENCED_DAYS)
    proposals = []
    notes = []
    for path in sorted((base / 'memory/notes').glob('*.md')):
        if path.is_symlink():
            raise ValueError(f'note must not be a symlink; {SYMLINK}')
        fields, body = parse_note(path.read_text(encoding='utf-8'))
        if fields['status'] == 'active' and path.stem not in OWNER_NOTES:
            created = (date.fromisoformat(fields['created']) if 'created' in fields
                       else date.fromtimestamp(path.stat().st_mtime))
            notes.append((path, fields['summary'] + body, created))
    texts = []
    for offset in range(UNREFERENCED_DAYS + 1):
        records = day_records(root, (today - timedelta(days=offset)).isoformat()) or {}
        texts += [text for name, text in records.items()
                  if name.split('/')[0] in ('briefs', 'decisions', 'retro')]
    probation = config['memory']['probation_days']
    for path, _, created in notes:
        slug = path.stem
        named = re.compile(r'(?<![\w-])' + re.escape(slug) + r'(?![\w-])')
        if ((today - created).days > UNREFERENCED_DAYS
                and promotion._working_days(created, today) >= probation
                and not any(named.search(text) for text in texts)):
            proposals.append({'kind': 'unreferenced', 'action': 'archive',
                              'target': f'.wuwei/memory/notes/{path.name}',
                              'evidence': f'{slug}: named by no brief, decision or retro since {since} '
                                          f'({UNREFERENCED_DAYS} days)'})
    loads = promotion.adherence_counts(root)['note_loads'] if len(notes) > 1 else {}
    for index, (left, text, _) in enumerate(notes):
        for right, other, _ in notes[index + 1:]:
            ratio = SequenceMatcher(None, text.casefold(), other.casefold()).ratio()
            if ratio < threshold:
                continue
            survivor, target = ((right, left) if loads.get(right.stem, 0) > loads.get(left.stem, 0)
                                else (left, right))
            proposals.append({'kind': 'duplicate', 'action': 'fold',
                              'target': f'.wuwei/memory/notes/{target.name}',
                              'survivor': f'.wuwei/memory/notes/{survivor.name}',
                              'evidence': f'{left.stem}, {right.stem}: near-duplicate notes ({ratio:.2f}); '
                                          f'{survivor.stem} has {loads.get(survivor.stem, 0)} loads, '
                                          f'{target.stem} {loads.get(target.stem, 0)}'})
    charters = base / 'charters'
    rules = []
    for path in sorted(charters.glob('*.md')) if charters.is_dir() and not charters.is_symlink() else ():
        if path.is_symlink():
            raise ValueError(f'charter must not be a symlink; {SYMLINK}')
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        rules += [(path, number, line) for number, line in enumerate(lines, 1) if line.startswith('- ')]
    dropped = set()
    for index, (path, number, line) in enumerate(rules):
        for other_path, other_number, other in rules[index + 1:]:
            ratio = SequenceMatcher(None, line[2:].strip().casefold(), other[2:].strip().casefold()).ratio()
            if other_path == path and ratio >= threshold and (path, line) not in dropped:
                dropped.add((path, line))
                proposals.append({'kind': 'superseded', 'action': 'drop',
                                  'target': f'.wuwei/charters/{path.name}', 'old_text': line,
                                  'evidence': f'{path.name} line {number} is superseded by line '
                                              f'{other_number} ({ratio:.2f})'})
    for record in sorted((base / 'days').glob('*/decisions/D-*.md')):
        if record.is_symlink():
            continue
        try:
            fields, _ = decision.evaluate(record.read_text(encoding='utf-8'))
            options = dict(decision.table(fields['Options'], ['Option', 'Description'], 'Options'))
        except (ValueError, UnicodeError):
            continue  # decision lint owns invalid records
        chosen = fields['Outcome'].strip()
        if chosen not in options:
            continue
        for path, _, line in rules:
            if (path, line) not in dropped and _contradicts(line[2:].strip().rstrip('.'),
                                                            options[chosen].strip().rstrip('.')):
                dropped.add((path, line))
                proposals.append({'kind': 'contradicted', 'action': 'drop',
                                  'target': f'.wuwei/charters/{path.name}', 'old_text': line,
                                  'evidence': f'{record.stem} on {record.parent.parent.name} chose '
                                              f'{chosen}: {options[chosen]}'})
    return proposals


def _key(row):
    return row['kind'], row['target'], row.get('old_text') or row.get('survivor')


def read_forget(root):
    """memory/forget.json rows keyed by F-n; missing is empty, anything malformed is a ValueError."""
    path = Path(root) / '.wuwei/memory/forget.json'
    if path.is_symlink():
        raise ValueError(f'memory/forget.json must not be a symlink; {SYMLINK}')
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows, dict) or not all(
            isinstance(row, dict) and row.get('id') == ident and re.fullmatch(r'F-[1-9]\d*', ident)
            and row.get('status') in ('pending', 'applied', 'declined')
            and all(isinstance(row.get(key), str) for key in ('kind', 'action', 'target', 'evidence'))
            for ident, row in rows.items()):
        raise ValueError('memory/forget.json: expected F-n rows with kind, action, target, evidence and '
                         f'status; {DAMAGED}')
    return rows


def write_forget(root, rows):
    workspace.atomic_write(Path(root) / '.wuwei/memory/forget.json',
                           json.dumps(rows, indent=2, sort_keys=True) + '\n', mode=0o644)


def merge_proposals(root, proposals):
    """Add new proposals as pending F-n rows; a known key in any status blocks a repeat. Returns
    the pending rows."""
    rows = read_forget(root)
    known = {_key(row) for row in rows.values()}
    number = max((int(ident[2:]) for ident in rows), default=0)
    changed = False
    for proposal in proposals:
        if _key(proposal) in known:
            continue
        number += 1
        ident = f'F-{number}'
        rows[ident] = {**proposal, 'id': ident, 'status': 'pending',
                       'created': workspace.now().date().isoformat()}
        known.add(_key(proposal))
        changed = True
    if changed:
        write_forget(root, rows)
    return sorted((row for row in rows.values() if row['status'] == 'pending'), key=lambda row: int(row['id'][2:]))


def forget(root, ident, label, confirm=None):
    """The owner's answer to one F-n: keep declines it for good; apply asks y/N on the host
    terminal and lands it through promotion.land. Returns the updated row."""
    from hashlib import sha256
    from uuid import uuid4
    from wuwei import integrity, state
    root = Path(root)
    rows = read_forget(root)
    row = rows.get(ident)
    if row is None or row['status'] != 'pending' or label not in ('apply', 'keep'):
        raise ValueError(f'{ident}: no pending forgetting proposal to {label}; '
                         'bin/wuwei memory status counts the pending ones')
    if label == 'keep':
        row['status'] = 'declined'
        write_forget(root, rows)
        return row
    fingerprint = sha256(json.dumps(row, sort_keys=True).encode('utf-8')).hexdigest()
    prompt = f'{ident}: {row["action"]} {row["target"]}: {row["evidence"]}'
    if not (confirm or integrity._host_confirm)(fingerprint, prompt=prompt):
        raise PermissionError(f'{ident}: not confirmed, so nothing changed; rerun bin/wuwei memory forget '
                              f'{ident} apply and answer y')
    drop = row['action'] == 'drop'
    proposal = {'target': row['target'], 'action': 'patch' if drop else row['action'],
                'reason': row['evidence'], 'evidence': '.wuwei/memory/forget.json',
                **({'text': '', 'old_text': row.get('old_text')} if drop else {}),
                **({'survivor': row['survivor']} if 'survivor' in row else {})}
    ledger = root / '.wuwei/memory/ledger.jsonl'
    if ledger.is_symlink():
        raise ValueError(f'ledger path must not be a symlink; {SYMLINK}')
    record = promotion.land(root, proposal, day=workspace.now().date().isoformat(), run=uuid4().hex,
                            ledger=ledger, name=ident)
    if record['status'] != 'landed':
        raise ValueError(f'{ident}: {record["reason"]}')
    archive = 'memory/archive/' + ('dropped-rules.md' if drop else Path(row['target']).name)
    state.append_event('memory.folded', {'id': ident, 'kind': row['kind'], 'action': row['action'],
                                         'target': row['target'], 'archive': archive}, root)
    row['status'] = 'applied'
    write_forget(root, rows)
    memory.export(root)
    return row
