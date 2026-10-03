"""Planner decisions from recorded seats and gate verdicts."""

from pathlib import Path
import re
import shlex
import sys

from wuwei import brief, registry, state, verdict, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED, RACE


ROLES = ('arch', 'quality', 'security')
TIERS = ('light', 'standard', 'full')


def gate_set(row):
    """The item's recorded gates; all three roles until a tier is recorded.

    A recorded second opinion adds one gate named <role>@<runtime>."""
    roles = (row.get('gates') or {}).get('roles')
    if roles is None:
        return ROLES
    if not isinstance(roles, list) or 'quality' not in roles or not set(roles) <= set(ROLES):
        raise ValueError(f'invalid recorded gate set; {DAMAGED}')
    roles = tuple(role for role in ROLES if role in roles)
    second = row['gates'].get('second_opinion')
    if second is None:
        return roles
    if (not isinstance(second, dict) or second.get('role') not in roles
            or not re.fullmatch(r'[a-z]+', str(second.get('runtime')))
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', str(second.get('model')))):
        raise ValueError(f'invalid recorded gate set; {DAMAGED}')
    return (*roles, f"{second['role']}@{second['runtime']}")


def base(gate):
    """The sentinel role a gate runs as; a second opinion runs as its base role."""
    return gate.partition('@')[0]


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
            raise ValueError('no worktree; create one with bin/wuwei worktree add <item> before dispatching gates')
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
    record = {'tier': effective, 'computed': computed, 'reasons': reasons,
              'roles': ['quality'] if effective == 'light' else list(ROLES)}
    second = config['gates']['second_opinion']
    if effective != 'light' and second != 'off':
        runtime, _, model = second.partition(':')
        record['second_opinion'] = {'role': config['gates']['second_opinion_role'],
                                    'runtime': runtime, 'model': model}
    return record


def tracker_call(item, action, root=None):
    """Record the tracker measurement without blocking the local build loop."""
    root = workspace.find_workspace(root)
    try:
        config = workspace.load_config(root)
        if config['adapters']['tracker'] == 'none':
            result = registry.Result(2, reason='tracker adapter is none; tracker updates are skipped; the owner sets adapters.tracker with bin/wuwei config set in a host terminal if they should reach the tracker')
        else:
            tracker = registry.load('tracker', config)
            if action == 'claim':
                result = tracker.claim(item, root=root)
            elif action in ('in_review', 'done'):
                result = tracker.transition(item, config['tracker']['states'][action], root=root)
            else:
                raise ValueError('unknown tracker action; pass claim, in_review or done')
            if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
                raise ValueError(f'invalid tracker result; {ADAPTER_DATA}')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = registry.Result(2, reason=f'tracker call unmeasured: {type(exc).__name__}')
    try:
        state.append_event('tracker.call', {'item': item, 'action': action,
                           'exit': result.exit, 'reason': result.reason or ''}, root)
    except (OSError, ValueError) as exc:
        print(f'tracker call unmeasured: could not record result: {type(exc).__name__}; run bin/wuwei doctor, which tests the tracker adapter', file=sys.stderr)
    return result


class Refused(ValueError):
    """A measured planner refusal."""


def _item(data, item):
    if not data['gate_approved'] or item not in data['approved_items'] or item not in data['items']:
        raise Refused(f'{item} is not approved at the morning gate; approve it there (/wuwei:wuwei-plan) '
                      f'or admit it with bin/wuwei plan add {item}')
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
        raise Refused(f'{item} is in phase {phase}, not at a gate; run bin/wuwei build next {item}')
    if phase in ('gate', 'delta'):
        try:
            brief.gate_ready(data, item)
        except brief.Refused as exc:
            raise Refused(str(exc)) from exc
        if not any(seat['item'] == item and seat['role'] == 'builder'
                   and seat['status'] == 'stopped' for seat in brief.seats(data).values()):
            raise Refused(f'builder must stand down before gates; wait for the {item} builder to stop, then run bin/wuwei dispatch next {item}')
    if phase == 'gate' and not row['gates'] and all(
            _record(data, item, role, 'initial') is None for role in ROLES):
        config = workspace.load_config(root)
        record = tier(root, config, row)

        def update(fresh):
            if _item(fresh, item)['gates']:
                raise Refused(f'gate tier changed during dispatch; {RACE}')
            fresh['items'][item]['gates'] = record
        state._write_state(update, root, reserved=False, kind='gate.tiered',
                           payload={'item': item, **record})
        from wuwei import docs
        docs.exempt(root, config, item, record['tier'])
        row = data['items'][item] = {**row, 'gates': record}
    gates = gate_set(row)
    if phase == 'fix':
        if any(_record(data, item, role, 'delta') is not None for role in gates):
            return {'action': 'escalate', 'reason': 'fix round already used'}
        if any(_record(data, item, role, 'initial') is None for role in gates):
            raise Refused(f'fix phase requires all initial verdicts; record the missing one with bin/wuwei dispatch receive {item} <role> <seat> (bin/wuwei why {item} shows it)')
        roles = [role for role in gates
                 if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        return _fix(item, roles)
    if phase == 'gate':
        roles = list(gates)
        round_name = 'initial'
    else:
        if any(_record(data, item, role, 'initial') is None for role in gates):
            raise Refused(f'delta phase requires all initial verdicts; record the missing one with bin/wuwei dispatch receive {item} <role> <seat> (bin/wuwei why {item} shows it)')
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
        if '@' in role:
            second = data['items'][item]['gates']['second_opinion']
            name = _opinion_name(data, rows, item, role, round_name)
            seat = data['seats'].get(name) if name else None
            if name and not (seat and seat['status'] == 'running'):
                actions.append({'action': 'run', 'gate': role, 'runtime': second['runtime'],
                                'model': second['model'],
                                'command': 'wuwei dispatch opinion ' + shlex.quote(item)})
            continue
        if round_name == 'initial':
            logged = _first_briefs(rows, item, role)
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
            feedback = _delta_feedback(first)
            extra = {'action': 'continue', 'resume': seat['agent_id'], 'feedback': feedback,
                     'prompt': action['prompt'] + '\n\n' + feedback}
        receive = 'wuwei dispatch receive ' + ' '.join(map(shlex.quote, (item, role, name)))
        actions.append({**action, **extra,
                        'receive': receive + (' --round delta' if round_name == 'delta' else '')})
    return actions


def _first_briefs(rows, item, role):
    """Logged first-model gate briefs of one role; a second-opinion brief never launches as Agent."""
    return [row['payload'] for row in rows if row['kind'] == 'brief written'
            and row['payload'].get('item') == item
            and row['payload'].get('role') == 'sentinel-' + role
            and row['payload'].get('gate') is True and not row['payload'].get('second_opinion')]


def _opinion_name(data, rows, item, gate, round_name):
    """The second-opinion seat name once its round can run, else None."""
    if round_name == 'delta':
        return Path(_record(data, item, gate, 'initial')['file']).stem.removeprefix('gate-')
    logged = _first_briefs(rows, item, base(gate))
    return logged[-1]['name'] + '-' + gate.partition('@')[2] if logged else None


def _delta_feedback(first):
    return (f'Delta review: the fix round changed {first["head"]}..HEAD. Re-check your '
            f'findings at the current HEAD and rewrite {first["file"]}.')


def _fix(item, roles):
    return {'action': 'fix', 'roles': roles, 'command': 'wuwei build next ' + shlex.quote(item)}


def receive(item, role, name, round_name='initial', root=None):
    """Lint and record one stopped sentinel's verdict file."""
    root = workspace.find_workspace() if root is None else Path(root)
    data = state.read_state(root)
    _item(data, item)
    if round_name not in ('initial', 'delta'):
        raise Refused('unknown gate round; pass --round delta for a delta, or leave the flag out for the initial round')
    gates = gate_set(data['items'][item])
    if role not in gates:
        raise Refused(f'gate role {role} is not in the item gate set; use one of {", ".join(gates)}')
    sentinel = 'sentinel-' + base(role)
    if data['items'][item]['phase'] != ('gate' if round_name == 'initial' else 'delta'):
        raise Refused(f'gate round does not match item phase {data["items"][item]["phase"]};run bin/wuwei dispatch next {item} for the right round')
    if round_name == 'delta':
        first = _record(data, item, role, 'initial')
        if first is None or first['verdict'] != 'FIX':
            raise Refused(f'gate did not need a delta; drop --round delta, or run bin/wuwei dispatch next {item} for what is open')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise Refused('unsafe seat name; use the seat name that bin/wuwei dispatch next returned')
    seat = brief.seats(data).get(name)
    if not seat or seat['item'] != item or seat['role'] != sentinel or seat['status'] != 'stopped':
        raise Refused('matching sentinel must stand down before receive; wait for the seat to stop, then rerun the same bin/wuwei dispatch receive')
    runtime = role.partition('@')[2] or None
    if seat.get('runtime') != runtime or (runtime and not name.endswith('-' + runtime)):
        raise Refused(f'gate role {role} needs its own runtime seat; start it with bin/wuwei dispatch opinion {item}')
    key = f'{item}:{role}:{round_name}'
    if key in data['gate_verdicts']:
        raise Refused(f'gate already received; run bin/wuwei dispatch next {item} for what remains')
    directory = workspace.day_dir(root)
    path = directory / 'decisions' / f'gate-{name}.md'
    if path.is_symlink():
        raise Refused('gate verdict must be a regular day file; replace the link with the file itself; bin/wuwei doctor names it')
    code, message = verdict.lint_file(path, role=sentinel, root=root)
    if code == 2:
        raise OSError(message)
    if code:
        raise Refused(message)
    text = verdict.active_text(path.read_text(encoding='utf-8'))
    head = verdict.rows(text, 'Head')[0].strip()
    brief_path = root / seat['brief']
    if brief_path.resolve() != directory / 'briefs' / f'{name}.md':
        raise Refused(f'seat brief path does not match gate name; receive the seat with the name its brief was written for (bin/wuwei dispatch next {item})')
    brief_text = brief_path.read_text(encoding='utf-8')
    if (f'HEAD: {head}' not in brief_text and f'Head: {head}' not in brief_text
            and not str(seat.get('head') or '').lower().startswith(head.lower())):
        raise Refused('verdict HEAD differs from dispatched brief; have the sentinel write the verdict with the Head from its brief, then receive it again')
    trees = re.findall(r'^Worktree: (.+)$', brief_text, re.M)
    if trees and trees[0] != 'none':
        from wuwei import registry
        tree = Path(trees[0])
        if not tree.is_absolute():
            raise Refused(f'gate brief has an invalid worktree; write the brief again with --worktree <absolute path> (bin/wuwei worktree add {item} creates it)')
        current_head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                                  str(tree), root=root)['sha']
        if not isinstance(current_head, str) or not current_head.lower().startswith(head.lower()):
            raise Refused(f'verdict HEAD differs from current worktree HEAD; write a fresh gate brief for the current HEAD and run bin/wuwei dispatch next {item}')
    current = [_record(data, item, gate, round_name) for gate in gates]
    if any(record and record['head'] != head for record in current):
        raise Refused(f'gate HEAD differs from sibling verdict; rerun the odd gate on the current HEAD via bin/wuwei dispatch next {item}')
    if sentinel == 'sentinel-security' and data['items'][item]['flags']['agent_surface']:
        from wuwei import scanner
        if not trees or trees[0] == 'none':
            raise OSError('scanner: unmeasured: missing reviewed worktree; write the security brief again with --worktree <absolute path>, then receive the verdict again')
        findings = scanner.rows(tree, item, data['items'][item]['flags'],
                                workspace.load_config(root), root)
        measured_head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                                   str(tree), root=root)['sha']
        if measured_head != current_head:
            raise OSError(f'scanner: unmeasured: worktree HEAD changed during audit; {RACE}')
        text = scanner.merge(text, findings)
        code, message = verdict.lint(text, class_sweep=True)
        if code:
            raise OSError(f'scanner: unmeasured: {message}; fix the verdict as named, check it with bin/wuwei verdict lint <file>, then receive it again')
    result = re.search(verdict.VERDICT_ROW, text, re.M)[1]
    if base(role) == 'quality':
        from wuwei import docs
        config = workspace.load_config(root)
        if docs.unmet(config, data['items'][item]) and (
                result == 'PASS' or not re.search(r'\bDOC: *FINDING', text)):
            raise Refused(f'docs obligation unmet for {item}; have the sentinel write a FIX verdict with a '
                          f'DOC: FINDING naming {docs.command(config, item)}, then receive it again')
    blocks = verdict.finding_blocks(text)
    notes = [block.strip() for block in blocks if not re.search(verdict.BLOCKS_YES, block, re.I)]
    value = {'item': item, 'role': role, 'round': round_name, 'verdict': result,
             'head': head, 'file': str(path.relative_to(root)),
             'blocks': any(re.search(verdict.BLOCKS_YES, block, re.I) for block in blocks),
             'notes': notes, 'findings': [block.strip() for block in blocks],
             'usage': seat.get('usage') or _seat_usage(seat, data['seat_policy'].get(sentinel, {}))}
    if runtime:
        value.update(runtime=seat['runtime'], model=seat.get('model'))

    def update(fresh):
        _item(fresh, item)
        if fresh['items'][item]['flags'] != data['items'][item]['flags']:
            raise OSError(f'scanner: unmeasured: item flags changed during receive; {RACE}')
        if fresh['items'][item]['phase'] != data['items'][item]['phase'] or key in fresh['gate_verdicts']:
            raise Refused(f'gate state changed during receive; {RACE}')
        fresh['gate_verdicts'][key] = value

    state._write_state(update, root, reserved=False, kind='gate.received',
                       payload={'item': item, 'role': role, 'round': round_name, 'verdict': result})
    if sentinel == 'sentinel-security' and data['items'][item]['flags']['agent_surface']:
        workspace.atomic_write(path, text + '\n')
    return value


