"""Planner decisions from recorded seats and gate verdicts."""

from pathlib import Path
import re
import shlex
import sys

from wuwei import brief, registry, state, verdict, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED, RACE


ROLES = ('arch', 'quality', 'security')
GATE_BODY = 'Review {item} at its HEAD against its spec and acceptance criteria.'
TIERS = ('light', 'standard', 'full')
GATE_ROLES = (*ROLES, 'goal')  # #622: goal runs only as the single gate of a docs-only diff
# #622: a docs-only diff gets one reviewer. ponytail: documents are told by suffix, not content;
# .md and .rst anywhere, .txt only under docs/ or specs/. #657: a notebook is analysis.
DOC_DIRS = ('docs', 'specs')
DOC_SUFFIXES = ('.md', '.rst', '.ipynb')
AGENT_DOCS = ('AGENTS.md', 'CLAUDE.md', 'SKILL.md', 'charters/*', 'skills/*', 'agents/*',
              'commands/*', '.claude/*', '.agents/*')
SPEC_DOCS = ('specs/*', '*spec*', '*prereg*', '*pre-registration*')


def gate_set(row):
    """The item's recorded gates; all three roles until a tier is recorded. Every set holds
    quality, except a docs-only item's single goal gate (#622).

    A recorded second opinion adds one gate named <role>@<runtime>."""
    roles = (row.get('gates') or {}).get('roles')
    if roles is None:
        return ROLES
    if not isinstance(roles, list) or not set(roles) <= set(GATE_ROLES) or (
            roles != ['goal'] and ('quality' not in roles or 'goal' in roles)):
        raise ValueError(f'invalid recorded gate set; {DAMAGED}')
    roles = tuple(role for role in GATE_ROLES if role in roles)
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


def _docs_role(paths, data=()):
    """#622: the single gate of a diff whose every path is a document, else None. #657: a
    data path (merge.uncounted) counts as a document."""
    from wuwei import merge
    if not paths or not all((path in data or path.endswith(DOC_SUFFIXES) or (
            path.endswith('.txt') and path.split('/', 1)[0] in DOC_DIRS))
            and merge.matched(path, AGENT_DOCS) is None for path in paths):
        return None
    return 'quality' if any(merge.matched(path, SPEC_DOCS) for path in paths) else 'goal'


def tier(root, config, row):
    """Compute the item's gate tier from its diff, flags, track, floor and lead tier."""
    from wuwei import merge
    computed, reasons, docs = 'light', [], None

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
        repo, changes = _changes(root, config, row)
        skip = merge.uncounted(root, repo, changes)  # #657: generated and data lines never count
        total = sum(change['additions'] or 0 for change in changes) + sum(
            change['deletions'] or 0 for change in changes)
        excluded = sum((change['additions'] or 0) + (change['deletions'] or 0)
                       for change in changes if change['path'] in skip)
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
            if (change['additions'] is None or change['deletions'] is None) and path not in skip:
                rise('standard', f'{path} binary change')
        # A .json counts as a document only under data_paths: by suffix alone it may be config.
        named = tuple(p + '*' if p.endswith('/') else p for p in gates['data_paths'])
        docs = _docs_role([change['path'] for change in changes],
                          [path for path, kind in skip.items() if kind == 'data' and (
                              not path.endswith('.json') or merge.matched(path, named))]
                          ) if computed == 'light' else None
        counted = total - excluded
        lines = f'{total} changed lines' + (
            f', {excluded} generated or data excluded, {counted} count,' if excluded else '')
        if counted > gates['light_max_lines'] and not docs:
            rise('standard', f'{lines} over light_max_lines {gates["light_max_lines"]}')
        elif not docs:
            reasons.append(f'{lines} within light_max_lines {gates["light_max_lines"]}')
    floor = repo['gates']['floor'] if repo else 'standard'
    if docs and floor != 'full':
        floor = 'light'
    effective = max(computed, floor, key=TIERS.index)
    if TIERS.index(floor) > TIERS.index(computed):
        reasons.append(f'floor {floor}')
    lead = row.get('tier')
    if docs and lead and TIERS.index(lead) > TIERS.index(effective):
        reasons.append(f'lead tier {lead} overridden: docs-only')
    elif lead and TIERS.index(lead) > TIERS.index(effective):
        effective = lead
        reasons.append(f'lead tier {lead}')
    elif lead and TIERS.index(lead) < TIERS.index(effective):
        reasons.append(f'lead tier {lead} refused: below {effective}')
    from wuwei import pace  # #579: the day's pace adjusts the tier and depth once, here
    guard = None
    if repo is not None:
        run, why = step_zero('standard', [change['path'] for change in changes], repo['gates']['trust_paths'])
        guard = why if run else None
    try:
        current = pace.current(state.read_state(root), config)
    except (OSError, ValueError, KeyError, TypeError):
        current = 'steady'  # an unreadable day never changes today's record
    flagged = row.get('track') == 'FULL' or any(row['flags'].values())
    effective, lighter, more = pace.adjust(current, effective, guard, flagged, repo is not None)
    reasons += more
    single = docs if docs and effective == 'light' else None
    if single:
        reasons.append(f'docs-only: 1 reviewer ({single})')
    record = {'tier': effective, 'computed': computed, 'reasons': reasons,
              'roles': [single] if single else ['quality'] if effective == 'light' else list(ROLES)}
    if lighter != effective:
        record['depth'] = lighter
    second = config['gates']['second_opinion']
    if effective != 'light' and second != 'off':
        runtime, _, model = second.partition(':')
        record['second_opinion'] = {'role': config['gates']['second_opinion_role'],
                                    'runtime': runtime, 'model': model}
    return record


