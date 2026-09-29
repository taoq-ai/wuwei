"""Day-close evidence for obligations and the retro landing."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re

from wuwei import obligations, registry, verdict, watch, workspace
from wuwei.promotion import safe_path


def _settings(root):
    config = workspace.load_config(root)
    settings = config['retro']
    if not settings['charter_paths']:
        raise ValueError('retro.charter_paths must not be empty')
    for raw in [*settings['charter_paths'], settings['changelog']]:
        path = Path(raw)
        if (path.is_absolute() or '..' in path.parts or raw.startswith(('-', ':'))
                or any(c in raw for c in '*?[]\n\r\0')):
            raise ValueError('retro paths must be literal repository-relative paths')
    return settings, registry.load('vcs', config), str((root / '.wuwei').resolve())


def _tree(vcs, repo, ref, paths, root):
    data = obligations._read(vcs.read_tree, repo, ref, paths, root=root)
    if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                         for k, v in data.items()):
        raise ValueError('invalid committed tree evidence')
    return data


def _notes(root, directory):
    notes = {}
    for row in watch.records(directory / 'events.jsonl'):
        if row['kind'] != 'retro.captured':
            continue
        record = row['payload']
        path = safe_path(root, record['evidence'], label='retro evidence')
        if path.parent != directory / 'retro':
            raise ValueError('retro evidence must belong to today')
        evidence = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(evidence, dict) or
                any(evidence.get(key) != record.get(key) for key in
                    ('agent_id', 'agent_type', 'fields', 'missing', 'invalid')) or
                evidence.get('missing') != [] or evidence.get('invalid') != [] or
                not isinstance(evidence.get('agent_type'), str)):
            raise ValueError('invalid captured retro evidence')
        notes[record['evidence']] = evidence['agent_type'].rsplit(':', 1)[-1]
    return list(notes.values())


def retro(root):
    """Sections, commits, changelog, collected notes, then sentinel parity."""
    findings = []
    try:
        directory = workspace.day_dir(root)
        day = directory.name
        path = directory / 'retro' / (day + '.md')
        try:
            text = verdict.active_text(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return 1, f'OWED: retro/{day}.md does not exist; run the retro session first'
        sections = {}
        current = None
        for line in text.splitlines():
            if line.startswith('## '):
                current = line[3:].strip()
                if current in sections:
                    findings.append(f'OWED: duplicate {current} section')
                sections.setdefault(current, [])
            elif current:
                sections[current].append(line)
        for name in ('Applied', 'Proposed'):
            if name not in sections:
                findings.append(f"OWED: retro lacks '## {name}' section")
        applied_text = '\n'.join(sections.get('Applied', [])).strip()
        paths = sorted(set(re.findall(r'(?<![\w./-])([\w./-]+\.md)\b', applied_text)))
        if 'Applied' in sections and not paths and applied_text.lower() != 'none':
            findings.append('OWED: Applied must list charter paths or exactly none')
        proposal_dir = directory / 'proposals'
        if proposal_dir.is_symlink():
            raise ValueError('proposals directory must not be a symlink')
        if proposal_dir.exists() and any(proposal_dir.glob('*.json')):
            findings.append('OWED: retro proposals await wuwei promote')
        if proposal_dir.exists():
            landed = set()
            for proposal in proposal_dir.glob('*.landed'):
                if proposal.is_symlink():
                    raise ValueError('landed proposal must not be a symlink')
                record = json.loads(proposal.read_text(encoding='utf-8'))
                target = record.get('target')
                if not isinstance(target, str):
                    raise ValueError('invalid landed proposal target')
                landed.add(target)
                if target.startswith('.wuwei/charters/') and target not in paths:
                    findings.append(f'OWED: Applied omits promoted charter {target}')
            for proposal in proposal_dir.glob('*.rejected'):
                if proposal.is_symlink():
                    raise ValueError('rejected proposal must not be a symlink')
                record = json.loads(proposal.read_text(encoding='utf-8'))
                target = record.get('target')
                if not isinstance(target, str):
                    raise ValueError('invalid rejected proposal target')
                if target.startswith('.wuwei/charters/') and target not in landed:
                    findings.append(f'OWED: rejected charter proposal {target} needs a landed revision')
        if paths:
            settings, vcs, repo = _settings(root)
            for path in paths:
                if not any(Path(path) == Path(p) or Path(path).is_relative_to(p)
                           for p in settings['charter_paths']) or '..' in Path(path).parts:
                    raise ValueError(f'Applied path outside retro.charter_paths: {path}')
            local_paths = [str(Path(path).relative_to('.wuwei')) for path in paths]
            changed = obligations._read(vcs.changes_on, repo, day, root=root)
            if not isinstance(changed, list) or any(not isinstance(p, str) for p in changed):
                raise ValueError('invalid changed paths evidence')
            for path in local_paths:
                if path not in changed:
                    findings.append(f'OWED: retro says {path} was amended but no commit today touches it')
            changelog = str(Path(settings['changelog']).relative_to('.wuwei'))
            tree = _tree(vcs, repo, 'HEAD', [*local_paths, changelog], root)
            for path in local_paths:
                if path not in tree:
                    findings.append(f'OWED: applied charter {path} absent from committed HEAD')
            if changelog not in changed:
                findings.append('OWED: no commit today touches the changelog')
            if not re.search(r'^- ' + re.escape(day) + r'(?:\s|$)', tree.get(changelog, ''), re.M):
                findings.append(f'OWED: changelog has no committed line dated {day}')
            integrity = obligations._read(vcs.workspace_changes, repo, root=root)
            if not isinstance(integrity, list) or any(not isinstance(p, str) for p in integrity):
                raise ValueError('invalid workspace history evidence')
            for path in [*local_paths, changelog]:
                if path in integrity:
                    findings.append(f'OWED: {path} has unpromoted changes or history')
        notes = _notes(root, directory)
        if not notes:
            findings.append('OWED: collected retro notes are empty')
        gates = sum(bool(verdict.rows(verdict.active_text(p.read_text(encoding='utf-8')), 'Change'))
                    for p in (directory / 'decisions').glob('[gG][aA][tT][eE]-*.[mM][dD]'))
        sentinels = sum(role.startswith('sentinel-') for role in notes)
        if gates > sentinels:
            findings.append(f'OWED: {gates} verdict files carry a retro note, collected notes have '
                            f'{sentinels} sentinel notes; append the rest')
        return int(bool(findings)), '\n'.join(findings)
    except watch.ERRORS as exc:
        return 2, '\n'.join([*findings, f'retro unmeasured: {exc}'])


def check(root):
    """Recheck all closing conditions, retaining findings even when another read fails."""
    from wuwei import pr_actions
    results = [pr_actions.check(root)]
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            counts = obligations.evaluate(root)
        results.append((counts['exit'], output.getvalue().strip()))
    except watch.ERRORS as exc:
        results.append((2, f'obligations unmeasured: {exc}'))
    results.extend([retro(root), pr_actions.check(root, closing=True)])
    return max(code for code, _ in results), '\n'.join(dict.fromkeys(
        message for code, message in results if code and message))
