"""Validate charter proposals and record their outcomes."""

import json
from pathlib import Path
import re

from wuwei import registry, state, workspace
from wuwei.exits import DAMAGED, SYMLINK

SLUG_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def save_goals(root, text):
    """Validate and commit the owner's complete goals document (the gate approved it)."""
    root = workspace.find_workspace(root)
    target = safe_path(root, '.wuwei/memory/goals.md', label='target')
    if not target.is_file():
        raise OSError('goals target is missing; run bin/wuwei init --upgrade to restore the template')
    from wuwei.goals import parse
    parse(text)
    previous = target.read_text(encoding='utf-8')
    vcs = registry.load('vcs', workspace.load_config(root))
    if text == previous:
        if not (root / '.wuwei/.git').is_dir():
            return False  # no workspace history, so no unrecorded edit to commit
        result = vcs.workspace_changes(root / '.wuwei', root=root)
        if result.exit:
            raise OSError(result.reason)
        if 'memory/goals.md' not in result.data:
            return False
    # The producer writes only after validation and records the exact target.
    workspace.atomic_write(target, text)
    result = vcs.workspace_owner_commit(root / '.wuwei', ['memory/goals.md'], root=root)
    if result.exit:
        workspace.atomic_write(target, previous)
        raise OSError(result.reason)
    return True