def _changes(root, config, row):
    """(repository settings, diff stat rows) of the item's worktree against its merge base."""
    from wuwei.guards import commit_push
    if not row.get('worktree'):
        raise ValueError('no worktree; create one with bin/wuwei worktree add <item> before dispatching gates')
    tree = (root / row['worktree']).resolve()
    repo, _, vcs = commit_push.context(tree, {}, {}, root, identity=False)
    head = brief.read(vcs.head, str(tree), root=root)['sha']
    base = brief.read(vcs.merge_base, str(tree), config['brief']['remote'] + '/'
                      + repo['default_branch'], root=root)['sha']
    return repo, brief.read(vcs.diff_stat, str(tree), base, head, root=root)


def depth(row, *, gate=False):
    """#567: the item's process depth (design 5.3): the depth dispatch recorded (#579, the pace),
    else its tier, else the builder brief's prediction (never for a gate reader), else standard."""
    gates = row.get('gates') or {}
    return gates.get('depth') or gates.get('tier') or (None if gate else row.get('depth')) or 'standard'


def max_rounds(config, row):
    """#623: the item's fix-round cap: its recorded tier's override, else gates.max_rounds."""
    gates = config['gates']
    return gates['tier_max_rounds'].get((row.get('gates') or {}).get('tier')) or gates['max_rounds']


def rounds_used(data, item):
    """#623: fix rounds the item opened in this stage (the count resets at raise); a delta
    follows at least one, even after a manual transition."""
    used = (data.get('builds', {}).get(item) or {}).get('fix_rounds', 0)
    return max(used, int(data['items'][item]['phase'] == 'delta'))


def rotate(data, item, used):
    """#623: the next round answers each gate's delta verdict, so it becomes the gate's initial
    record and the record it replaces is kept as round<used>. Every verdict reader keeps
    reading initial and delta."""
    verdicts = data['gate_verdicts']
    for gate in gate_set(data['items'][item]):
        delta = verdicts.pop(f'{item}:{gate}:delta', None)
        if delta is not None:
            verdicts[f'{item}:{gate}:round{used}'] = verdicts[f'{item}:{gate}:initial']
            verdicts[f'{item}:{gate}:initial'] = delta


# #567: the builder's class sweep at standard covers the classes whose files the diff touches.
# ponytail: a glob heuristic per class; sentinels still own their classes.
CLASS_PATHS = (
    ('AUTH', ('guards/*', '*auth*', 'grants*', '*permission*', 'security*')),
    ('VAL', ('*pars*', '*valid*', '*schema*', 'config*', '*normal*')),
    ('DOC', ('*.md', 'docs/*', '*.rst')),
    ('TEST', ('tests/*', 'test_*', '*_test.*')),
    ('INF', ('.github/*', 'workflows/*', 'hooks/*', 'bin/*', '*.toml', '*.yml', '*.yaml',
             'Dockerfile*', '*.json')),
    ('RET', ('registry*', 'adapters/*', '*retry*')),
    ('ERR', ('exits*', '*error*', 'adapters/*', 'guards/*')),
    ('STATE', ('state*', '*lock*', '*journal*', 'events*')),
    ('CON', ('commands/*', '__main__*', '*contract*', '*schema*', '*api*')),
    ('BUD', ('adapters/*', '*runtime*', '*dispatch*', '*timeout*')),
)
GUARD_CODE = ('guards/*', 'grants*', 'outward*', 'hooks/*')


