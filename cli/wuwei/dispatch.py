"""Planner decisions from recorded seats and gate verdicts."""

from pathlib import Path
import re

from wuwei import brief, state, verdict, workspace


ROLES = ('arch', 'quality', 'security')


class Refused(ValueError):
    """A measured planner refusal."""


def _item(data, item):
    if not data['gate_approved'] or item not in data['approved_items'] or item not in data['items']:
        raise Refused('item is not approved at the morning gate')
    return data['items'][item]


def _record(data, item, role, round_name):
    return data['gate_verdicts'].get(f'{item}:{role}:{round_name}')


def next_step(item, root=None):
    """Return the next planner action without launching a seat."""
    from wuwei import steward
    steward.review(root)
    data = state.read_state(root)
    row = _item(data, item)
    notes = steward.pending(data, item)
    if notes:
        raise Refused(f'steward note {notes[0]["id"]} requires planner acknowledgement')
    phase = row['phase']
    if phase not in ('gate', 'fix', 'delta'):
        raise Refused(f'item phase {phase} is not dispatchable')
    if phase in ('gate', 'delta'):
        try:
            brief.gate_ready(data, item)
        except brief.Refused as exc:
            raise Refused(str(exc)) from exc
        if not any(seat['item'] == item and seat['role'] == 'builder'
                   and seat['status'] == 'stopped' for seat in brief.seats(data).values()):
            raise Refused('builder must stand down before gates')
    if phase == 'fix':
        if any(_record(data, item, role, 'delta') is not None for role in ROLES):
            return {'action': 'escalate', 'reason': 'fix round already used'}
        if any(_record(data, item, role, 'initial') is None for role in ROLES):
            raise Refused('fix phase requires all initial verdicts')
        roles = [role for role in ROLES
                 if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        return {'action': 'fix', 'roles': roles}
    if phase == 'gate':
        roles = list(ROLES)
        round_name = 'initial'
    else:
        if any(_record(data, item, role, 'initial') is None for role in ROLES):
            raise Refused('delta phase requires all initial verdicts')
        roles = [role for role in ROLES
                 if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        round_name = 'delta'
    if any(_record(data, item, role, round_name) and
           _record(data, item, role, round_name)['verdict'] in ('PARK', 'ESCALATE')
           for role in roles):
        return {'action': 'escalate', 'reason': 'gate parked or escalated'}
    missing = [role for role in roles if _record(data, item, role, round_name) is None]
    if missing:
        return {'action': 'gates', 'roles': missing}
    results = [_record(data, item, role, round_name) for role in roles]
    if any(result['verdict'] in ('PARK', 'ESCALATE') for result in results):
        return {'action': 'escalate', 'reason': 'gate parked or escalated'}
    if phase == 'gate':
        failures = [role for role in roles if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        return {'action': 'fix', 'roles': failures} if failures else {'action': 'raise', 'notes': []}
    if any(result['blocks'] for result in results):
        return {'action': 'escalate', 'reason': 'blocking finding remains after delta'}
    notes = [note for result in results for note in result['notes']]
    return {'action': 'raise', 'notes': notes}


def receive(item, role, name, round_name='initial', root=None):
    """Lint and record one stopped sentinel's verdict file."""
    root = workspace.find_workspace() if root is None else Path(root)
    data = state.read_state(root)
    _item(data, item)
    if role not in ROLES or round_name not in ('initial', 'delta'):
        raise Refused('unknown gate role or round')
    if data['items'][item]['phase'] != ('gate' if round_name == 'initial' else 'delta'):
        raise Refused('gate round does not match item phase')
    if round_name == 'delta':
        first = _record(data, item, role, 'initial')
        if first is None or first['verdict'] != 'FIX':
            raise Refused('gate did not need a delta')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise Refused('unsafe seat name')
    seat = brief.seats(data).get(name)
    if not seat or seat['item'] != item or seat['role'] != 'sentinel-' + role or seat['status'] != 'stopped':
        raise Refused('matching sentinel must stand down before receive')
    key = f'{item}:{role}:{round_name}'
    if key in data['gate_verdicts']:
        raise Refused('gate already received')
    directory = workspace.day_dir(root)
    path = directory / 'decisions' / f'gate-{name}.md'
    if path.is_symlink():
        raise Refused('gate verdict must be a regular day file')
    code, message = verdict.lint_file(path, role='sentinel-' + role, root=root)
    if code == 2:
        raise OSError(message)
    if code:
        raise Refused(message)
    text = verdict.active_text(path.read_text(encoding='utf-8'))
    head = verdict.rows(text, 'Head')[0].strip()
    brief_path = root / seat['brief']
    if brief_path.resolve() != directory / 'briefs' / f'{name}.md':
        raise Refused('seat brief path does not match gate name')
    brief_text = brief_path.read_text(encoding='utf-8')
    if f'HEAD: {head}' not in brief_text and f'Head: {head}' not in brief_text:
        raise Refused('verdict HEAD differs from dispatched brief')
    trees = re.findall(r'^Worktree: (.+)$', brief_text, re.M)
    if trees and trees[0] != 'none':
        from wuwei import registry
        tree = Path(trees[0])
        if not tree.is_absolute():
            raise Refused('gate brief has an invalid worktree')
        current_head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                                  str(tree), root=root)['sha']
        if not isinstance(current_head, str) or not current_head.lower().startswith(head.lower()):
            raise Refused('verdict HEAD differs from current worktree HEAD')
    current = [_record(data, item, gate, round_name) for gate in ROLES]
    if any(record and record['head'] != head for record in current):
        raise Refused('gate HEAD differs from sibling verdict')
    if role == 'security' and data['items'][item]['flags']['agent_surface']:
        from wuwei import scanner
        if not trees or trees[0] == 'none':
            raise OSError('scanner: unmeasured: missing reviewed worktree')
        findings = scanner.rows(tree, item, data['items'][item]['flags'],
                                workspace.load_config(root), root)
        measured_head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                                   str(tree), root=root)['sha']
        if measured_head != current_head:
            raise OSError('scanner: unmeasured: worktree HEAD changed during audit')
        text = scanner.merge(text, findings)
        code, message = verdict.lint(text, class_sweep=True)
        if code:
            raise OSError('scanner: unmeasured: ' + message)
    result = re.search(verdict.VERDICT_ROW, text, re.M)[1]
    blocks = verdict.finding_blocks(text)
    notes = [block.strip() for block in blocks if not re.search(verdict.BLOCKS_YES, block, re.I)]
    value = {'item': item, 'role': role, 'round': round_name, 'verdict': result,
             'head': head, 'file': str(path.relative_to(root)),
             'blocks': any(re.search(verdict.BLOCKS_YES, block, re.I) for block in blocks),
             'notes': notes}

    def update(fresh):
        _item(fresh, item)
        if fresh['items'][item]['flags'] != data['items'][item]['flags']:
            raise OSError('scanner: unmeasured: item flags changed during receive')
        if fresh['items'][item]['phase'] != data['items'][item]['phase'] or key in fresh['gate_verdicts']:
            raise Refused('gate state changed during receive')
        fresh['gate_verdicts'][key] = value

    state._write_state(update, root, reserved=False, kind='gate.received',
                       payload={'item': item, 'role': role, 'round': round_name, 'verdict': result})
    if role == 'security' and data['items'][item]['flags']['agent_surface']:
        workspace.atomic_write(path, text + '\n')
    return value


def discovery(trigger, root=None):
    """Emit a discovery wake; ranking and starts belong to discovery policy."""
    if trigger not in ('sweep', 'seat-free'):
        raise Refused('unknown discovery trigger')
    root = workspace.find_workspace() if root is None else Path(root)
    data = state.read_state(root)
    config = workspace.load_config(root)
    queued = sum(row['status'] == 'queued' and row['phase'] == 'planned'
                 for row in data['items'].values())
    needed = trigger == 'sweep' or queued < config['discovery']['min_queue']
    if needed:
        state.append_event('discovery.requested', {'trigger': trigger, 'queued': queued}, root)
    return {'action': 'discover' if needed else 'none'}
