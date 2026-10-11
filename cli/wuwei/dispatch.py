"""Planner decisions from recorded seats and gate verdicts."""

import os
from pathlib import Path
import re
import shlex
import sys

from wuwei import brief, registry, state, verdict, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED, RACE


ROLES = ('arch', 'quality', 'security')
GATE_BODY = 'Review {item} at its HEAD against its spec and acceptance criteria.'
SHEPHERD_BODY = ('Raise the PR for {item} and own it until merged. Open it with bin/wuwei pr raise '
                 '<owner/repo> --base <branch> --title <title> --body-file <file> --item {item}. It '
                 'links the PR to {item} and requests the ranked reviewers.')
TIERS = ('light', 'standard', 'full')
GATE_ROLES = (*ROLES, 'goal')  # #622: goal runs only as the single gate of a docs-only diff
# #622: a docs-only diff gets one reviewer. ponytail: documents are told by suffix, not content;
# .md and .rst anywhere, .txt only under docs/ or specs/. #657: a notebook is analysis.
DOC_DIRS = ('docs', 'specs')
DOC_SUFFIXES = ('.md', '.rst', '.ipynb')
AGENT_DOCS = ('AGENTS.md', 'CLAUDE.md', 'SKILL.md', 'charters/*', 'skills/*', 'agents/*',
              'commands/*', '.claude/*', '.agents/*')
SPEC_DOCS = ('specs/*', '*spec*', '*prereg*', '*pre-registration*')
# #734: a scratch path in verdict text, workspace-relative or absolute, maybe with :<line>
SCRATCH_PATH = r'[^\s`\'"()<>\[\]{},;|]*(?:scratchpad|\.wuwei/scratch)/[^\s`\'"()<>\[\]{},;|]+'


# ponytail: default seat cost before any seat ran (the default memory floor); measured after.
SEAT_MIB = 1024


def _gb(mib):
    return f'{round(mib / 1024, 1):g} GB'


def processes(config, policy):
    """#658: True when a seat runtime of the day launches its own process: any runtime but the
    Claude subagent, and none launches nothing. policy: the seat policy, role to row."""
    rows = policy.values() if isinstance(policy, dict) else ()
    names = {config['adapters']['runtime'], *(row.get('runtime') for row in rows if isinstance(row, dict))}
    return bool(names - {'claude', 'none', None})