def classes(root, config, row):
    """(tier record, {class: changed paths}): none at light, the touched classes at standard,
    every class at full. ValueError when the diff cannot be read."""
    from wuwei import merge
    record = tier(root, config, row)
    if record.get('depth', record['tier']) == 'light':
        return record, {}
    _, changes = _changes(root, config, row)
    found = {name: [change['path'] for change in changes if merge.matched(change['path'], globs)]
             for name, globs in CLASS_PATHS}
    return record, {name: paths for name, paths in found.items()
                    if paths or record['tier'] == 'full'}


def step_zero(value, paths, trust_paths, flags=None):
    """#567: None at light; (run, reason) otherwise. At standard step zero runs only when a
    changed path is guard code or a repository trust path, or (#663) the item is flagged
    trust_surface or boundary_relevant, whatever its diff."""
    from wuwei import merge
    if value == 'light':
        return None
    if value == 'full':
        return True, ''
    named = [name for name in ('trust_surface', 'boundary_relevant') if (flags or {}).get(name)]
    if named:
        return True, ', '.join(named)
    for path in paths:
        pattern = merge.matched(path, (*trust_paths, *GUARD_CODE))
        if pattern is not None:
            return True, f'{path} matches {pattern}'
    return False, 'no guard code or trust path in the diff'


