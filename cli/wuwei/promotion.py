"""Validate memory proposals and record their outcomes."""

from datetime import date, timedelta
import json
from pathlib import Path
import shutil
from uuid import uuid4

from wuwei import registry, state, workspace
from wuwei.notes import OWNER_NOTES, SLUG_RE, parse_note


def owner_edit(root, name, text):
    """Validate and promote an owner's complete goals or voice document."""
    root = workspace.find_workspace(root)
    if name not in ('goals', 'voice'):
        raise ValueError('unknown owner memory target')
    target = safe_path(root, f'.wuwei/memory/{name}.md', label='target')
    if not target.is_file():
        raise OSError(f'{name} target is missing')
    if name == 'goals':
        from wuwei.goals import parse
        parse(text)
    else:
        from wuwei.voice import parse_profile
        parse_profile(text)
    previous = target.read_text(encoding='utf-8')
    vcs = registry.load('vcs', workspace.load_config(root))
    if text == previous:
        result = vcs.workspace_changes(root / '.wuwei', root=root)
        if result.exit:
            raise OSError(result.reason)
        if f'memory/{name}.md' not in result.data:
            return False
    # The producer writes only after validation and records the exact target.
    workspace.atomic_write(target, text)
    result = vcs.workspace_owner_commit(root / '.wuwei', [f'memory/{name}.md'], root=root)
    if result.exit:
        workspace.atomic_write(target, previous)
        raise OSError(result.reason)
    return True


def safe_path(root, raw, *, label):
    """Resolve a workspace-relative path without following symlinked components."""
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise ValueError(f'{label} path must be workspace-relative')
    relative = Path(raw)
    if '..' in relative.parts or relative.parts[0] != '.wuwei':
        raise ValueError(f'{label} path must be inside .wuwei')
    path = root / relative
    if any(part.is_symlink() for part in (path, *list(path.parents)[:-len(root.parts)])):
        raise ValueError(f'{label} path must not use a symlink')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'{label} path must be inside workspace')
    return path


def _target(root, raw):
    path = safe_path(root, raw, label='target')
    if path.parent == root / '.wuwei/charters':
        if not SLUG_RE.fullmatch(path.stem) or path.suffix != '.md':
            raise ValueError('invalid charter target')
    elif path.parent == root / '.wuwei/memory/notes':
        if path.stem in OWNER_NOTES:
            raise ValueError('baseline is maintained by the owner outside agent tools')
        if not SLUG_RE.fullmatch(path.stem) or path.suffix != '.md':
            raise ValueError('invalid note target')
    elif path == root / '.wuwei/memory/voice.md':
        pass
    else:
        raise ValueError('target must be a WUWEI charter override, note or voice profile')
    return path


def _lines(text):
    return {line.strip().casefold() for line in text.splitlines() if line.strip()}


def _working_days(created, today):
    return sum((created + timedelta(days=i)).weekday() < 5
               for i in range(1, max(0, (today - created).days) + 1))


def _ensure_clean(root, target):
    vcs = registry.load('vcs', workspace.load_config(root))
    result = vcs.workspace_changes(root / '.wuwei', root=root)
    if result.exit:
        raise OSError(result.reason)
    if not isinstance(result.data, list) or not all(isinstance(p, str) for p in result.data):
        raise OSError('workspace integrity evidence unreadable')
    if target.relative_to(root / '.wuwei').as_posix() in result.data:
        raise ValueError('target has unpromoted changes; owner must review workspace history')


def _changelog(root):
    return safe_path(root, workspace.load_config(root)['retro']['changelog'], label='changelog')


def _snapshot(root):
    """Keep pre-fold memory and charters under protected workspace history."""
    base = root / '.wuwei'
    target = base / 'memory/snapshots' / uuid4().hex
    for name in ('memory', 'charters'):
        source = base / name
        if source.is_symlink() or not source.is_dir():
            raise ValueError(f'{name} must be a real directory before folding')
        if any(path.is_symlink() for path in source.rglob('*')):
            raise ValueError(f'{name} contains a symlink')
    if target.parent.is_symlink():
        raise ValueError('snapshot directory must not be a symlink')
    target.mkdir(parents=True)
    shutil.copytree(base / 'memory', target / 'memory',
                    ignore=shutil.ignore_patterns('snapshots'))
    shutil.copytree(base / 'charters', target / 'charters')
    return [path for path in target.rglob('*') if path.is_file()]


