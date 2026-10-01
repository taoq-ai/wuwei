"""Planner decisions from recorded seats and gate verdicts."""

from pathlib import Path
import re
import shlex
import sys

from wuwei import brief, registry, state, verdict, workspace


ROLES = ('arch', 'quality', 'security')
TIERS = ('light', 'standard', 'full')


def gate_set(row):
    """The item's recorded gate roles; all three until a tier is recorded."""
    roles = (row.get('gates') or {}).get('roles')
    if roles is None:
        return ROLES
    if not isinstance(roles, list) or 'quality' not in roles or not set(roles) <= set(ROLES):
        raise ValueError('invalid recorded gate set')
    return tuple(role for role in ROLES if role in roles)


def tier(root, config, row):
    """Compute the item's gate tier from its diff, flags, track, floor and lead tier."""
    from wuwei import merge
    from wuwei.guards import commit_push
    computed, reasons = 'light', []

    def rise(level, reason):
        nonlocal computed
        computed = max(computed, level, key=TIERS.index)
        reasons.append(reason)
    if row.get('track') == 'FULL':
        rise('full', 'track FULL')
    for name, value in row['flags'].items():
        if value:
            rise('standard', f'lead flag {name}')
    try:
        if not row.get('worktree'):
            raise ValueError('no worktree')
        tree = (root / row['worktree']).resolve()
        repo, _, vcs = commit_push.context(tree, {}, {}, root, identity=False)
        head = brief.read(vcs.head, str(tree), root=root)['sha']
        base = brief.read(vcs.merge_base, str(tree), config['brief']['remote'] + '/'
                          + repo['default_branch'], root=root)['sha']
        changes = brief.read(vcs.diff_stat, str(tree), base, head, root=root)
        total = sum(change['additions'] or 0 for change in changes) + sum(
            change['deletions'] or 0 for change in changes)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        repo = None
        rise('standard', f'diff unmeasured: {str(exc) or type(exc).__name__}')
    else:
        gates = repo['gates']
        for change in changes:
            path = change['path']
            for kind, patterns in (('trust path', gates['trust_paths']),
                                   ('never-auto path', repo['merge']['never_auto_paths'])):
                pattern = merge.matched(path, patterns)
                if pattern is not None:
                    rise('standard', f'{path} matches {kind} {pattern}')
            pattern = next((p for p in config['brief']['full_path_patterns'] if re.search(p, path, re.I)), None)
            if pattern is not None:
                rise('standard', f'{path} matches FULL-track pattern {pattern}')
            if change['additions'] is None or change['deletions'] is None:
                rise('standard', f'{path} binary change')
        if total > gates['light_max_lines']:
            rise('standard', f'{total} changed lines over light_max_lines {gates["light_max_lines"]}')
        elif computed == 'light':
            reasons.append(f'{total} changed lines within light_max_lines {gates["light_max_lines"]}')
    floor = repo['gates']['floor'] if repo else 'standard'
    effective = max(computed, floor, key=TIERS.index)
    if TIERS.index(floor) > TIERS.index(computed):
        reasons.append(f'floor {floor}')
    lead = row.get('tier')
    if lead and TIERS.index(lead) > TIERS.index(effective):
        effective = lead
        reasons.append(f'lead tier {lead}')
    elif lead and TIERS.index(lead) < TIERS.index(effective):
        reasons.append(f'lead tier {lead} refused: below {effective}')
    return {'tier': effective, 'computed': computed, 'reasons': reasons,
            'roles': ['quality'] if effective == 'light' else list(ROLES)}