def safe_path(root, raw, *, label):
    """Resolve a workspace-relative path without following symlinked components."""
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise ValueError(f'{label} path must be workspace-relative; pass a path relative to the workspace')
    relative = Path(raw)
    if '..' in relative.parts or relative.parts[0] != '.wuwei':
        raise ValueError(f'{label} path must be inside .wuwei; pass a path inside .wuwei')
    path = root / relative
    if any(part.is_symlink() for part in (path, *list(path.parents)[:-len(root.parts)])):
        raise ValueError(f'{label} path must not use a symlink; {SYMLINK}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'{label} path must be inside workspace; pass a path inside the workspace')
    return path


def _target(root, raw):
    path = safe_path(root, raw, label='target')
    if path.parent != root / '.wuwei/charters':
        raise ValueError('target must be a WUWEI charter override; use a path under .wuwei/charters')
    if not SLUG_RE.fullmatch(path.stem) or path.suffix != '.md':
        raise ValueError(f'invalid charter target; {DAMAGED}')
    return path


def _lines(text):
    return {line.strip().casefold() for line in text.splitlines() if line.strip()}


def _ensure_clean(root, target):
    vcs = registry.load('vcs', workspace.load_config(root))
    result = vcs.workspace_changes(root / '.wuwei', root=root)
    if result.exit:
        raise OSError(result.reason)
    if not isinstance(result.data, list) or not all(isinstance(p, str) for p in result.data):
        raise OSError('workspace integrity evidence unreadable; run bin/wuwei doctor, which tests the workspace history')
    if target.relative_to(root / '.wuwei').as_posix() in result.data:
        raise ValueError('target has uncommitted changes in the workspace history; the owner commits or reverts them under .wuwei, then run bin/wuwei promote again')


def _changelog(root):
    return safe_path(root, workspace.load_config(root)['retro']['changelog'], label='changelog')


def _apply(root, proposal):
    raw = proposal.get('target')
    target = _target(root, raw)
    action = proposal.get('action')
    if action not in ('add', 'patch'):
        raise ValueError('action must be add or patch; set the proposal action to one of them')
    reason = proposal.get('reason')
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('reason is required; add a one-line reason')
    evidence = safe_path(root, proposal.get('evidence'), label='evidence')
    if not evidence.is_file():
        raise ValueError('evidence does not exist; pass an existing evidence path')
    if target.exists():
        old = target.read_text(encoding='utf-8')
    else:
        old = (Path(__file__).resolve().parents[2] / 'charters' / target.name).read_text(encoding='utf-8')
    if action != 'add' and not target.is_file():
        raise ValueError('target does not exist; pass an existing target path')
    if action == 'patch' and proposal.get('text') == '':
        return _drop(root, target, old, proposal.get('old_text'))
    text = proposal.get('text', proposal.get('delta'))
    if not isinstance(text, str) or not text.strip():
        raise ValueError('text or delta is required; pass the text or the delta to apply')
    if action == 'add':
        if _lines(text) & _lines(old):
            raise ValueError('duplicate add; use patch')
        updated = old.rstrip('\n') + ('\n' if old else '') + text.rstrip('\n') + '\n'
    else:
        previous = proposal.get('old_text')
        if not isinstance(previous, str) or not previous or old.count(previous) != 1:
            raise ValueError('patch must name one existing old_text rule; pass the exact old_text of one existing rule')
        updated = old.replace(previous, text, 1)
    if len(updated.splitlines()) > 200:
        raise ValueError('target exceeds 200 line cap; split the charter override')
    _ensure_clean(root, target)
    _ensure_clean(root, _changelog(root))
    target.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(target, updated)
    return [target]


def _drop(root, target, old, previous):
    """Remove one whole rule line from a local charter, keeping it in dropped-rules.md."""
    if (not isinstance(previous, str) or not previous.startswith('- ') or not previous.endswith('\n')
            or '\n' in previous[:-1] or old.count(previous) != 1
            or not (old.startswith(previous) or '\n' + previous in old)):
        raise ValueError('drop must name one whole existing rule line; pass the exact old_text of one '
                         'rule line, newline included')
    dropped = root / '.wuwei/memory/archive/dropped-rules.md'
    if dropped.parent.is_symlink() or dropped.is_symlink():
        raise ValueError(f'archive path must not be a symlink; {SYMLINK}')
    _ensure_clean(root, target)
    _ensure_clean(root, _changelog(root))
    prior = dropped.read_text(encoding='utf-8') if dropped.exists() else ''
    dropped.parent.mkdir(exist_ok=True)
    workspace.atomic_write(target, old.replace(previous, '', 1))
    workspace.atomic_write(dropped, prior + f'- {workspace.now().date()} {target.name}: {previous[2:].strip()}\n')
    return [target, dropped]


def land(root, proposal, *, day, run, ledger, name):
    """Apply one proposal (a dict, or a proposal file renamed to its status once logged), log it
    and commit it; returns the ledger record."""
    source = proposal if isinstance(proposal, Path) else None
    try:
        if source is not None:
            proposal = {}
            proposal = json.loads(source.read_text(encoding='utf-8'))
        if not isinstance(proposal, dict):
            raise ValueError(f'proposal must be an object; {DAMAGED}')
        changed = _apply(root, proposal)
        status, reason = 'landed', proposal['reason']
    except (ValueError, TypeError, KeyError) as exc:
        status, reason = 'rejected', str(exc)
    if not isinstance(proposal, dict):
        proposal = {}
    record = {'date': day, 'run_id': run, 'target': proposal.get('target', name),
              'action': proposal.get('action', ''), 'status': status,
              'reason': reason, 'evidence': proposal.get('evidence', '')}
    state.append_jsonl(ledger, record)
    if source is not None:
        source.rename(source.with_suffix(f'.{status}'))
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
    return record


def promote(root=None):
    from uuid import uuid4
    root = workspace.find_workspace() if root is None else Path(root)
    if (root / '.wuwei').is_symlink():
        raise ValueError('.wuwei must not be a symlink')
    day = workspace.now().date().isoformat()
    directory = root / '.wuwei/days' / day / 'proposals'
    if directory.is_symlink():
        raise ValueError(f'proposals directory must not be a symlink; {SYMLINK}')
    if not directory.exists():
        return []
    ledger = root / '.wuwei/memory/ledger.jsonl'
    if ledger.is_symlink() or ledger.parent.is_symlink():
        raise ValueError(f'ledger path must not be a symlink; {SYMLINK}')
    run = uuid4().hex
    records = []
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink():
            raise ValueError(f'proposal must not be a symlink; {SYMLINK}')
        records.append(land(root, path, day=day, run=run, ledger=ledger, name=path.name))
    return records


def last_run(root):
    path = Path(root) / '.wuwei/memory/ledger.jsonl'
    if not path.exists():
        return 'Last promote: none'
    if path.is_symlink():
        raise ValueError(f'ledger must not be a symlink; {SYMLINK}')
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    if not records:
        return 'Last promote: none'
    latest = records[-1]
    selected = [r for r in records if r['run_id'] == latest['run_id']]
    landed = [r['target'] for r in selected if r['status'] == 'landed']
    rejected = [f"{r['target']}: {r['reason']}" for r in selected if r['status'] == 'rejected']
    return (f"Last promote {latest['date']}: landed {len(landed)} ({', '.join(landed)}); "
            f"rejected {len(rejected)} ({', '.join(rejected)})")