def _apply(root, proposal):
    raw = proposal.get('target')
    target = _target(root, raw)
    action = proposal.get('action')
    if action not in ('add', 'patch', 'fold', 'archive'):
        raise ValueError('action must be add, patch, fold or archive')
    reason = proposal.get('reason')
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('reason is required')
    evidence = safe_path(root, proposal.get('evidence'), label='evidence')
    if not evidence.is_file():
        raise ValueError('evidence does not exist')
    if target.parent == root / '.wuwei/memory/notes' and action == 'add':
        raise ValueError('new notes require wuwei note add')
    if target.exists():
        old = target.read_text(encoding='utf-8')
    elif target.parent == root / '.wuwei/charters':
        old = (Path(__file__).resolve().parents[2] / 'charters' / target.name).read_text(encoding='utf-8')
    else:
        old = ''
    if action != 'add' and not target.is_file():
        raise ValueError('target does not exist')
    if action in ('add', 'patch'):
        text = proposal.get('text', proposal.get('delta'))
        if not isinstance(text, str) or not text.strip():
            raise ValueError('text or delta is required')
        if action == 'add':
            if _lines(text) & _lines(old):
                raise ValueError('duplicate add; use patch')
            updated = old.rstrip('\n') + ('\n' if old else '') + text.rstrip('\n') + '\n'
        else:
            previous = proposal.get('old_text')
            if not isinstance(previous, str) or not previous or old.count(previous) != 1:
                raise ValueError('patch must name one existing old_text rule')
            updated = old.replace(previous, text, 1)
        if len(updated.splitlines()) > 200:
            raise ValueError('target exceeds 200 line cap')
        if target.parent == root / '.wuwei/memory/notes':
            parse_note(updated)
        if target == root / '.wuwei/memory/voice.md':
            from wuwei.voice import parse_profile
            parse_profile(updated)
        _ensure_clean(root, target)
        if target.parent == root / '.wuwei/charters':
            _ensure_clean(root, _changelog(root))
        target.parent.mkdir(parents=True, exist_ok=True)
        workspace.atomic_write(target, updated)
    else:
        if target.parent == root / '.wuwei/charters':
            raise ValueError('only notes can be archived or folded')
        fields, _ = parse_note(old)
        if fields['status'] != 'active':
            raise ValueError('target is not active')
        created = (date.fromisoformat(fields['created']) if 'created' in fields
                   else date.fromtimestamp(target.stat().st_mtime))
        probation = workspace.load_config(root)['memory']['probation_days']
        if _working_days(created, workspace.now().date()) < probation:
            raise ValueError('note is in probation')
        if action == 'fold':
            survivor = _target(root, proposal.get('survivor'))
            if survivor == target or survivor.parent != target.parent or not survivor.is_file():
                raise ValueError('fold requires a live note survivor')
            survivor_text = survivor.read_text(encoding='utf-8')
            if parse_note(survivor_text)[0]['status'] != 'active':
                raise ValueError('fold requires a live note survivor')
            _, retired_body = parse_note(old)
            _, survivor_body = parse_note(survivor_text)
            merged = survivor_text
            if retired_body.strip() and retired_body.strip() not in survivor_body:
                merged = (survivor_text.rstrip() + f'\n\n## Folded from {target.name}\n'
                          + retired_body.strip() + '\n')
            if len(merged.splitlines()) > workspace.load_config(root)['memory']['note_line_cap']:
                raise ValueError('folded survivor exceeds note line cap')
            _ensure_clean(root, survivor)
        from wuwei import memory
        findings = memory.write_index(root)
        if findings:
            raise ValueError('; '.join(findings))
        archive = root / '.wuwei/memory/archive'
        if archive.is_symlink():
            raise ValueError('archive path must not be a symlink')
        archive.mkdir(exist_ok=True)
        destination = archive / target.name
        if destination.exists() or destination.is_symlink():
            raise ValueError('archive destination already exists')
        # A move preserves the complete original note and does not delete its content.
        _ensure_clean(root, target)
        index = root / '.wuwei/memory/index.md'
        snapshot = _snapshot(root) if action == 'fold' else []
        if action == 'fold' and merged != survivor_text:
            workspace.atomic_write(survivor, merged)
        target.rename(destination)
        findings = memory.write_index(root)
        if findings:
            raise ValueError('; '.join(findings))
        return [target, destination, index, *([survivor] if action == 'fold' else []), *snapshot]
    return [target]