def tracker_call(item, action, root=None):
    """Record the tracker measurement without blocking the local build loop."""
    root = workspace.find_workspace(root)
    try:
        config = workspace.load_config(root)
        if config['adapters']['tracker'] == 'none':
            result = registry.Result(2, reason='tracker adapter is none')
        else:
            tracker = registry.load('tracker', config)
            if action == 'claim':
                result = tracker.claim(item, root=root)
            elif action in ('in_review', 'done'):
                result = tracker.transition(item, config['tracker']['states'][action], root=root)
            else:
                raise ValueError('unknown tracker action')
            if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
                raise ValueError('invalid tracker result')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = registry.Result(2, reason=f'tracker call unmeasured: {type(exc).__name__}')
    try:
        state.append_event('tracker.call', {'item': item, 'action': action,
                           'exit': result.exit, 'reason': result.reason or ''}, root)
    except (OSError, ValueError) as exc:
        print(f'tracker call unmeasured: could not record result: {type(exc).__name__}', file=sys.stderr)
    return result


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
    root = workspace.find_workspace(root)
    steward.review(root)
    data = state.read_state(root)
    row = _item(data, item)
    notes = steward.pending(data, item)
    if notes:
        raise Refused(f'steward note {notes[0]["id"]} requires planner acknowledgement: '
                      f'{notes[0]["text"]}')
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
    if phase == 'gate' and not row['gates'] and all(
            _record(data, item, role, 'initial') is None for role in ROLES):
        record = tier(root, workspace.load_config(root), row)

        def update(fresh):
            if _item(fresh, item)['gates']:
                raise Refused('gate tier changed during dispatch')
            fresh['items'][item]['gates'] = record
        state._write_state(update, root, reserved=False, kind='gate.tiered',
                           payload={'item': item, **record})
        row = {**row, 'gates': record}
    gates = gate_set(row)
    if phase == 'fix':
        if any(_record(data, item, role, 'delta') is not None for role in gates):
            return {'action': 'escalate', 'reason': 'fix round already used'}
        if any(_record(data, item, role, 'initial') is None for role in gates):
            raise Refused('fix phase requires all initial verdicts')
        roles = [role for role in gates
                 if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        return _fix(item, roles)
    if phase == 'gate':
        roles = list(gates)
        round_name = 'initial'
    else:
        if any(_record(data, item, role, 'initial') is None for role in gates):
            raise Refused('delta phase requires all initial verdicts')
        roles = [role for role in gates
                 if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        round_name = 'delta'
    if any(_record(data, item, role, round_name) and
           _record(data, item, role, round_name)['verdict'] in ('PARK', 'ESCALATE')
           for role in roles):
        return {'action': 'escalate', 'reason': 'gate parked or escalated'}
    missing = [role for role in roles if _record(data, item, role, round_name) is None]
    if missing:
        action = {'action': 'gates', 'roles': missing,
                  'seats': _seats(root, data, item, missing, round_name)}
        return {**action, 'tier': row['gates']} if phase == 'gate' and row['gates'] else action
    results = [_record(data, item, role, round_name) for role in roles]
    if any(result['verdict'] in ('PARK', 'ESCALATE') for result in results):
        return {'action': 'escalate', 'reason': 'gate parked or escalated'}
    if phase == 'gate':
        failures = [role for role in roles if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        if not failures:
            return {'action': 'raise', 'notes': []}
        from wuwei.commands import build
        feedback = '\n'.join(f'Gate {role} FIX: fix only the blocking findings (blocks: yes) in '
                             f'{_record(data, item, role, "initial")["file"]}.' for role in failures)
        build.open_fix(item, feedback, root=root)
        return _fix(item, failures)
    if any(result['blocks'] for result in results):
        return {'action': 'escalate', 'reason': 'blocking finding remains after delta'}
    notes = [note for result in results for note in result['notes']]
    return {'action': 'raise', 'notes': notes}


def _seats(root, data, item, roles, round_name):
    """Ready launch or continue actions for gate seats the planner has not started."""
    actions = []
    rows = brief.events(root) if round_name == 'initial' else []
    for role in roles:
        if round_name == 'initial':
            logged = [row['payload'] for row in rows if row['kind'] == 'brief written'
                      and row['payload'].get('item') == item
                      and row['payload'].get('role') == 'sentinel-' + role
                      and row['payload'].get('gate') is True]
            if not logged or logged[-1].get('name') in data['seats']:
                continue
            name = logged[-1]['name']
            action = brief.seat_action('sentinel-' + role, root / logged[-1]['path'],
                                       logged[-1]['worktree'], root)
            extra = {}
        else:
            first = _record(data, item, role, 'initial')
            name = Path(first['file']).stem.removeprefix('gate-')
            seat = data['seats'].get(name)
            if (not seat or seat['status'] != 'stopped' or not seat.get('agent_id')
                    or not str(seat.get('head') or '').lower().startswith(first['head'].lower())):
                continue
            action = brief.seat_action('sentinel-' + role, root / seat['brief'],
                                       data['items'][item]['worktree'], root)
            feedback = (f'Delta review: the fix round changed {first["head"]}..HEAD. Re-check your '
                        f'findings at the current HEAD and rewrite {first["file"]}.')
            extra = {'action': 'continue', 'resume': seat['agent_id'], 'feedback': feedback,
                     'prompt': action['prompt'] + '\n\n' + feedback}
        receive = 'wuwei dispatch receive ' + ' '.join(map(shlex.quote, (item, role, name)))
        actions.append({**action, **extra,
                        'receive': receive + (' --round delta' if round_name == 'delta' else '')})
    return actions


def _fix(item, roles):
    return {'action': 'fix', 'roles': roles, 'command': 'wuwei build next ' + shlex.quote(item)}


def receive(item, role, name, round_name='initial', root=None):
    """Lint and record one stopped sentinel's verdict file."""
    root = workspace.find_workspace() if root is None else Path(root)
    data = state.read_state(root)
    _item(data, item)
    if role not in ROLES or round_name not in ('initial', 'delta'):
        raise Refused('unknown gate role or round')
    if role not in gate_set(data['items'][item]):
        raise Refused(f'gate role {role} is not in the item gate set')
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
    if (f'HEAD: {head}' not in brief_text and f'Head: {head}' not in brief_text
            and not str(seat.get('head') or '').lower().startswith(head.lower())):
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


def discovery(trigger, root=None, found=None):
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
    if trigger == 'sweep':
        # A seat-free request runs on the watch's next tick, off the hook path.
        from wuwei import discovery as discovery_module
        discovery_module.intake(root, trigger=trigger, found=found)
    return {'action': 'discover' if needed else 'none'}