def host(root, config, running=0, free=None, policy=None):
    """Capacity (#528, #658): CAP and the seat ceiling. Claude subagent seats take host.seats,
    else one per core, and never read free memory; seats that are separate processes take the
    median of today's last five memory readings (the seats that fit above the floor, one per
    core). Then the owner's values and the token budget; `bound` names what set CAP. `free` is
    MiB when the caller already measured it; `policy` the day's seat policy when held."""
    import statistics  # lazy: dispatch is on the hook path (#346)

    from wuwei import metrics, state, workspace
    from wuwei.guards.agent_launch import free_memory

    owner_cap, owner_seats = config['cap'], config['host']['seats']
    try:
        if policy is None:
            policy = state.read_state(root)['seat_policy']
        separate = processes(config, policy)
        if separate and free is None:
            free = free_memory(config, root) // 2**20
        cores = os.cpu_count()
        if not cores:
            raise ValueError('cores unmeasured (os.cpu_count gave none); run bin/wuwei doctor, then retry')
    except (OSError, ValueError) as exc:
        cap = owner_cap or 1
        return {'unmeasured': str(exc), 'cap': cap, 'seats': owner_seats or 4, 'bound': 'unmeasured',
                'text': f'cap {cap} (unmeasured): {exc}'}
    days = sorted((root / '.wuwei/days').glob('*'), reverse=True)
    damaged, memory = None, {}
    if separate:
        try:
            seat = next((cost for day in days
                         if (cost := metrics.seat_cost(metrics._events(day) or [])) != metrics.UNMEASURED), None)
        except ValueError as exc:
            # a damaged day log never blocks a launch: default seat cost, budget unmeasured
            seat, damaged = None, exc
        seat_mib = seat or SEAT_MIB
        reading = max(1, min(running + max(0, (free - config['host']['free_memory_mb']) // seat_mib), cores))
        try:  # the sweep records each reading on cap.derived; smooth over today's last five
            readings = [row['payload']['reading'] for row in metrics._events(workspace.day_dir(root)) or []
                        if row['kind'] == 'cap.derived' and type(row['payload'].get('reading')) is int][-4:]
        except ValueError as exc:
            readings, damaged = [], damaged or exc
        readings.append(reading)
        fit, rule = statistics.median_low(readings), 'memory'
        measured = ((f'median of {", ".join(map(str, readings))}; ' if len(readings) > 1 else '')
                    + f'{_gb(free)} free, {_gb(seat_mib)} per seat, {cores} cores')
        memory = {'free_mib': free, 'seat_mib': seat_mib,
                  'seat_source': 'default' if seat is None else 'measured', 'reading': reading}
    else:
        fit, rule = owner_seats or cores, 'host.seats'
        measured = 'subagent runtime, free memory not read' + ('' if owner_seats else f'; host.seats unset, {cores} cores')
    # the derived ceiling holds one gate (three sentinels launch together); the floor still guards
    seats = owner_seats or max(fit, len(ROLES))
    cap, bound = (owner_cap, 'owner') if owner_cap else (min(fit, seats), rule)
    text = (f'cap {cap} (owner): config cap; the host fits {min(fit, seats)} ({measured})'
            if owner_cap else f'cap {cap} ({bound}): {measured}')
    budget = config['budget']['tokens_per_day']
    if budget:
        # ponytail: counts tokens already spent today, not what running seats will still spend;
        # reserve a per-seat share at launch if this overshoots.
        try:
            per_seat = None if damaged else next((statistics.median(tokens) for day in days
                                                  if (tokens := metrics.seat_tokens(metrics._events(day) or []))), None)
            used = sum(metrics.seat_tokens(metrics._events(workspace.day_dir(root)) or []))
        except ValueError as exc:
            per_seat, damaged = None, damaged or exc
        if per_seat is None:
            text += f'; budget {budget} tokens a day, per-seat tokens unmeasured'
        else:
            per_seat = max(1, round(per_seat))
            fits = max(1, (budget - used) // per_seat)
            if fits < cap:
                cap, bound = fits, 'budget'
                text = f'cap {cap} (budget): {measured}'
            text += f'; budget {budget} tokens a day, {used} used, {per_seat} per seat'
    if damaged:
        text += f'; warning: {damaged}'
    return {'cores': cores, **memory, 'cap': cap, 'seats': seats, 'bound': bound, 'text': text}


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
    single = docs if docs and effective == 'light' else None
    if single:
        reasons.append(f'docs-only: 1 reviewer ({single})')
    record = {'tier': effective, 'computed': computed, 'reasons': reasons,
              'roles': [single] if single else ['quality'] if effective == 'light' else list(ROLES)}
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
    """#567: the item's process depth (design 5.3): its recorded tier, else the builder brief's
    prediction (never for a gate reader), else standard."""
    gates = row.get('gates') or {}
    return gates.get('tier') or (None if gate else row.get('depth')) or 'standard'


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


def polish_offer(config, row, roles, results, used):
    """#723: the polish round a round-one pass offers, {'gate', 'notes'}, or None (off, no
    notes, already recorded, or at the round cap). The gate is the one that wrote every
    note, else quality."""
    notes = [note for result in results for note in result['notes']]
    if (config['gates']['polish'] == 'never' or not notes or row.get('polish')
            or used >= max_rounds(config, row)):
        return None
    authors = [role for role, result in zip(roles, results) if result['notes']]
    return {'gate': authors[0] if len(authors) == 1 else 'quality', 'notes': notes}


def rechecks(data, item, role):
    """#723: role runs the item's delta: its initial verdict was not PASS (#732), or it is the
    gate of the item's open polish round (before the PR). One rule for next_step, delta_due, receive and
    opinion."""
    row = data['items'][item]
    first = _record(data, item, role, 'initial')
    polish = row.get('polish') or {}
    return bool(first) and (first['verdict'] != 'PASS' or (
        polish.get('status') == 'opened' and polish.get('gate') == role and not row.get('pr')))


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
GUARD_CODE = ('guards/*', 'outward*', 'hooks/*')


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
    from wuwei.tracker import relabel, ticket as recorded
    root = workspace.find_workspace(root)
    ticket = item
    try:
        config = workspace.load_config(root)
        ticket = recorded(state.read_state(root), item) or item
        if config['adapters']['tracker'] == 'none':
            result = registry.Result(2, reason='tracker adapter is none, so tracker updates are skipped; to reach the tracker, the owner sets adapters.tracker with bin/wuwei config set')
        else:
            tracker = registry.load('tracker', config)
            if action == 'claim':
                result = tracker.claim(ticket, root=root)
            elif action in ('in_review', 'done'):
                result = tracker.transition(ticket, config['tracker']['states'][action], root=root)
                if action == 'in_review' and isinstance(result, registry.Result) and result.exit:
                    result = relabel(tracker, root, config, item, ticket, result)  # #670
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


def _parked(root, item, reason, ask=True):
    """Park the item in code (plan.park). At the round cap the owner decides on plan resume's
    Owner step card (ask); a PARK verdict or the owner's No parks with no card."""
    from wuwei import plan
    plan.park(item, reason, root)
    return {'action': 'escalate' if ask else 'parked', 'reason': reason,
            'command': 'wuwei plan resume ' + shlex.quote(item)}


def _asked(root, data, item, results, roles, round_name):
    """The owner's answer ('Yes', 'No' or None) and the card for the ESCALATE verdicts asked."""
    import hashlib
    from wuwei import sessions
    key = ':'.join(f"{item}:{round_name}:{role}:{results[role]['verdict']}:{results[role]['file']}"
                   for role in roles)
    token = hashlib.sha256(key.encode()).hexdigest()[:12]
    role = roles[0]
    detail = (f"Gate {role} says {results[role]['verdict']} on {item}: {_head(results[role])}. "
              'Yes opens a fix round; No parks the item.')
    command = 'bin/wuwei dispatch next ' + shlex.quote(item)
    return (sessions.owner_answer(root, command, detail, token, PARKS),
            sessions.owner_card(command, detail, token, PARKS))


PARKS = 'The item parks.'


def _resumed(root, item):
    """True when the owner resumed the item after its last park and no fix round has opened
    since: the resume is the owner's Yes to the verdict that parked it."""
    from wuwei import watch
    last = {}
    for number, row in enumerate(watch.records(workspace.day_dir(root) / 'events.jsonl')):
        if row['payload'].get('item') == item and row['kind'] in ('plan.resumed', 'plan.disposed', 'build.fix_opened'):
            last[row['kind']] = number
    return last.get('plan.resumed', -1) > max(last.get('plan.disposed', -1), last.get('build.fix_opened', -1))


def _blocked(root, data, item):
    """(the stopped builder's Blocked: line, its agent id) when the line is not none, else None."""
    from wuwei import watch
    ids = {seat.get('agent_id') for seat in brief.seats(data).values()
           if seat['item'] == item and seat['role'] == 'builder' and seat['status'] == 'stopped'} - {None}
    found = [(str(row['payload'].get('fields', {}).get('Blocked', '')).strip(), row['payload']['agent_id'])
             for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
             if row['kind'] == 'retro.captured' and row['payload'].get('agent_id') in ids]
    return found[-1] if found and found[-1][0] and found[-1][0].casefold() != 'none' else None


def _head(result):
    """The first finding of a verdict on one line."""
    return ' '.join((result['findings'] or ['no finding'])[0].splitlines()[0].split())


def next_step(item, root=None):
    """Return the next planner action without launching a seat."""
    root = workspace.find_workspace(root)
    data = state.read_state(root)
    row = _item(data, item)
    phase = row['phase']
    if phase in ('parked', 'escalated'):  # only the owner resumes it, on plan resume's card
        return {'action': 'escalate', 'reason': (row.get('disposition') or {}).get('reason') or f'{item} is {phase}',
                'command': 'wuwei plan resume ' + shlex.quote(item)}
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
    note = ''
    if phase == 'gate' and (stopped := _blocked(root, data, item)):  # a builder's Blocked: line asks the owner
        import hashlib
        from wuwei import sessions
        line, agent = stopped
        reason, command = f'builder blocked: {line}', 'bin/wuwei dispatch next ' + shlex.quote(item)
        detail = f'The {item} builder stopped on: {line}. Yes sends it to its gates with your answer; No parks the item.'
        token = hashlib.sha256(f'{agent}\n{line}'.encode()).hexdigest()[:12]
        answer = sessions.owner_answer(root, command, detail, token, PARKS)
        if answer == 'No':
            return _parked(root, item, reason, ask=False)
        if answer != 'Yes':
            return {'action': 'escalate', 'reason': reason, 'command': 'wuwei dispatch next ' + shlex.quote(item),
                    'card': sessions.owner_card(command, detail, token, PARKS)}
        note = f"\nOwner decision: the owner said Yes to the builder's Blocked: line: {line}"
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
            return _parked(root, item, 'fix round already used')
        if any(_record(data, item, role, 'initial') is None for role in gates):
            raise Refused(f'fix phase requires all initial verdicts; record the missing one with bin/wuwei dispatch receive {item} <role> <seat> (bin/wuwei why {item} shows it)')
        return _fix(item, [role for role in gates if rechecks(data, item, role)])
    if phase == 'gate':
        roles = list(gates)
        round_name = 'initial'
    else:
        if any(_record(data, item, role, 'initial') is None for role in gates):
            raise Refused(f'delta phase requires all initial verdicts; record the missing one with bin/wuwei dispatch receive {item} <role> <seat> (bin/wuwei why {item} shows it)')
        roles = [role for role in gates if rechecks(data, item, role)]
        round_name = 'delta'
    missing = [role for role in roles if _record(data, item, role, round_name) is None]
    if missing:
        commands = []
        action = {'action': 'gates', 'roles': missing,
                  'seats': _seats(root, data, item, missing, round_name, commands, note)}
        if commands:  # #551: the exact brief and receive steps, never a remembered action
            action['commands'] = commands
        return {**action, 'tier': row['gates']} if phase == 'gate' and row['gates'] else action
    results = dict(zip(roles, (_record(data, item, role, round_name) for role in roles)))
    asked = [role for role in roles if results[role]['verdict'] in ('PARK', 'ESCALATE')]
    blocking = [role for role in roles if role in asked or (
        results[role]['verdict'] == 'FIX' if phase == 'gate' else results[role]['blocks'])]
    if not blocking:
        if phase == 'gate':  # #723: a pass with notes may offer a polish round
            offer = polish_offer(config, row, roles, list(results.values()), rounds_used(data, item))
            if offer is not None:
                if config['gates']['polish'] == 'always':
                    return _open_polish(root, item, offer)
                return {'action': 'polish', **offer, 'command': 'wuwei dispatch polish ' + shlex.quote(item),
                        'skip': 'wuwei dispatch skip-polish ' + shlex.quote(item)}
        return raise_action(root, data, item, [note for result in results.values() for note in result['notes']])
    cap = max_rounds(config, row)
    if rounds_used(data, item) >= cap:  # #623: a park with its finding at the cap
        findings = results[blocking[0]]['findings']
        finding = next((text for text in findings if re.search(verdict.BLOCKS_YES, text, re.I)),
                       (findings or ['none'])[0])
        return _parked(root, item, (
            f'round cap {cap} reached: {blocking[0]} still blocks: '
            f'{" ".join(finding.splitlines()[0].split())}; unpark after a design change '
            'that closes it is recorded in the spec'))
    parks = [role for role in asked if results[role]['verdict'] == 'PARK']
    if parks and not _resumed(root, item):  # a PARK verdict parks in code; a resume is the owner's Yes
        return _parked(root, item, f"gate {parks[0]} PARK: {_head(results[parks[0]])}", ask=False)
    if asked and not _resumed(root, item):  # ESCALATE: the owner decides on the Owner step card of dispatch next
        answer, card = _asked(root, data, item, results, asked, round_name)
        reason = f"gate {asked[0]} {results[asked[0]]['verdict']}: {_head(results[asked[0]])}"
        if answer == 'No':
            return _parked(root, item, reason, ask=False)
        if answer != 'Yes':
            return {'action': 'escalate', 'reason': reason, 'command': 'wuwei dispatch next ' + shlex.quote(item),
                    'card': card}
    from wuwei.commands import build
    build.open_fix(item, _fix_feedback(data, item, blocking, round_name), root=root)
    return _fix(item, blocking)


def raise_action(root, data, item, notes):
    """#783: raise in the gate shape (#551): the shepherd's brief command, then its launch."""
    name = f'shepherd-{item}'
    path = workspace.day_dir(root) / 'briefs' / f'{name}.md'
    worktree = data['items'][item].get('worktree') or str(root)
    action = {'action': 'raise', 'notes': notes, 'seats': []}
    if not path.is_file():
        body = '\n'.join([SHEPHERD_BODY.format(item=item), *(f'Review note: {note}' for note in notes)])
        action['commands'] = [f'wuwei brief shepherd {item} {name} --worktree {shlex.quote(worktree)} '
                              '--body ' + shlex.quote(body)]
    elif name not in data['seats']:
        action['seats'] = [brief.seat_action('shepherd', path, worktree, root)]
    else:
        action['reason'] = (f'{name} is {data["seats"][name].get("status")} and the PR is not raised; '
                            f'bin/wuwei why {item} shows it')
    return action


def launch_set(root=None):
    """The turn's launch set: each open approved item's next action, gate items first, then
    build, then planned; builders within CAP, launches within the free host.seats."""
    from collections import Counter
    from wuwei.commands import build
    from wuwei.commands.next import approved
    root = workspace.find_workspace(root)
    data, config = state.read_state(root), workspace.load_config(root)
    items = data['items']
    running = [seat for seat in brief.seats(data).values() if seat['status'] == 'running']
    # #528: capacity re-derives at every sweep; the day state keeps the snapshot.
    limits = host(root, config, running=len(running), policy=data['seat_policy'])
    cap, bound = limits['cap'], limits['bound']
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
        if launches > free:
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
    seated = [name for name in builds if not state.held(data, name)]  # #648: a held item takes no seat
    building = len(seated)
    share = Counter(data.get('goal_seats', {}))
    share.subtract(goal(name) for name in seated)
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
    """Today's proposal row for the item, else its #648 main_broken row (a fix item), or None."""
    import json
    path = workspace.day_dir(root) / 'proposal.json'
    candidates = json.loads(path.read_text(encoding='utf-8'))['candidates'] if path.is_file() else []
    return (next((row for row in candidates if row.get('id') == name), None)
            or state.read_state(root).get('main_broken', {}).get(name))


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


def _seats(root, data, item, roles, round_name, commands, note=''):
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
                                f'{shlex.quote(worktree)} --body ' + shlex.quote(GATE_BODY.format(item=item) + note))
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
            feedback = _recheck_feedback(data['items'][item], first,
                                         depth(data['items'][item], gate=True) == 'light', head)
            ci = brief.ci_block(data['items'][item].get('ci_jobs', ()), root / worktree)  # #733
            feedback += '\n' + ci if ci else ''
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
    return bool(row and row['phase'] == 'delta' and first and rechecks(data, item, role)
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


def _recheck_feedback(row, first, light=False, head='HEAD'):
    """#723: a polish re-check reads the notes; any other delta keeps _delta_feedback."""
    polish = row.get('polish') or {}
    if first['verdict'] != 'PASS' or polish.get('status') != 'opened':
        return _delta_feedback(first, light, head)
    return (f'Polish re-check: the polish round changed {first["head"]}..{head} to close these review '
            'notes:\n' + '\n'.join(polish['notes']) + f'\nRewrite {first["file"]} with Head: {head}: '
            'drop each note the delta closed, keep an open one as blocks: no, and block only on a '
            'defect the delta introduced.')


def _polish_feedback(notes):
    return ('Polish round: every gate passed. Fix only these non-blocking review notes, test first '
            'where a note names a behaviour, and change nothing else. A note that needs more than a '
            'small local change stays a review note; name it in your handoff.\n' + '\n'.join(notes))


def _fix_feedback(data, item, roles, round_name):
    return '\n'.join(f'Gate {role} {record["verdict"]}: fix only the blocking findings (blocks: yes) '
                     f'in {record["file"]}.' for role in roles
                     for record in (_record(data, item, role, round_name),))


def _fix(item, roles):
    return {'action': 'fix', 'roles': roles, 'command': 'wuwei build next ' + shlex.quote(item)}


def _stale_scratch(text, brief_text, root):
    """#734: scratch paths the verdict names that existed before its seat's brief was written."""
    from datetime import datetime
    written = re.search(r'^Written: (\S+)$', brief_text, re.M)
    if not written:
        return []
    since = datetime.fromisoformat(written[1]).timestamp()
    stale = []
    for token in dict.fromkeys(re.findall(SCRATCH_PATH, text)):
        path = Path(root) / re.sub(r'(:\d+)+$', '', token.rstrip('.:'))
        try:
            # ponytail: ctime, since tar sets mtime to the commit time; a stale file the seat
            # rewrote reads as new, which is right: its content is the seat's
            if path.stat().st_ctime < since:
                stale.append(token)
        except OSError:
            continue  # not on disk: nothing to date
    return stale


def _open_polish(root, item, offer):
    from wuwei.commands import build
    build.open_fix(item, _polish_feedback(offer['notes']), root=root,
                   polish={'status': 'opened', 'gate': offer['gate'], 'notes': offer['notes']})
    return _fix(item, [offer['gate']])


def _offered(root, item):
    """#723: the open polish offer; refused unless gates.polish is offer and one is open."""
    mode = workspace.load_config(root)['gates']['polish']
    if mode != 'offer':
        raise Refused(f'gates.polish is {mode}; bin/wuwei dispatch next {item} decides the polish round itself')
    offer = next_step(item, root)
    if offer['action'] != 'polish':
        raise Refused(f'{item} has no polish offer; run bin/wuwei dispatch next {item} for its step')
    return offer


def polish(item, root=None):
    """#723: open the offered polish round."""
    root = workspace.find_workspace(root)
    return _open_polish(root, item, _offered(root, item))


def skip_polish(item, root=None):
    """#723: decline the offered polish round; the notes ship as review notes."""
    root = workspace.find_workspace(root)
    offer = _offered(root, item)

    def update(fresh):
        row = _item(fresh, item)
        if row['phase'] != 'gate' or row.get('polish'):
            raise Refused(f'polish state changed during skip; {RACE}')
        row['polish'] = {'status': 'skipped', 'gate': offer['gate'], 'notes': offer['notes']}
    state._write_state(update, root, reserved=False, kind='polish.skipped',
                       payload={'item': item, 'gate': offer['gate'], 'notes': len(offer['notes'])})
    return raise_action(root, state.read_state(root), item, offer['notes'])


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
        if first is None or not rechecks(data, item, role):
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

    stale = _stale_scratch(text, brief_text, root)  # #734: before the write, so damage records nothing
    state._write_state(update, root, reserved=False, kind='gate.received',
                       payload={'item': item, 'role': role, 'round': round_name, 'verdict': result})
    if left:  # #672: the round left files in the builder's worktree
        # ponytail: git status omits ignored files (a gitignored __pycache__); the brief's
        # Probe env: line prevents those. Add an --ignored status form if seats keep leaving them.
        print(f"warning: {tree} has files the gate round left: {', '.join(left)}; gate seats "
              'probe in a copy under their scratch directory; remove them, or the next gate '
              'brief refuses a dirty tree', file=sys.stderr)
    for cited in stale:
        print(f"warning: {name}'s verdict names {cited}, which existed before its brief was "
              "written; its check may have read an earlier seat's files: rerun it in a new, "
              'empty directory', file=sys.stderr)
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
        raise Refused(f'item has no second opinion; the owner enables one with bin/wuwei config set gates.second_opinion')
    gate = gate_set(row)[-1]
    sentinel = 'sentinel-' + base(gate)
    round_name = {'gate': 'initial', 'delta': 'delta'}.get(row['phase'])
    if round_name is None:
        raise Refused(f'item phase {row["phase"]} has no second-opinion round; run bin/wuwei dispatch next {item} for the current step')
    if _record(data, item, gate, round_name):
        return _record(data, item, gate, round_name)
    first = _record(data, item, gate, 'initial')
    if round_name == 'delta' and not rechecks(data, item, gate):
        raise Refused(f'gate did not need a delta; drop --round delta, or run bin/wuwei dispatch next {item} for what is open')
    name = _opinion_name(data, brief.events(root) if round_name == 'initial' else [], item, gate, round_name)
    if name is None:
        raise Refused(f'write the {base(gate)} gate brief first')
    directory = workspace.day_dir(root)
    relative = str((directory / 'briefs' / f'{name}.md').relative_to(root))
    runtime = registry.load('runtime', {**config, 'adapters': {**config['adapters'], 'runtime': second['runtime']}})
    seat = data['seats'].get(name)
    if seat is None or seat['status'] == 'stopped':
        running = sum(other['status'] == 'running' for other in brief.seats(data).values())
        ceiling = host(root, config, running=running, policy=data['seat_policy'])['seats']  # #528
        if running >= ceiling:
            raise Refused(f'running seats at host seat ceiling host.seats={ceiling}; wait for a seat to finish. Or the owner raises host.seats with bin/wuwei config set')
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
                raise Refused('second opinion cannot resume on the builder runtime; set gates.second_opinion to a runtime other than the builder. The owner runs bin/wuwei config set')
            feedback = (_recheck_feedback(row, first, head=head) if round_name == 'delta' else
                        'Your verdict file was rejected by the verdict lint; rewrite '
                        f'{directory.relative_to(root)}/decisions/gate-{name}.md to the verdict '
                        'contract in your brief.')
            ci = brief.ci_block(row.get('ci_jobs', ()), root / row['worktree']) if round_name == 'delta' else ''
            feedback += '\n' + ci if ci else ''  # #733
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