def promote(root=None):
    root = workspace.find_workspace() if root is None else Path(root)
    if (root / '.wuwei').is_symlink():
        raise ValueError('.wuwei must not be a symlink')
    day = workspace.now().date().isoformat()
    directory = root / '.wuwei/days' / day / 'proposals'
    if directory.is_symlink():
        raise ValueError('proposals directory must not be a symlink')
    if not directory.exists():
        return []
    ledger = root / '.wuwei/memory/ledger.jsonl'
    if ledger.is_symlink() or ledger.parent.is_symlink():
        raise ValueError('ledger path must not be a symlink')
    run = uuid4().hex
    records = []
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink():
            raise ValueError('proposal must not be a symlink')
        proposal = {}
        try:
            proposal = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(proposal, dict):
                raise ValueError('proposal must be an object')
            changed = _apply(root, proposal)
            status, reason = 'landed', proposal['reason']
        except (ValueError, TypeError, KeyError) as exc:
            status, reason = 'rejected', str(exc)
        if not isinstance(proposal, dict):
            proposal = {}
        record = {'date': day, 'run_id': run, 'target': proposal.get('target', path.name),
                  'action': proposal.get('action', ''), 'status': status,
                  'reason': reason, 'evidence': proposal.get('evidence', '')}
        state.append_jsonl(ledger, record)
        path.rename(path.with_suffix(f'.{status}'))
        records.append(record)
        if status == 'landed':
            vcs = registry.load('vcs', workspace.load_config(root))
            charter = [p for p in changed if p.parent == root / '.wuwei/charters']
            if charter:
                changelog = _changelog(root)
                prior = changelog.read_text(encoding='utf-8') if changelog.exists() else ''
                line = f"- {day} {', '.join(p.name for p in charter)}: {reason}\n"
                changelog.parent.mkdir(parents=True, exist_ok=True)
                workspace.atomic_write(changelog, prior + line)
                changed.append(changelog)
            paths = [p.relative_to(root / '.wuwei').as_posix() for p in [*changed, ledger]]
            result = vcs.workspace_commit(root / '.wuwei', paths, root=root)
            if result.exit:
                raise OSError(result.reason)
    return records


def last_run(root):
    path = Path(root) / '.wuwei/memory/ledger.jsonl'
    if not path.exists():
        return 'Last promote: none'
    if path.is_symlink():
        raise ValueError('ledger must not be a symlink')
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    if not records:
        return 'Last promote: none'
    latest = records[-1]
    selected = [r for r in records if r['run_id'] == latest['run_id']]
    landed = [r['target'] for r in selected if r['status'] == 'landed']
    rejected = [f"{r['target']}: {r['reason']}" for r in selected if r['status'] == 'rejected']
    return (f"Last promote {latest['date']}: landed {len(landed)} ({', '.join(landed)}); "
            f"rejected {len(rejected)} ({', '.join(rejected)})")


def _load_counts(root):
    counts = {}
    for path in sorted((Path(root) / '.wuwei/days').glob('*/traces.jsonl')):
        if path.is_symlink():
            raise ValueError('trace must not be a symlink')
        for line in path.read_text(encoding='utf-8').splitlines():
            batch = json.loads(line)
            for resource in batch['resourceSpans']:
                for scope in resource['scopeSpans']:
                    for span in scope['spans']:
                        attrs = {a['key']: a['value']['stringValue'] for a in span['attributes']}
                        if attrs.get('gen_ai.tool.name') != 'Read':
                            continue
                        args = json.loads(attrs['gen_ai.tool.arguments'])
                        file = Path(args.get('file_path', ''))
                        if not file.is_absolute():
                            file = Path(root) / file
                        slug = file.stem
                        if (file.parent == Path(root) / '.wuwei/memory/notes'
                                and file.suffix == '.md' and SLUG_RE.fullmatch(slug)):
                            counts[slug] = counts.get(slug, 0) + 1
    return counts


def adherence_counts(root=None):
    """Count note loads and recorded guard refusals from dedicated producer logs."""
    root = workspace.find_workspace() if root is None else Path(root)
    refusals = {}
    for path in sorted((root / '.wuwei/days').glob('*/events.jsonl')):
        if path.is_symlink():
            raise ValueError('events must not be a symlink')
        for line in path.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            if event.get('kind') == 'hook.refusal':
                reason = event['payload']['reason']
                refusals[reason] = refusals.get(reason, 0) + 1
    return {'note_loads': _load_counts(root), 'guard_refusals': refusals}


def archive_candidates(root=None):
    root = workspace.find_workspace() if root is None else Path(root)
    config = workspace.load_config(root)['memory']
    loads = adherence_counts(root)['note_loads']
    today = workspace.now().date()
    active = []
    for path in sorted((root / '.wuwei/memory/notes').glob('*.md')):
        if path.is_symlink():
            raise ValueError('note must not be a symlink')
        fields, _ = parse_note(path.read_text(encoding='utf-8'))
        if fields['status'] != 'active':
            continue
        created = date.fromisoformat(fields['created']) if 'created' in fields else date.fromtimestamp(path.stat().st_mtime)
        working = _working_days(created, today)
        active.append((path.stem, loads.get(path.stem, 0), working))
    eligible = sorted((item for item in active if item[2] >= config['probation_days']),
                      key=lambda x: (x[1] / max(x[2], 1), x[0]))
    overflow = max(0, len(active) - config['max_notes'])
    return [(slug, count) for index, (slug, count, _) in enumerate(eligible)
            if count == 0 or index < overflow]
