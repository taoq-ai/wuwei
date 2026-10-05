"""Day-close evidence for obligations and the retro landing."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import sys

from wuwei import decision, obligations, registry, state, verdict, watch, workspace
from wuwei.promotion import safe_path
from wuwei.exits import DAMAGED, SYMLINK


def _settings(root):
    config = workspace.load_config(root)
    settings = config['retro']
    if not settings['charter_paths']:
        raise ValueError('retro.charter_paths must not be empty; the owner lists the charter folders the retro may change with bin/wuwei config set retro.charter_paths in a host terminal')
    for raw in [*settings['charter_paths'], settings['changelog']]:
        path = Path(raw)
        if (path.is_absolute() or '..' in path.parts or raw.startswith(('-', ':'))
                or any(c in raw for c in '*?[]\n\r\0')):
            raise ValueError('retro paths must be literal repository-relative paths; the owner sets plain relative paths with bin/wuwei config set in a host terminal')
    return settings, registry.load('vcs', config), str((root / '.wuwei').resolve())


def _tree(vcs, repo, ref, paths, root):
    data = obligations._read(vcs.read_tree, repo, ref, paths, root=root)
    if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                         for k, v in data.items()):
        raise ValueError(f'invalid committed tree evidence; {DAMAGED}')
    return data


def _notes(root, directory):
    notes = {}
    for row in watch.records(directory / 'events.jsonl'):
        if row['kind'] != 'retro.captured':
            continue
        record = row['payload']
        path = safe_path(root, record['evidence'], label='retro evidence')
        if path.parent != directory / 'retro':
            raise ValueError('retro evidence must belong to today; capture it again with the retro session (bin/wuwei retro)')
        evidence = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(evidence, dict) or
                any(evidence.get(key) != record.get(key) for key in
                    ('agent_id', 'agent_type', 'fields', 'missing', 'invalid')) or
                evidence.get('missing') != [] or evidence.get('invalid') != [] or
                not isinstance(evidence.get('agent_type'), str)):
            raise ValueError(f'invalid captured retro evidence; {DAMAGED}')
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
            return 1, f'OWED: retro/{day}.md does not exist; run /wuwei:wuwei-retro to write it'
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
            raise ValueError(f'proposals directory must not be a symlink; {SYMLINK}')
        if proposal_dir.exists() and any(proposal_dir.glob('*.json')):
            findings.append('OWED: retro proposals await wuwei promote')
        if proposal_dir.exists():
            landed = set()
            for proposal in proposal_dir.glob('*.landed'):
                if proposal.is_symlink():
                    raise ValueError(f'landed proposal must not be a symlink; {SYMLINK}')
                record = json.loads(proposal.read_text(encoding='utf-8'))
                target = record.get('target')
                if not isinstance(target, str):
                    raise ValueError(f'invalid landed proposal target; {DAMAGED}')
                landed.add(target)
                if target.startswith('.wuwei/charters/') and target not in paths:
                    findings.append(f'OWED: Applied omits promoted charter {target}')
            for proposal in proposal_dir.glob('*.rejected'):
                if proposal.is_symlink():
                    raise ValueError(f'rejected proposal must not be a symlink; {SYMLINK}')
                record = json.loads(proposal.read_text(encoding='utf-8'))
                target = record.get('target')
                if not isinstance(target, str):
                    raise ValueError(f'invalid rejected proposal target; {DAMAGED}')
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
                raise ValueError(f'invalid changed paths evidence; {DAMAGED}')
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
                raise ValueError(f'invalid workspace history evidence; {DAMAGED}')
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


def unresolved(root, rows, open_items=None, notes=None):
    """Account for approved items, owner decisions and pushed item branches; open item names
    are appended to open_items when given. A parked or carried item whose branch cannot be
    measured is a fact appended to notes, never a gate."""
    findings, code = [], 0
    notes = [] if notes is None else notes

    def unmeasured(label, exc):
        nonlocal code
        code = 2
        findings.append(f'{label} unmeasured: {exc}')

    try:
        data = state.read_state(root)
        config = workspace.load_config(root)
        outcomes = data.get('decision_outcomes', {})
        routes = data.get('decision_routes', {})
        if not isinstance(outcomes, dict) or not isinstance(routes, dict):
            raise ValueError(f'invalid decision ledger; {DAMAGED}')
        prs = {row['pr']: row for row in rows if row['exit'] != 2 and 'pr' in row}
        resolved = {data['pr_dispositions'][ref]['decision'] for ref, row in prs.items()
                    if row.get('disposition') in ('parked', 'carried')}
        dispositions = {}
        directory = workspace.day_dir(root) / 'decisions'
        identifiers = outcomes.keys() | routes.keys()
        try:
            if directory.is_symlink():
                raise ValueError(f'decisions directory must belong to today; {SYMLINK}')
            if directory.exists():
                identifiers |= {p.stem for p in directory.iterdir()
                                if p.name.startswith('D-') and p.suffix == '.md'}
        except watch.ERRORS as exc:
            unmeasured('decisions', exc)
        for identifier in sorted(identifiers):
            try:
                fields, _ = decision.evaluate(decision.today_path(identifier, root).read_text(encoding='utf-8'))
                if identifier in routes or decision.route(fields) == 'owner':
                    if identifier not in resolved and not decision.answered(data, identifier):
                        findings.append(f'{identifier}: pending owner decision: {fields["Question"]}')
                elif identifier in outcomes:
                    record = outcomes[identifier]
                    if (fields['Decided-by'] == record['decided_by'] == 'seat'
                            and record.get('item_disposition') == fields['Outcome']):
                        dispositions[fields['Outcome']] = fields['Context'].partition('Reason: ')[2]
            except watch.ERRORS as exc:
                unmeasured(identifier, exc)
        owned = data['raised_prs'] + data['claimed_prs']
        from wuwei import tracker
        done = ({row['payload'].get('item') for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
                 if row['kind'] == 'tracker.call' and row['payload'].get('action') == 'done'
                 and row['payload'].get('exit') == 0} if tracker.in_force(config) else set())
        for name in data['approved_items']:
            try:
                item = data['items'][name]
                ref = item.get('pr')
                pr = prs.get(ref, {})
                key = next((k for k in (f'parked {name}', f'carried {name}') if k in dispositions), None)
                disposed = (f'{name}: {key.split()[0]}' + (f' ({dispositions[key]})' if dispositions[key] else '')
                            if key else f'{name}: {pr["disposition"]}'
                            if pr.get('disposition') in ('parked', 'carried') else None)
                if pr.get('state') != 'merged' and not disposed:
                    findings.append(f'{name} is still open ({item["status"]}/{item["phase"]}): carry it '
                                    'to tomorrow (recommended), park it, or keep working? '
                                    f'Carry: bin/wuwei plan carry {name}. '
                                    f'Park: bin/wuwei plan park {name} --reason "<why>". '
                                    'Keep working: finish it, then run bin/wuwei close again.')
                    if open_items is not None:
                        open_items.append(name)
                number = tracker.ticket(data, name)
                if tracker.in_force(config) and item['phase'] == 'merged' and number and name not in done:
                    line = f'{name}: ticket {number} is not done: bin/wuwei tracker done {name}'
                    if config['tracker']['strict_close']:
                        findings.append(line)
                    else:
                        print(line, file=sys.stderr)
                tree = item.get('worktree')
                if tree is not None and ref not in owned:
                    if not isinstance(tree, str) or not tree:
                        raise ValueError(f'invalid item worktree; {DAMAGED}')
                    path = (root / tree).resolve()
                    if disposed and not path.is_dir():
                        notes.append(f'{disposed}, unmeasured: worktree missing')
                        continue
                    try:
                        vcs = registry.load('vcs', config)
                        branch = obligations._read(vcs.branch, str(path), root=root)['name']
                        pushed = obligations._read(vcs.pushed_branches, str(path), root=root)
                        if (not isinstance(branch, str) or not branch
                                or not isinstance(pushed, list)
                                or any(not isinstance(b, str) or not b for b in pushed)):
                            raise ValueError(f'invalid pushed branch evidence; {DAMAGED}')
                    except watch.ERRORS as exc:
                        if not disposed:
                            raise
                        notes.append(f'{disposed}, unmeasured: {exc}')
                        continue
                    if branch in pushed:
                        findings.append(f'{name}: pushed branch {branch} has no raised or claimed PR')
            except watch.ERRORS as exc:
                unmeasured(f'item {name}', exc)
    except watch.ERRORS as exc:
        unmeasured('day work', exc)
    return max(code, int(bool(findings))), '\n'.join(findings)


def check(root):
    """Recheck all closing conditions, retaining findings even when another read fails."""
    from wuwei import pr_actions
    _, rows = pr_actions.evaluate(root)
    results = [pr_actions.check(root, rows=rows), unresolved(root, rows)]
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            counts = obligations.evaluate(root)
        results.append((counts['exit'], output.getvalue().strip()))
    except watch.ERRORS as exc:
        results.append((2, f'obligations unmeasured: {exc}'))
    from wuwei import docs
    results.extend([docs.close(root), retro(root), pr_actions.check(root, closing=True, rows=rows)])
    return max(code for code, _ in results), '\n'.join(dict.fromkeys(
        message for code, message in results if code and message))