def opinion(item, root=None):
    """Run the item's second-opinion gate through its runtime adapter and receive its verdict."""
    from wuwei.commands import build
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    data = state.read_state(root)
    row = _item(data, item)
    second = (row.get('gates') or {}).get('second_opinion')
    if not second:
        raise Refused(f'item has no second opinion; the owner enables one with bin/wuwei config set gates.second_opinion in a host terminal')
    gate = gate_set(row)[-1]
    sentinel = 'sentinel-' + base(gate)
    round_name = {'gate': 'initial', 'delta': 'delta'}.get(row['phase'])
    if round_name is None:
        raise Refused(f'item phase {row["phase"]} has no second-opinion round; run bin/wuwei dispatch next {item} for the current step')
    if _record(data, item, gate, round_name):
        return _record(data, item, gate, round_name)
    first = _record(data, item, gate, 'initial')
    if round_name == 'delta' and (not first or first['verdict'] != 'FIX'):
        raise Refused(f'gate did not need a delta; drop --round delta, or run bin/wuwei dispatch next {item} for what is open')
    name = _opinion_name(data, brief.events(root) if round_name == 'initial' else [], item, gate, round_name)
    if name is None:
        raise Refused(f'write the {base(gate)} gate brief first')
    directory = workspace.day_dir(root)
    relative = str((directory / 'briefs' / f'{name}.md').relative_to(root))
    runtime = registry.load('runtime', {**config, 'adapters': {**config['adapters'], 'runtime': second['runtime']}})
    seat = data['seats'].get(name)
    if seat is None or seat['status'] == 'stopped':
        if sum(other['status'] == 'running' for other in brief.seats(data).values()) >= config['host']['seats']:
            raise Refused(f'running seats at host seat ceiling host.seats={config["host"]["seats"]}; wait for a seat to finish, or the owner raises host.seats with bin/wuwei config set in a host terminal')
        if seat is None:
            if round_name == 'delta':
                raise Refused(f'second-opinion seat is missing; run bin/wuwei why {item}, then bin/wuwei dispatch next {item}')
            if not (root / relative).exists():
                text = (directory / 'briefs' / f'{name.rpartition("-")[0]}.md').read_text(encoding='utf-8')
                try:
                    brief.write(sentinel, item, name, text.split('\n\n', 1)[1].removesuffix('\n'),
                                gate=True, second_opinion=second, root=root)
                except brief.Refused as exc:
                    raise Refused(str(exc)) from exc
            job = build._data(runtime.dispatch(sentinel, str(root / relative), row['worktree'], True,
                                               root=root), 'dispatch')
        else:
            # continue_job resumes the latest thread of this runtime in the worktree, which is
            # the builder's own thread when the builder runs on the same runtime.
            if data['seat_policy'].get('builder', {}).get('runtime') == second['runtime']:
                raise Refused('second opinion cannot resume on the builder runtime; set gates.second_opinion to a runtime other than the builder (the owner runs bin/wuwei config set in a host terminal)')
            feedback = (_delta_feedback(first) if round_name == 'delta' else
                        'Your verdict file was rejected by the verdict lint; rewrite '
                        f'{directory.relative_to(root)}/decisions/gate-{name}.md to the verdict '
                        'contract in your brief.')
            job = build._data(runtime.continue_job(seat['job'], feedback, root=root), 'continuation')
        head = brief.read(registry.load('vcs', config).head, row['worktree'], root=root)['sha']
        seat = {'id': name, 'role': sentinel, 'item': item, 'brief': relative, 'head': head,
                'status': 'running', 'started_at': workspace.now().isoformat(),
                'runtime': second['runtime'], 'model': second['model'], 'job': job}
        state._write_state(lambda fresh: fresh['seats'].update({name: seat}), root, reserved=False,
                           kind='seat launched', payload={'name': name, 'item': item})
    status = build.wait(runtime, seat['job'], config, root)
    result = build._data(runtime.result(seat['job'], root=root), 'result')
    if not isinstance(result, dict) or not isinstance(result.get('text'), str):
        raise ValueError(f'invalid runtime result; {ADAPTER_DATA}')
    path = directory / 'decisions' / f'gate-{name}.md'
    if path.is_symlink():
        raise Refused('gate verdict must be a regular day file; replace the link with the file itself; bin/wuwei doctor names it')
    if not path.is_file() or path.stat().st_mtime < seat['job'].get('started_at', float('inf')):
        path.parent.mkdir(exist_ok=True)
        workspace.atomic_write(path, result['text'] + '\n')
    from datetime import datetime
    usage = {'duration': (workspace.now() - datetime.fromisoformat(seat['started_at'])).total_seconds(),
             **result.get('usage', {})}
    usage = build.normalize_usage(usage, status.get('model') or second['model'])

    def stop(fresh):
        fresh['seats'][name].update(status='stopped', stopped_at=workspace.now().isoformat(), usage=usage)
    state._write_state(stop, root, reserved=False, kind='seat.usage',
                       payload={'item': item, 'role': sentinel, 'gate': gate, 'usage': usage})
    state.append_event('seat stopped', {'name': name}, root)
    return receive(item, gate, name, round_name, root)


def _seat_usage(seat, policy):
    """A Claude seat's usage: duration from its start and stop, model from its policy."""
    from datetime import datetime
    from wuwei.commands import build
    measured = {}
    if seat.get('started_at') and seat.get('stopped_at'):
        measured['duration'] = (datetime.fromisoformat(seat['stopped_at'])
                                - datetime.fromisoformat(seat['started_at'])).total_seconds()
    return build.normalize_usage(measured, policy.get('model'))


def discovery(trigger, root=None, found=None):
    """Emit a discovery wake; ranking and starts belong to discovery policy."""
    if trigger not in ('sweep', 'seat-free'):
        raise Refused('unknown discovery trigger; run bin/wuwei dispatch discovery sweep or bin/wuwei dispatch discovery seat-free')
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