def tracker_call(item, action, root=None):
    """Record the tracker measurement without blocking the local build loop."""
    from wuwei.tracker import ticket as recorded
    root = workspace.find_workspace(root)
    ticket = item
    try:
        config = workspace.load_config(root)
        ticket = recorded(state.read_state(root), item) or item
        if config['adapters']['tracker'] == 'none':
            result = registry.Result(2, reason='tracker adapter is none, so tracker updates are skipped; to reach the tracker, the owner sets adapters.tracker with bin/wuwei config set in a host terminal')
        else:
            tracker = registry.load('tracker', config)
            if action == 'claim':
                result = tracker.claim(ticket, root=root)
            elif action in ('in_review', 'done'):
                result = tracker.transition(ticket, config['tracker']['states'][action], root=root)
            else:
                raise ValueError('unknown tracker action; pass claim, in_review or done')
            if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
                raise ValueError(f'invalid tracker result; {ADAPTER_DATA}')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = registry.Result(2, reason=f'tracker call unmeasured: {type(exc).__name__}')
    try:
        state.append_event('tracker.call', {'item': item, 'ticket': ticket, 'action': action,
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
    config = workspace.load_config(root)
    if phase == 'gate' and not row['gates'] and all(
            _record(data, item, role, 'initial') is None for role in ROLES):
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
    if phase == 'gate':
        # Design 5.10 backstop: no gates for an item reached by a manual transition with a gap.
        from wuwei import specmode
        code, reason = specmode.check(root, config, item, row, (root / row['worktree']).resolve()
                                      if row.get('worktree') else None, build=True, where='dispatch')
        if code:
            raise Refused(reason)
    from wuwei import tracker
    status, reason = tracker.check(data, config, item, row)
    if status == 'missing':
        raise Refused(reason)
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
        commands = []
        action = {'action': 'gates', 'roles': missing,
                  'seats': _seats(root, data, item, missing, round_name, commands)}
        if commands:  # #551: the exact brief and receive steps, never a remembered action
            action['commands'] = commands
        return {**action, 'tier': row['gates']} if phase == 'gate' and row['gates'] else action
    results = [_record(data, item, role, round_name) for role in roles]
    if any(result['verdict'] in ('PARK', 'ESCALATE') for result in results):
        return {'action': 'escalate', 'reason': 'gate parked or escalated'}
    if phase == 'gate':
        failures = [role for role in roles if _record(data, item, role, 'initial')['verdict'] == 'FIX']
        if not failures:
            return {'action': 'raise', 'notes': []}
        from wuwei.commands import build
        build.open_fix(item, _fix_feedback(data, item, failures, 'initial'), root=root)
        return _fix(item, failures)
    blocking = [role for role, result in zip(roles, results) if result['blocks']]
    if blocking:  # #623: the next round below the cap; a park with its finding at the cap
        cap = max_rounds(config, row)
        if rounds_used(data, item) >= cap:
            finding = next(text for text in results[roles.index(blocking[0])]['findings']
                           if re.search(verdict.BLOCKS_YES, text, re.I))
            return {'action': 'escalate', 'reason': (
                f'round cap {cap} reached: {blocking[0]} still blocks: '
                f'{" ".join(finding.splitlines()[0].split())}; unpark after a design change '
                'that closes it is recorded in the spec')}
        from wuwei.commands import build
        build.open_fix(item, _fix_feedback(data, item, blocking, 'delta'), root=root)
        return _fix(item, blocking)
    notes = [note for result in results for note in result['notes']]
    return {'action': 'raise', 'notes': notes}


def launch_set(root=None):
    """The turn's launch set: each open approved item's next action, gate items first, then
    build, then planned; builders within CAP, launches within the free host.seats."""
    from collections import Counter
    from wuwei.commands import build
    from wuwei.commands.next import approved
    root = workspace.find_workspace(root)
    data, config = state.read_state(root), workspace.load_config(root)
    from wuwei import calibrate
    items = data['items']
    running = [seat for seat in brief.seats(data).values() if seat['status'] == 'running']
    # #528: capacity re-derives at every sweep; the day state keeps the snapshot.
    limits = calibrate.host(root, config, running=len(running), policy=data['seat_policy'])
    from wuwei import pace  # #579: the day's pace sets the seats, never a refusal
    cap, bound, hold = pace.seats(pace.current(data, config), limits)
    ceiling = limits['seats']
    # #658: under the memory rule every sweep records its reading; CAP smooths over them
    if data['gate_approved'] and ((data['cap'], data['cap_bound']) != (cap, bound) or 'reading' in limits):
        state._write_state(lambda fresh: fresh.update(cap=cap, cap_bound=bound), root, reserved=False,
                           kind='cap.derived', payload={'cap': cap, 'bound': bound, 'text': limits['text'],
                                                        **{key: limits[key] for key in ('reading',) if key in limits}})
    free = start = ceiling - len(running)
    builds = [name for name in approved(data) if items[name]['phase'] in state.BUILD_PHASES]
    busy = {seat['item'] for seat in running}
    names = [name for name in approved(data) if name not in busy]
    goal = lambda name: items[name].get('goal', 'unplanned')
    entries = []

    def add(name, call):
        nonlocal free
        try:
            value = call()
        except (Refused, ValueError, build.PortExit) as exc:
            value = {'action': 'refused', 'reason': str(exc)}
        launches = len(value.get('seats', [])) if 'seats' in value else int(
            value['action'] in ('launch', 'continue', 'start'))
        if launches and hold:
            value = {'action': 'wait', 'reason': hold}
        elif launches > free:
            value = {'action': 'wait', 'reason': (
                f'{launches} launch(es) do not fit the {max(free, 0)} free of host.seats={ceiling}; '
                'they launch together next turn, after running seats stop')}
        else:
            free -= launches
        entries.append({'item': name, 'goal': goal(name), **value})

    for name in names:
        if items[name]['phase'] in ('gate', 'delta'):
            add(name, lambda: next_step(name, root))
    for name in builds:
        if name not in busy:
            add(name, lambda: build.next_action(name, root=root))
    building = len(builds)
    share = Counter(data.get('goal_seats', {}))
    share.subtract(goal(name) for name in builds)
    first, rest = [], []
    for name in (name for name in names if items[name]['phase'] == 'planned'):
        (first if share[goal(name)] > 0 else rest).append(name)
        share[goal(name)] -= 1
    briefed = {row['payload'].get('item') for row in brief.events(root)
               if row['kind'] == 'brief written' and row['payload'].get('role') == 'builder'}
    gate_waits = any(row['action'] == 'wait' for row in entries if items[row['item']]['phase'] in ('gate', 'delta'))
    starts, skip = {}, []
    for name in first + rest:
        if name in briefed:
            continue
        try:
            starts[name] = _start(root, name, config['repos'])
        except ValueError as exc:  # a corrupt proposal refuses this item, never the whole set
            skip.append(name)
            entries.append({'item': name, 'goal': goal(name), 'action': 'refused', 'reason': str(exc)})
            continue
        if starts[name][0].startswith('wuwei plan park '):  # #603: a park takes no seat, whatever the seats and CAP
            skip.append(name)
            entries.append({'item': name, 'goal': goal(name), 'action': 'park', 'commands': starts[name]})
    for index, name in enumerate(name for name in first + rest if name not in skip):
        if gate_waits:
            entries.append({'item': name, 'goal': goal(name), 'action': 'wait', 'reason': (
                'a gate waits for seats; gates launch before new builds so ready items merge first')})
        elif building + index >= cap:
            entries.append({'item': name, 'goal': goal(name), 'action': 'wait', 'reason': (
                f'CAP {cap} reached ({building} building); bin/wuwei next names the seat '
                'expected to free first')})
        elif name in briefed:
            add(name, lambda: build.next_action(name, root=root))
        else:
            add(name, lambda: {'action': 'start', 'commands': starts[name]})
    return {'action': 'set', 'cap': cap, 'bound': bound, 'capacity': limits['text'],
            'building': building, 'free_seats': start,
            'entries': entries}


def candidate(root, name):
    """Today's proposal row for the item, or None."""
    import json
    path = workspace.day_dir(root) / 'proposal.json'
    candidates = json.loads(path.read_text(encoding='utf-8'))['candidates'] if path.is_file() else []
    return next((row for row in candidates if row.get('id') == name), None)


def _start(root, name, repos):
    """The exact commands that start a planned item: its worktree, then its builder brief."""
    row = candidate(root, name)
    body = (f"Implement {name}: {row['scope']}. Evidence: {row['evidence']}." if row and row.get('scope')
            else f"Implement {name} as today's plan records it.")
    tree = f'worktrees/{name}'
    add = [] if (root / tree).exists() else [f'wuwei worktree add {name}']
    if add and len(repos) > 1:  # #603: worktree add exits 2 without --repo here
        names = [repo['name'] for repo in repos]
        repo = (row or {}).get('repo')
        if repo not in names:
            return [f'wuwei plan park {name} --reason ' + shlex.quote(
                f'names no configured repository ({", ".join(names)}); the lead names repo for it '
                'when it is proposed again')]
        add = [add[0] + ' --repo ' + shlex.quote(repo)]
    return add + [f'wuwei brief builder {name} builder-{name} --worktree {tree} --body ' + shlex.quote(body)]


def _seats(root, data, item, roles, round_name, commands):
    """Ready launch or continue actions for gate seats the planner has not started; the brief
    and receive commands still due go to commands."""
    worktree = data['items'][item].get('worktree')
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
            if not logged and worktree:
                commands.append(f'wuwei brief {role} {item} {role}-{item} --gate --worktree '
                                f'{shlex.quote(worktree)} --body ' + shlex.quote(GATE_BODY.format(item=item)))
            if logged and data['seats'].get(logged[-1].get('name'), {}).get('status') == 'stopped':
                commands.append('wuwei dispatch receive ' + ' '.join(map(shlex.quote, (item, role, logged[-1]['name']))))
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
            if (seat and seat['status'] == 'stopped' and seat.get('agent_id')
                    and not str(seat.get('head') or '').lower().startswith(first['head'].lower())):
                commands.append('wuwei dispatch receive ' + ' '.join(map(shlex.quote, (item, role, name)))
                                + ' --round delta')
            if not delta_due(data, item, role, name):
                continue
            # #669: the fix round moved the head; record it so an in-session resume can
            # write a true Head: line ('head' stays the initial head for delta_due).
            worktree = data['items'][item]['worktree']
            head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                              str((root / worktree).resolve()), root=root)['sha']
            if seat.get('delta_head') != head:
                state._write_state(lambda fresh: fresh['seats'][name].update(delta_head=head),
                                   root, reserved=False, kind='gate.delta_head',
                                   payload={'item': item, 'seat': name, 'head': head})
            action = brief.seat_action('sentinel-' + role, root / seat['brief'], worktree, root)
            feedback = _delta_feedback(first, depth(data['items'][item], gate=True) == 'light', head)
            extra = {'action': 'continue', 'resume': seat['agent_id'], 'feedback': feedback,
                     'prompt': action['prompt'] + '\n\n' + feedback}
        receive = 'wuwei dispatch receive ' + ' '.join(map(shlex.quote, (item, role, name)))
        actions.append({**action, **extra,
                        'receive': receive + (' --round delta' if round_name == 'delta' else '')})
    return actions


def delta_due(data, item, role, name):
    """#614: seat name is due its delta continue: the item is in delta, role's initial FIX came
    from that seat, no delta verdict yet, and the seat stopped with an agent id at the initial
    head (not continued since). One rule for _seats and the launch guard."""
    row = data['items'].get(item)
    first = _record(data, item, role, 'initial')
    seat = data['seats'].get(name)
    return bool(row and row['phase'] == 'delta' and first and first['verdict'] == 'FIX'
                and _record(data, item, role, 'delta') is None
                and Path(first['file']).stem.removeprefix('gate-') == name
                and seat and seat['status'] == 'stopped' and seat.get('agent_id')
                and str(seat.get('head') or '').lower().startswith(first['head'].lower()))


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


def _delta_feedback(first, light=False, head='HEAD'):
    if light:  # #567: no delta procedure at light; the same seat re-reads its findings
        return (f'Re-read: the fix round changed {first["head"]}..{head}. Re-read the diff for your '
                f'blocking findings and rewrite only the Verdict: and Head: lines of {first["file"]}, '
                f'with Head: {head}; mark each finding the fix closed blocks: no.')
    return (f'Delta review: the fix round changed {first["head"]}..{head}. Re-check your '
            f'findings at {head} and rewrite {first["file"]} with Head: {head}. A new finding on lines '
            'this fix round did not change is blocks: no, unless it is a trust-boundary security '
            'finding.')  # #623: no scope widening after round one


def _fix_feedback(data, item, roles, round_name):
    return '\n'.join(f'Gate {role} FIX: fix only the blocking findings (blocks: yes) in '
                     f'{_record(data, item, role, round_name)["file"]}.' for role in roles)


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
    # #669: a delta seat answers to the head the fix round left, never the stale brief head
    expected = str(seat.get('delta_head') or seat.get('head') or '') if round_name == 'delta' else ''
    if expected:
        if not expected.lower().startswith(head.lower()):
            raise Refused(f'verdict Head {head} is not the delta head {expected}; have the sentinel '
                          f'write the verdict with Head: {expected}, then receive it again')
    elif (f'HEAD: {head}' not in brief_text and f'Head: {head}' not in brief_text
            and not str(seat.get('head') or '').lower().startswith(head.lower())):
        raise Refused('verdict HEAD differs from dispatched brief; have the sentinel write the verdict with the Head from its brief, then receive it again')
    trees = re.findall(r'^Worktree: (.+)$', brief_text, re.M)
    left = []
    if trees and trees[0] != 'none':
        from wuwei import registry
        tree = Path(trees[0])
        if not tree.is_absolute():
            raise Refused(f'gate brief has an invalid worktree; write the brief again with --worktree <absolute path> (bin/wuwei worktree add {item} creates it)')
        vcs = registry.load('vcs', workspace.load_config(root))
        current_head = brief.read(vcs.head, str(tree), root=root)['sha']
        if not isinstance(current_head, str) or not current_head.lower().startswith(head.lower()):
            raise Refused(f'verdict HEAD differs from current worktree HEAD; write a fresh gate brief for the current HEAD and run bin/wuwei dispatch next {item}')
        left = [row['path'] for row in brief.status(vcs, str(tree), root)]  # #672
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
    blocks = sorted(verdict.finding_blocks(text),  # #677: blocking findings first
                    key=lambda block: not re.search(verdict.BLOCKS_YES, block, re.I))
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
    if left:  # #672: the round left files in the builder's worktree
        # ponytail: git status omits ignored files (a gitignored __pycache__); the brief's
        # Probe env: line prevents those. Add an --ignored status form if seats keep leaving them.
        print(f"warning: {tree} has files the gate round left: {', '.join(left)}; gate seats "
              'probe in a copy under their scratch directory; remove them, or the next gate '
              'brief refuses a dirty tree', file=sys.stderr)
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
        from wuwei import calibrate
        running = sum(other['status'] == 'running' for other in brief.seats(data).values())
        ceiling = calibrate.host(root, config, running=running, policy=data['seat_policy'])['seats']  # #528
        if running >= ceiling:
            raise Refused(f'running seats at host seat ceiling host.seats={ceiling}; wait for a seat to finish. Or the owner raises host.seats with bin/wuwei config set in a host terminal')
        head = brief.read(registry.load('vcs', config).head, row['worktree'], root=root)['sha']
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
                raise Refused('second opinion cannot resume on the builder runtime; set gates.second_opinion to a runtime other than the builder. The owner runs bin/wuwei config set in a host terminal')
            feedback = (_delta_feedback(first, head=head) if round_name == 'delta' else
                        'Your verdict file was rejected by the verdict lint; rewrite '
                        f'{directory.relative_to(root)}/decisions/gate-{name}.md to the verdict '
                        'contract in your brief.')
            job = build._data(runtime.continue_job(seat['job'], feedback, root=root), 'continuation')
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
