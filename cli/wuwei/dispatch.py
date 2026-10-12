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
    core). Then the owner's values; `bound` names what set CAP. `free` is MiB when the caller
    already measured it; `policy` the day's seat policy when held. #898: with
    host.min_free_memory_pct set, every runtime reads the share free; `held` says why no new
    seat launches (below the floor, or unmeasured)."""
    import statistics  # lazy: dispatch is on the hook path (#346)

    from wuwei import metrics, state, workspace
    from wuwei.guards.agent_launch import free_memory, free_percent

    owner_cap, owner_seats = config['cap'], config['host']['seats']
    floor, held, note = config['host']['min_free_memory_pct'], {}, ''
    if floor:
        try:
            share = free_percent(config, root)
            note = f'; free memory {share}% (floor {floor}%)'
            held = {'held': f'held: free memory {share}% < {floor}%'} if share < floor else {}
        except ValueError as exc:  # never a silent block: the hold names the reading's failure
            note, held = f'; {exc}', {'held': f'held: {exc}' + (
                '' if 'doctor' in str(exc) else '; bin/wuwei doctor tests the host adapter')}
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
                'text': f'cap {cap} (unmeasured): {exc}{note}', **held}
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
        measured = 'subagent runtime' + ('' if floor else ', free memory not read') + (
            '' if owner_seats else f'; host.seats unset, {cores} cores')
    # the derived ceiling holds one gate (three sentinels launch together); the floor still guards
    seats = owner_seats or max(fit, len(ROLES))
    cap, bound = (owner_cap, 'owner') if owner_cap else (min(fit, seats), rule)
    text = (f'cap {cap} (owner): config cap; the host fits {min(fit, seats)} ({measured})'
            if owner_cap else f'cap {cap} ({bound}): {measured}')
    if damaged:
        text += f'; warning: {damaged}'
    return {'cores': cores, **memory, 'cap': cap, 'seats': seats, 'bound': bound, 'text': text + note, **held}


WINDOWS = {'five_hour': 300, 'seven_day': 10080}  # #845: minutes; the usage windows both runtimes share


def _readings(root):
    """The saved readings, runtime to window to reading (.wuwei/windows.json, a cache)."""
    import json
    path = Path(root) / '.wuwei/windows.json'
    try:
        found = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f'windows.json: {exc}') from exc
    if not isinstance(found, dict) or not all(isinstance(rows, dict) for rows in found.values()):
        raise ValueError('windows.json: not a table of runtimes; remove it, the next readings rewrite it')
    return found


def save_windows(root, runtime, readings):
    """#845: merge a runtime's valid readings ({window: {used_percent, resets_at ISO}}) into the
    cache; anything else is outside data and dropped. Writes only on a change."""
    import json
    import math
    from wuwei import derive
    keep = {window: {'used_percent': row['used_percent'], 'resets_at': row['resets_at']}
            for window, row in (readings.items() if isinstance(readings, dict) else ())
            if window in WINDOWS and isinstance(row, dict)
            and type(row.get('used_percent')) in (int, float) and math.isfinite(row['used_percent'])
            and row['used_percent'] >= 0 and getattr(derive.when(row.get('resets_at')), 'tzinfo', None)}
    try:
        saved = _readings(root)
    except ValueError:
        saved = {}  # a damaged cache is replaced
    merged = {**saved, runtime: {**saved.get(runtime, {}), **keep}}
    if keep and merged != saved:
        workspace.atomic_write(Path(root) / '.wuwei/windows.json', json.dumps(merged, sort_keys=True) + '\n')


def windows(root, config, runtimes):
    """#845: room in whole seats per budgeted runtime of `runtimes`, {name: {room, until, text}}.
    A window's used tokens are the larger of its counted seat.usage tokens and the live reading's
    percent of its budget; room is (budget - used) // per-seat tokens, 0 at a reading of 100
    percent, None (no bound) without a budget and per-seat cost. The runtime takes its smallest
    room and the latest reset among its spent windows, else its binding window's reset.
    ponytail: only measured seats count (Claude gate sentinels report none); readings catch them."""
    import functools
    import statistics
    from datetime import timedelta
    from wuwei import derive, metrics
    now, default = workspace.now(), config['adapters']['runtime']
    days = sorted((Path(root) / '.wuwei/days').glob('*'), reverse=True)
    events = functools.cache(lambda day: metrics._events(day) or [])
    try:
        readings, warning = _readings(root), None
    except ValueError as exc:  # a damaged cache is ignored, never a blocked launch
        readings, warning = {}, exc
    found = {}
    for name in runtimes:
        if name not in config['budget']:
            continue
        parts, rooms, damaged, per_seat = [], [], None, False
        for window, minutes in WINDOWS.items():
            budget, length = config['budget'][name][window], timedelta(minutes=minutes)
            reading = readings.get(name, {}).get(window)
            reset = derive.when(reading.get('resets_at')) if isinstance(reading, dict) else None
            percent = reading.get('used_percent') if reset and reset > now else None
            if type(percent) not in (int, float):
                percent = reset = None
            if not budget and percent is None:
                continue
            if budget and per_seat is False:  # the history scan only for a budgeted window
                try:
                    tokens = lambda runtime: next((t for day in days if (t := metrics.seat_tokens(events(day), runtime, default))), None)
                    per_seat = tokens(name) or tokens(None)
                    per_seat = per_seat and max(1, round(statistics.median(per_seat)))
                except ValueError as exc:
                    per_seat, damaged = None, exc
            start, counted, earliest = (reset or now) - length, None, None
            if not damaged:
                try:
                    mine = [row for day in days if day.name >= str((start - timedelta(days=1)).date())
                            for row in events(day) if row['kind'] == 'seat.usage'
                            and row['payload'].get('runtime', default) == name and derive.when(row['ts']) >= start]
                    counted = sum(metrics.seat_tokens(mine))
                    earliest = min((derive.when(row['ts']) for row in mine), default=None)
                except (ValueError, KeyError, TypeError) as exc:
                    damaged = exc
            used = max(counted or 0, int(budget * percent // 100)) if percent is not None else counted
            room = (0 if percent is not None and percent >= 100 else
                    max(0, (budget - used) // per_seat) if budget and per_seat and not damaged else None)
            until = reset or (earliest or now) + length
            parts.append(f'{name} {window}' + (f' {used} of {budget} used' if budget and used is not None else '')
                         + (f' (reported {percent:g}%)' if percent is not None else '')
                         + (', per-seat tokens unmeasured' if budget and not per_seat and not damaged else '')
                         + ('' if room is None else f', room {room}' + (f' until {until.isoformat()}' if room == 0 else '')))
            if room is not None:
                rooms.append((room, until))
        parts += [f'warning: {exc}' for exc in (damaged, warning) if exc]
        spent = [until for room, until in rooms if room == 0]
        until = max(spent) if spent else min(rooms)[1] if rooms else None
        found[name] = {'room': min(rooms)[0] if rooms else None, 'until': until and until.isoformat(),
                       'text': '; '.join(parts)}
    return found


def route(row, default, left):
    """#845: the runtime a new build starts on: the policy row's runtime when it has room (or no
    bound), else its alternate when that has room, else the policy runtime, to wait."""
    primary, alternate = row.get('runtime') or default, row.get('alternate')
    fits = lambda name: left.get(name) is None or left[name] > 0
    return alternate if not fits(primary) and alternate and fits(alternate) else primary


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
    if found := second_opinion(config, row, effective):
        record['second_opinion'] = found
    return record


def second_opinion(config, row, tier):
    """The item's second-opinion gate, or None: off, a light tier, or (#873) none of the flags
    gates.second_opinion_when names."""
    second, when = config['gates']['second_opinion'], config['gates']['second_opinion_when']
    if second == 'off' or tier == 'light' or when and not any(row['flags'].get(name) for name in when):
        return None
    runtime, _, model = second.partition(':')
    return {'role': config['gates']['second_opinion_role'], 'runtime': runtime, 'model': model}


def _released(root, config, data, item):
    """#873: a recorded second opinion the config no longer selects leaves the item's tier
    record, so an item waiting only on it moves on; the state after it. One whose latest
    verdict blocks (FIX, PARK, ESCALATE or a blocks: yes finding) stays until it is answered."""
    gates = data['items'][item].get('gates') or {}
    if not gates.get('second_opinion') or second_opinion(config, data['items'][item], gates.get('tier')):
        return data
    gate = gate_set(data['items'][item])[-1]
    latest = _record(data, item, gate, 'delta') or _record(data, item, gate, 'initial')
    if latest and (latest['verdict'] != 'PASS' or latest['blocks']):
        return data
    state._write_state(lambda fresh: fresh['items'][item]['gates'].pop('second_opinion', None), root,
                       kind='gate.released', payload={'item': item, 'gate': gate})
    return state.read_state(root)


def _changes(root, config, row):
    """(repository settings, diff stat rows) of the item's worktree against its merge base."""
    from wuwei import commit_push
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


def capped(root, config, data, item):
    """The item's round cap when its rounds are spent, else None. D3, #904: the owner's resume
    after the park grants one more round, spent when that round opens (build.fix_opened)."""
    cap = max_rounds(config, data['items'][item])
    return cap if rounds_used(data, item) >= cap and not _resumed(root, item) else None


def rotate(data, item, used):
    """#623: the next round answers each gate's delta verdict, so it becomes the gate's initial
    record and the record it replaces is kept as round<used>. Every verdict reader keeps
    reading initial and delta."""
    verdicts = data['gate_verdicts']
    for gate in gate_set(data['items'][item]):
        (verdicts.get(f'{item}:{gate}:initial') or {}).pop('late', None)  # #902 D1: this round answers it
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


def rechecks(data, item, role, root=None):
    """#723: role runs the item's delta: its initial verdict was not PASS (#732), or it is the
    gate of the item's open polish round (before the PR). One rule for next_step, delta_due, receive and
    opinion. With root (#844, design 5.3) a PASS also reruns when the worktree HEAD moved past it
    other than by a recorded fix round."""
    row = data['items'][item]
    first = _record(data, item, role, 'initial')
    polish = row.get('polish') or {}
    if bool(first) and root is not None and first['verdict'] == 'PASS' and row.get('worktree'):
        from wuwei import derive
        if not derive.at_head(row, first['head'], derive.head(Path(root) / row['worktree'])):
            return True
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


def tracker_call(item, action, root=None, row=None):
    """Perform one tracker lifecycle update without blocking the local build loop. #842: it is
    a duty (create for a day item; claim, in_review and done with a recorded ticket): duty.due before
    the call, then duty.done when every step returned 0, or duty.skipped with the error (the
    adapter already retried). A duty already done on any day is not run again. row: the item
    record a create opens the ticket from when it is not in today's proposal."""
    from wuwei import tracker as hygiene
    root = workspace.find_workspace(root)
    ticket, duty, pr = item, None, None
    try:
        config = workspace.load_config(root)
        data = state.read_state(root)
        ticket = hygiene.ticket(data, item) or item
        if config['adapters']['tracker'] == 'none':
            result = registry.Result(2, reason='tracker adapter is none, so tracker updates are skipped; to reach the tracker, the owner sets adapters.tracker with bin/wuwei config set')
        else:
            if action not in ('create', 'claim', 'in_review', 'done'):
                raise ValueError('unknown tracker action; pass create, claim, in_review or done')
            name = f'tracker.{action}'
            if (hygiene.ticket(data, item) if action == 'create'
                    else hygiene.duty_done(root, item, name, ticket)):
                return registry.Result(0, reason=f'{item}: {name} already recorded')
            pr = data['items'].get(item, {}).get('pr')
            if action == 'create':
                if item in data['items']:  # a duty for a day item; any other subject is refused below
                    duty = {'item': item, 'duty': name, 'ticket': None}
                    state.append_event('duty.due', {**duty, 'command': f'wuwei tracker create {item}'}, root)
                result = hygiene.create(root, item, row=row)
                if result.exit == 0 and duty:
                    duty['ticket'] = ticket = result.data['id']
            else:
                if hygiene.ticket(data, item):
                    duty = {'item': item, 'duty': name, 'ticket': ticket}
                    state.append_event('duty.due', {**duty, 'command': f'wuwei tracker move {item} {action}'}, root)
                port = registry.load('tracker', config)
                if action == 'claim':
                    result = port.claim(ticket, root=root)
                else:
                    result = port.transition(ticket, config['tracker']['states'][action], root=root)
                    if action == 'in_review' and isinstance(result, registry.Result) and result.exit:
                        result = hygiene.relabel(port, root, config, item, ticket, result)  # #670
                    if isinstance(result, registry.Result) and result.exit == 0 and duty and pr:
                        kind = 'pr' if action == 'in_review' else 'close'
                        text = f'Pull request: {pr}.' if action == 'in_review' else f'Merged in {pr}.'
                        result = hygiene.duty_comment(root, config, port, ticket, f'{kind}:{item}:{ticket}:duty',
                                                      kind, f'[{workspace.day_dir(root).name} {item}] {text}')
            if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
                raise ValueError(f'invalid tracker result; {ADAPTER_DATA}')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = registry.Result(2, reason=f'tracker call unmeasured: {type(exc).__name__}')
    try:
        state.append_event('tracker.call', {'item': item, 'ticket': ticket, 'action': action,
                           'exit': result.exit, 'reason': result.reason or ''}, root)
        if duty and result.exit == 0:
            state.append_event('duty.done', {**duty, 'pr': pr}, root)
        elif duty:
            state.append_event('duty.skipped', {**duty, 'error': result.reason or 'failed'}, root)
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
    from wuwei import plan, specmode
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
    return (sessions.owner_answer(root, command, token),
            sessions.owner_card(command, detail, token, PARKS))


PARKS = 'The item parks.'


def _resumed(root, item):
    """True when the owner resumed the item after its last park and no fix round has opened
    since: the resume is the owner's Yes to the verdict that parked it. #904: a build check
    answers the resume of a build park, so it ends the grant too."""
    from wuwei import watch
    ends = ('plan.disposed', 'build.fix_opened', 'build.checked')
    last = {}
    for number, row in enumerate(watch.records(workspace.day_dir(root) / 'events.jsonl')):
        if row['payload'].get('item') == item and row['kind'] in ('plan.resumed', *ends):
            last[row['kind']] = number
    return last.get('plan.resumed', -1) > max(last.get(kind, -1) for kind in ends)


def _blocked(root, data, item):
    """(the stopped builder's Blocked: line, its agent id) when the line is not none, else None."""
    from wuwei import watch
    ids = {seat.get('agent_id') for seat in brief.seats(data).values()
           if seat['item'] == item and seat['role'] == 'builder' and seat['status'] == 'stopped'} - {None}
    # #902: a builder bound by its build record keeps its agent id there, not on the seat
    ids |= {(data.get('builds', {}).get(item) or {}).get('agent_id')} - {None}
    found = [(str(row['payload'].get('fields', {}).get('Blocked', '')).strip(), row['payload']['agent_id'])
             for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
             if row['kind'] in ('retro.captured', 'retro.gap') and row['payload'].get('agent_id') in ids]
    return found[-1] if found and found[-1][0] and found[-1][0].casefold() != 'none' else None


def _blocked_card(root, data, item, build=False):
    """(reason, the owner's answer, the card, the line) when a stopped builder's Blocked: line
    asks the owner, else None. Pure: next derives it, dispatch next acts on it. build (#902): the
    build at its checks asks first, on the card of build next."""
    stopped = _blocked(root, data, item)
    if not stopped:
        return None
    import hashlib
    from wuwei import sessions
    line, agent = stopped
    command = f"bin/wuwei {'build' if build else 'dispatch'} next " + shlex.quote(item)
    detail = (f'The {item} builder stopped on: {line}. Yes '
              + ('continues it on your answer' if build else 'sends it to its gates with your answer')
              + '; No parks the item.')
    token = hashlib.sha256(f'{agent}\n{line}'.encode()).hexdigest()[:12]
    return (f'builder blocked: {line}', sessions.owner_answer(root, command, token),
            sessions.owner_card(command, detail, token, PARKS), line)


def _head(result):
    """The first finding of a verdict on one line."""
    return ' '.join((result['findings'] or ['no finding'])[0].splitlines()[0].split())


def decide(root, data, config, item):
    """#902: the one gate decision of an item at gate or delta, read only (next derives it on the
    hook path; next_step executes it): {'step', 'why', ...}. Steps: gone (its worktree), recheck
    (HEAD past the checked head), build (its build is not done), ask and park (an owner card or
    a park; cap parks for the owner's resume), gates (roles to read the current head: round,
    stale, current, note), polish (offer), raise (notes), fix (roles, round)."""
    from wuwei import derive
    row = data['items'][item]
    if tree := derive.gone(root, row):
        return {'step': 'gone', 'why': f'its worktree {tree} is gone or its HEAD unreadable'}
    build = data.get('builds', {}).get(item)
    moved = build and build['status'] == 'done' and build.get('checked') and derive.head(build['worktree'])
    if moved and moved != build['checked']:  # #901 review: a gate reads only a checked head
        return {'step': 'recheck', 'head': moved, 'why': f'HEAD {moved[:12]} is past its checked head'}
    if build and build.get('checked') and build['status'] != 'done':  # #901: checks pass before gates
        return {'step': 'build', 'why': f'its build is {build["status"]}, not done'}
    phase, note = row['phase'], ''
    if phase == 'gate' and not _resumed(root, item) and (blocked := _blocked_card(root, data, item)):
        reason, answer, card, line = blocked
        if answer == 'No':
            return {'step': 'park', 'why': reason}
        if answer != 'Yes':
            return {'step': 'ask', 'why': reason, 'card': card}
        note = f"\nOwner decision: the owner said Yes to the builder's Blocked: line: {line}"
    gates = gate_set(row)
    current = derive.head(Path(root) / row['worktree']) if row.get('worktree') else None
    if phase == 'delta' and (late := [role for role in gates if _record(data, item, role, 'initial') is None]):
        # #902: a gate with no initial verdict reads the current head first, on a fresh seat
        return {'step': 'gates', 'roles': late, 'round': 'initial', 'stale': late, 'current': current,
                'note': note, 'why': f"{', '.join(late)} has no initial verdict"}
    round_name = 'initial' if phase == 'gate' else 'delta'
    # #902 review F1, D1: a late initial that is not a PASS (received in this delta) is judged as an
    # initial verdict, outside the delta re-read, until a fix round opens (rotate clears the flag);
    # a late PASS takes the ordinary stale and recheck path
    late = [role for role in gates if round_name == 'delta' and _record(data, item, role, 'delta') is None
            and (_record(data, item, role, 'initial') or {}).get('late')
            and _record(data, item, role, 'initial')['verdict'] != 'PASS']
    roles = list(gates) if round_name == 'initial' else [
        role for role in gates if role not in late and rechecks(data, item, role, root)]
    stale = [role for role in roles if _record(data, item, role, round_name) is not None
             and derive.counted(root, row, _record(data, item, role, round_name), current) is None]
    if missing := [role for role in roles if _record(data, item, role, round_name) is None or role in stale]:
        return {'step': 'gates', 'roles': missing, 'round': round_name, 'stale': stale, 'current': current,
                'note': note, 'why': f"{', '.join(missing)} to run at the current head"}
    results = {**{role: _record(data, item, role, round_name) for role in roles},
               **{role: _record(data, item, role, 'initial') for role in late}}
    roles += late
    asked = [role for role in roles if results[role]['verdict'] in ('PARK', 'ESCALATE')]
    blocking = [role for role in roles if role in asked or (
        results[role]['verdict'] == 'FIX' if round_name == 'initial' or role in late else results[role]['blocks'])]
    if not blocking:
        notes = [note for result in results.values() for note in result['notes']]
        offer = round_name == 'initial' and polish_offer(config, row, roles, list(results.values()),
                                                         rounds_used(data, item))
        if offer:  # #723: a pass with notes may offer a polish round
            return {'step': 'polish', 'offer': offer, 'why': 'every gate passed with review notes'}
        return {'step': 'raise', 'notes': notes, 'why': 'every gate passed at the current head'}
    if cap := capped(root, config, data, item):  # #623: a park with its finding at the cap
        findings = results[blocking[0]]['findings']
        finding = next((text for text in findings if re.search(verdict.BLOCKS_YES, text, re.I)),
                       (findings or ['none'])[0])
        return {'step': 'cap', 'why': (
            f'round cap {cap} reached: {blocking[0]} still blocks: {" ".join(finding.splitlines()[0].split())}; '
            'unpark after a design change that closes it is recorded in the spec')}
    resumed = _resumed(root, item)  # a resume is the owner's Yes to the verdict that parked it
    if (parks := [role for role in asked if results[role]['verdict'] == 'PARK']) and not resumed:
        return {'step': 'park', 'why': f"gate {parks[0]} PARK: {_head(results[parks[0]])}"}
    if asked and not resumed:  # ESCALATE: the owner decides on the Owner step card of dispatch next
        answer, card = _asked(root, data, item, results, asked, round_name)
        reason = f"gate {asked[0]} {results[asked[0]]['verdict']}: {_head(results[asked[0]])}"
        if answer == 'No':
            return {'step': 'park', 'why': reason}
        if answer != 'Yes':
            return {'step': 'ask', 'why': reason, 'card': card}
    return {'step': 'fix', 'roles': blocking, 'records': [results[role] for role in blocking],
            'why': f'gate {blocking[0]} asks for a fix'}


def next_step(item, root=None):
    """Return the next planner action without launching a seat: decide's step, executed."""
    root = workspace.find_workspace(root)
    data = state.read_state(root)
    row = _item(data, item)
    phase = row['phase']
    if phase in ('parked', 'escalated'):  # only the owner resumes it, on plan resume's card
        return {'action': 'escalate', 'reason': (row.get('disposition') or {}).get('reason') or f'{item} is {phase}',
                'command': 'wuwei plan resume ' + shlex.quote(item)}
    from wuwei import derive
    if phase == 'raised' and row.get('pr'):  # F1: a rebase or a push moved the PR past its verdicts
        pull = derive.listing(workspace.day_dir(root))['pulls'].get(row['pr']) or {}
        if moved := derive.moved(root, data, item, pull.get('head')):
            if cap := capped(root, workspace.load_config(root), data, item):
                return _parked(root, item, f"round cap {cap} reached: PR {row['pr']} head moved to "
                               f'{moved[:12]} past its verdicts')
            from wuwei.commands import build
            build.open_fix(item, f'The PR head moved to {moved[:12]} outside a fix round (a rebase or a '
                           'push). Bring the worktree to that head, rerun the fast checks there and change '
                           'nothing else unless they fail; every gate then re-reads it.', root=root, start=moved)
            return _fix(item, [])
    if phase not in ('gate', 'fix', 'delta'):
        raise Refused(f'{item} is in phase {phase}, not at a gate; run bin/wuwei build next {item}')
    config = workspace.load_config(root)
    found = decide(root, data, config, item) if phase != 'fix' else {'step': 'fix'}
    if found['step'] == 'gone':  # F5
        raise Refused(f'{item} worktree {derive.gone(root, row)} is gone or its HEAD unreadable; no verdict counts '
                      f'there; the owner decides on the card of bin/wuwei next: park {item} or restore the worktree')
    if found['step'] == 'recheck':
        from wuwei.commands import build as builds
        return builds.recheck_moved(item, root, data['builds'][item], found['head'])
    if phase != 'fix':
        try:
            brief.gate_ready(data, item)
        except brief.Refused as exc:
            raise Refused(str(exc)) from exc
        build = data.get('builds', {}).get(item)
        if found['step'] == 'build':
            raise Refused(f'{item} build is {build["status"]}, not done; run bin/wuwei build next {item} for its step, '
                          f'then bin/wuwei dispatch next {item}')
        # #901: a build done without a seat (build reconcile) has stood down as well
        if build is None and not any(seat['item'] == item and seat['role'] == 'builder'
                                     and seat['status'] == 'stopped' for seat in brief.seats(data).values()):
            raise Refused(f'builder must stand down before gates; wait for the {item} builder to stop, then run bin/wuwei dispatch next {item}')
        if found['step'] in ('ask', 'park') and found['why'].startswith('builder blocked: '):
            return _act(root, item, found)
    if phase == 'gate' and not row['gates'] and all(
            _record(data, item, role, 'initial') is None for role in ROLES):
        record = tier(root, config, row)

        def update(fresh):
            if _item(fresh, item)['gates']:
                raise Refused(f'gate tier changed during dispatch; {RACE}')
            fresh['items'][item]['gates'] = record
        state._write_state(update, root, kind='gate.tiered',
                           payload={'item': item, **record})
    data = _released(root, config, state.read_state(root), item)
    row = data['items'][item]
    if phase == 'gate':
        # Design 5.10 backstop: no gates for an item reached by a manual transition with a gap.
        from wuwei import specmode
        code, reason = specmode.check(root, config, item, row, (root / row['worktree']).resolve()
                                      if row.get('worktree') else None, build=True, where='dispatch')
        if code:
            raise Refused(reason)
    if phase == 'fix':  # #902: a gate missing its initial verdict reads the head in the delta
        gates = gate_set(row)
        if any(_record(data, item, role, 'delta') is not None for role in gates):
            return _parked(root, item, 'fix round already used')
        return _fix(item, [role for role in gates if rechecks(data, item, role, root)])
    return _act(root, item, decide(root, data, config, item), data)


def _act(root, item, found, data=None):
    """#902: next_step's execution of one decide step."""
    step = found['step']
    if step == 'gates':
        commands = []
        action = {'action': 'gates', 'roles': found['roles'],
                  'seats': _seats(root, data, item, found['roles'], found['round'], commands,
                                  found['note'], found['stale'], found['current'])}
        if commands:  # #551: the exact brief and receive steps, never a remembered action
            action['commands'] = commands
        row = data['items'][item]
        return {**action, 'tier': row['gates']} if row['phase'] == 'gate' and row['gates'] else action
    if step == 'polish':
        if workspace.load_config(root)['gates']['polish'] == 'always':
            return _open_polish(root, item, found['offer'])
        return {'action': 'polish', **found['offer'], 'command': 'wuwei dispatch polish ' + shlex.quote(item),
                'skip': 'wuwei dispatch skip-polish ' + shlex.quote(item)}
    if step == 'raise':
        return raise_action(root, data, item, found['notes'])
    if step in ('cap', 'park'):  # a cap park asks the owner's resume; a PARK or the owner's No does not
        return _parked(root, item, found['why'], ask=step == 'cap')
    if step == 'ask':
        return {'action': 'escalate', 'reason': found['why'], 'command': 'wuwei dispatch next ' + shlex.quote(item),
                'card': found['card']}
    from wuwei.commands import build
    build.open_fix(item, _fix_feedback(found['roles'], found['records']), root=root)
    return _fix(item, found['roles'])


def raise_action(root, data, item, notes):
    """#783: raise in the gate shape (#551): the shepherd's brief command, then its launch."""
    if (pr := data['items'][item].get('pr')) in data.get('claimed_prs', ()):  # #879: back to its branch
        return {'action': 'run', 'command': f'wuwei pr act {pr} --push', 'notes': notes}
    # #902: a raise shepherd that stopped with no PR is retried on a second seat, once more per
    # owner resume; then the owner decides on the resume card. ponytail: a count, not a reason.
    from wuwei import watch
    resumes = sum(row['kind'] == 'plan.resumed' and row['payload'].get('item') == item
                  for row in watch.records(workspace.day_dir(root) / 'events.jsonl'))
    names = [f'shepherd-{item}', *(f'shepherd-{item}-{number}' for number in range(2, 3 + resumes))]
    name = next((name for name in names if data['seats'].get(name, {}).get('status') in (None, 'running')), None)
    if name is None:
        return _parked(root, item, f'shepherd stopped without raising the PR: {", ".join(names)}')
    if name in data['seats']:
        return {'action': 'wait', 'reason': f'{name} is raising the PR; its SubagentStop records it'}
    body = '\n'.join([SHEPHERD_BODY.format(item=item), *(f'Review note: {note}' for note in notes)])
    return {'action': 'raise', 'notes': notes, 'seats': [], **_seat(root, data, item, name, body)}


def _seat(root, data, item, name, body):
    """The shepherd seat's next step: its brief command while the brief is missing, then its
    launch while the seat is not registered, else None (it ran)."""
    path = workspace.day_dir(root) / 'briefs' / f'{name}.md'
    worktree = data['items'][item].get('worktree') or str(root)
    if not path.is_file():
        return {'commands': [f'wuwei seat brief shepherd {item} {name} --worktree {shlex.quote(worktree)} '
                             '--body ' + shlex.quote(body)]}
    if name not in data['seats']:
        return {'seats': [brief.seat_action('shepherd', path, worktree, root)]}
    return None


SHEPHERD_THREADS = (
    'Answer the review activity on {pr} for {item}. Run bin/wuwei pr act {pr}: it prints the next owed '
    'reply with its thread id, the question and every owed id. Read the thread and classify it against '
    'the item promise (Approved as). Answer each owed id with one of: bin/wuwei pr act {pr} --thread <id> '
    '--reply "<answer with evidence>"; --fix "<what the item promised and what is wrong>" when it asks a '
    'change inside the promise (a fix round opens); --scope "<why it is outside the promise>" when it '
    'asks a change outside it (the owner decides on the Owner step card it prints; hand it back). Repeat '
    'until pr act prints nothing owed; that read records the duty. Never merge.')


def shepherd_action(root, item):
    """#906: the shepherd seat that answers the item's review activity, once per activity revision
    (its seat name carries it): the brief command, then the seat launch."""
    from wuwei import derive
    data = state.read_state(root)
    pr = data['items'][item]['pr']
    name = derive.shepherd_seat(item, derive.listing(workspace.day_dir(root))['pulls'].get(pr) or {})
    return {'action': 'shepherd', 'seats': [], **(_seat(root, data, item, name, SHEPHERD_THREADS.format(
        pr=pr, item=item)) or {'action': 'wait', 'reason': f'{name} already ran for this review activity'})}


def gate_step(item, root):
    """#666, #902: what dispatch next decides, a fix round it opened answered by its builder
    action (#614); the one resolver of next's gate launches and of build next past its build."""
    action = next_step(item, root)
    return state.read_state(root)['builds'][item]['action'] if action['action'] == 'fix' else action


def resolve_offer(root, launch):
    """#844: one launch of the derived next resolved into its action, through the resolver its
    command names; the resolvers append their loop records. #902: the action is kept as the
    resolver answers it (a park, an owner card, a wait); next reads it, never a retry line."""
    from wuwei.commands import build
    item, command = launch['item'], launch['command']
    if launch['kind'] == 'shepherd':  # #906
        action = shepherd_action(root, item)
    elif command.startswith('wuwei build next '):
        action = build.step(item, root)
    elif command.startswith('wuwei dispatch next ') and command != 'wuwei dispatch next --all':
        action = gate_step(item, root)
    elif command.startswith('wuwei pr act '):  # #879: a claimed PR's fix round, else its plain run
        from wuwei import pr_actions
        action = pr_actions.launch(root, command.split()[-1])
        launch = {**launch, 'kind': 'fix' if action['action'] in ('launch', 'continue') else 'pr'}
    else:
        action = {'action': 'run', 'command': command}
    return {'kind': launch['kind'], **action}


def launch_set(root=None):
    """The turn's launch set over the derived next's launches (#844): gate, fix, raise and
    build steps first, then planned items; builders within CAP, launches within the free
    host.seats."""
    from collections import Counter
    from datetime import timedelta
    from wuwei import derive
    from wuwei.commands import build
    from wuwei.commands.next import approved, building as holders, slot
    root = workspace.find_workspace(root)
    data, config = state.read_state(root), workspace.load_config(root)
    items = data['items']
    running = [seat for seat in brief.seats(data).values() if seat['status'] == 'running']
    live = brief.live(data)  # #898: only registered seats that have not handed back hold a slot
    # #528: capacity re-derives at every sweep; the day state keeps the snapshot.
    limits = host(root, config, running=len(live), policy=data['seat_policy'])
    # #845: seats each runtime's windows still carry, less its running seats and build loops
    policies = [row for row in data['seat_policy'].values() if isinstance(row, dict)]
    second = config['gates']['second_opinion']  # #910: a second opinion takes its runtime's room
    rooms = windows(root, config, {config['adapters']['runtime'], *(row.get(key) for row in policies
                                                                    for key in ('runtime', 'alternate')),
                                   second.partition(':')[0] if second != 'off' else None} - {None})
    taken = Counter([(seat['role'] == 'builder' and (data.get('builds', {}).get(seat.get('item')) or {}).get('runtime'))
                     or seat.get('runtime') or data['seat_policy'].get(seat['role'], {}).get('runtime')
                     or config['adapters']['runtime'] for seat in live]
                    + [build['runtime'] for build in data.get('builds', {}).values() if state.looping(build)])
    windows_left = {name: row['room'] and max(0, row['room'] - taken[name]) for name, row in rooms.items()}
    hold = lambda runtime: {'action': 'wait', 'reason': f"{runtime} usage window has no room for a seat "
                            f"({rooms[runtime]['text']})" + (f"; it resets at {rooms[runtime]['until']}" if rooms[runtime]['until'] else ''),
                            **({'until': rooms[runtime]['until']} if rooms[runtime]['until'] else {})}
    cap, bound = limits['cap'], limits['bound']
    ceiling = limits['seats']
    # #658: under the memory rule every sweep records its reading; CAP smooths over them
    if data['gate_approved'] and ((data['cap'], data['cap_bound']) != (cap, bound) or 'reading' in limits):
        state._write_state(lambda fresh: fresh.update(cap=cap, cap_bound=bound), root,
                           kind='cap.derived', payload={'cap': cap, 'bound': bound, 'text': limits['text'],
                                                        **{key: limits[key] for key in ('reading',) if key in limits}})
    free = start = ceiling - len(live)
    busy = {seat['item'] for seat in running}
    names = [name for name in approved(data) if name not in busy]
    goal = lambda name: items[name].get('goal', 'unplanned')
    entries = []

    def add(name, call, kind='build'):
        nonlocal free
        try:
            value = {'kind': kind, **call()}
        except (Refused, ValueError, build.PortExit) as exc:
            value = {'kind': kind, 'action': 'refused', 'reason': str(exc)}
        if value['action'] in ('launch', 'continue') and value.get('runtime') not in ('claude', None):
            # #845: a builder bound to another runtime runs its own loop, in the background
            value = {'kind': kind, 'action': 'run', 'runtime': value['runtime'], 'command': 'wuwei build ' + ' '.join(
                map(shlex.quote, (name, value['brief'], value['worktree'])))}
        started = derive.when(((data.get('builds', {}).get(name) or {}).get('loop') or {}).get('started_at'))
        if value['action'] == 'run' and started and (again := started + timedelta(seconds=121)) > workspace.now():
            # #845 D2, E1: a loop that ended within two minutes of its start runs again after them
            value = {'action': 'wait', 'until': again.isoformat(),
                     'reason': f'{name} build loop ended right after it started; it runs again at {again.isoformat()}'}
        launches = len(value.get('seats', [])) if 'seats' in value else int(
            value['action'] in ('launch', 'continue', 'start') or value['action'] == 'run' and 'runtime' in value)
        seats, runtime = 'seats' in value, value.get('runtime')
        if launches and 'held' in limits:  # #898: below the memory floor no seat starts; re-check soon
            value = {'action': 'wait', 'reason': limits['held'],
                     'until': (workspace.now() + timedelta(minutes=1)).isoformat()}
        elif kind in ('build', 'fix') and launches and not seats and not slot(
                fresh := state.read_state(root), name, cap):  # #910: as the guard, on this sweep's writes
            value = {'action': 'wait', 'reason': f'CAP {cap} reached: build slots held by '
                     f"{', '.join(holders(fresh)[:cap])}; this builder launches when one hands off"}
        elif seats and launches:  # #910: the seats that fit launch; the rest after these verdicts
            fit, rest = [], []
            for seat in value['seats']:
                room = windows_left.get(seat.get('runtime'))
                if len(fit) < free and room != 0:
                    fit.append(seat)
                    if room is not None:
                        windows_left[seat['runtime']] -= 1
                else:
                    rest.append(seat)
            spent = next((seat['runtime'] for seat in rest if windows_left.get(seat.get('runtime')) == 0), None)
            free -= len(fit)
            if not fit:
                value = hold(spent) if spent and free > 0 else {'action': 'wait', 'reason': (
                    f'{launches} launch(es) wait for the {max(free, 0)} free of host.seats={ceiling}; '
                    'they launch as running seats stop')}
            elif rest:
                value = {**value, 'seats': fit, 'deferred': len(rest), 'reason': (
                    f'{len(fit)} of {launches} seats launch now; the rest wait for '
                    + (f'the {spent} usage window ({rooms[spent]["text"]})' if spent else f'host.seats={ceiling}')
                    + ' and launch after these verdicts are received')}
        elif launches and windows_left.get(runtime) == 0:
            value = hold(runtime)
        elif launches > free:
            value = {'action': 'wait', 'reason': (
                f'{launches} launch(es) do not fit the {max(free, 0)} free of host.seats={ceiling}; '
                'they launch next turn, after running seats stop')}
        elif launches:
            free -= launches
            if windows_left.get(runtime) is not None:
                windows_left[runtime] -= 1
        entries.append({'item': name, 'goal': goal(name), **value})

    offered = [launch for launch in derive.offers(data, root, config)['launches']  # seat steps only
               if derive.seated(data, launch)]
    for launch in sorted((launch for launch in offered if launch['command'] != 'wuwei dispatch next --all'),
                         key=lambda launch: launch['command'].startswith('wuwei build next ')):
        add(launch['item'], lambda: resolve_offer(root, launch), launch['kind'])
    names = [name for name in names if not derive.waits_on(root, data, name)]  # #637
    # #910: the one build slot count, read after the offers (a fix round opened this sweep holds
    # one); #648: a held item takes no seat
    seated = holders(state.read_state(root))
    building = len(seated)
    share = Counter(data.get('goal_seats', {}))
    share.subtract(goal(name) for name in seated)
    first, rest = [], []
    for name in (name for name in names if items[name]['phase'] == 'planned'):
        (first if share[goal(name)] > 0 else rest).append(name)
        share[goal(name)] -= 1
    briefed = {row['payload'].get('item') for row in brief.events(root)
               if row['kind'] == 'brief written' and row['payload'].get('role') == 'builder'}
    def partial(name):  # #910: an initial gate batch runs while the rest of its set is not launched
        gates = [seat for seat in data['seats'].values() if seat['item'] == name and seat['role'].startswith('sentinel-')]
        try:
            return items[name]['phase'] == 'gate' and len(gates) < len(gate_set(items[name]))
        except ValueError:  # a damaged gate record refuses the item at its own step, never the set
            return False
    gate_waits = 'held' not in limits and (any(  # #898: a memory hold holds the builds itself
        row['action'] == 'wait' or row.get('deferred') for row in entries  # #910: or launches part of its set
        if items[row['item']]['phase'] in ('gate', 'delta')) or any(
        partial(seat['item']) for seat in running if seat['role'].startswith('sentinel-')))
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
    index = 0
    for name in (name for name in first + rest if name not in skip):
        runtime = route(data['seat_policy'].get('builder', {}), config['adapters']['runtime'], windows_left)
        if gate_waits:
            entries.append({'item': name, 'goal': goal(name), 'action': 'wait', 'reason': (
                'a gate waits for seats; gates launch before new builds so ready items merge first')})
        elif windows_left.get(runtime) == 0:  # F4: held before build next binds, moves or claims it
            entries.append({'item': name, 'goal': goal(name), **hold(runtime)})
            continue
        elif building + index >= cap:
            entries.append({'item': name, 'goal': goal(name), 'action': 'wait', 'reason': (
                f'CAP {cap} reached ({building} building); bin/wuwei next names the seat '
                'expected to free first')})
        elif 'held' in limits:  # #898 F1: held before build next binds, moves or claims it
            entries.append({'item': name, 'goal': goal(name), 'action': 'wait', 'reason': limits['held'],
                            'until': (workspace.now() + timedelta(minutes=1)).isoformat()})
        elif name in briefed:
            add(name, lambda: build.next_action(name, root=root, runtime=runtime))
        else:
            add(name, lambda: {'action': 'start', 'commands': starts[name], 'runtime': runtime})
        index += 1
    for entry in entries:
        entry.setdefault('kind', 'build')
    return {'action': 'set', 'cap': cap, 'bound': bound,
            'capacity': limits['text'] + ''.join(f"; {row['text']}" for row in rooms.values() if row['text']),
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
    from wuwei import plan, specmode
    row = candidate(root, name) or {}
    item = state.read_state(root)['items'].get(name, {})
    scope = item.get('title') or row.get('scope')  # #908: the item's recorded promise first
    evidence = item.get('evidence') or row.get('evidence')
    body = (f"Implement {name}: {scope}." + (f' Evidence: {evidence}.' if evidence else '') if scope
            else f"Implement {name} as today's plan records it.")
    tree = item.get('worktree') or f'worktrees/{name}'  # #908: an adopted worktree is the item's
    repo = item.get('repo') or row.get('repo')  # #868: the owner's plan add names it
    add = [] if (root / tree).exists() else [f'wuwei worktree add {name}']
    if add and len(repos) > 1:  # #603: worktree add exits 2 without --repo here
        names = [repo['name'] for repo in repos]
        if repo not in names:
            return [f'wuwei plan park {name} --reason ' + shlex.quote(
                f'names no configured repository ({", ".join(names)}); run wuwei worktree add {name} '
                f'--repo <one of {", ".join(names)}>, then wuwei plan resume {name}')]
        add = [add[0] + ' --repo ' + shlex.quote(repo)]
    checkout = plan.checkout(root, repos, repo, tree)
    try:  # #864: a brief that cannot be written parks the item, so it holds no CAP seat
        if 'governed_by' in item and checkout is not None:  # the brief's own read of it
            specmode.brief_block(workspace.load_config(root), name, item, checkout)
    except ValueError as exc:
        return [f'wuwei plan park {name} --reason ' + shlex.quote(
            f'{name}: governed_by {item["governed_by"]}: {str(exc).split(";")[0]}; the owner fixes it '
            f'with wuwei plan set {name} governed_by=<path>, then wuwei plan resume {name}')]
    return add + [f'wuwei seat brief builder {name} builder-{name} --worktree {shlex.quote(tree)} --body '
                  + shlex.quote(body)]


def _seats(root, data, item, roles, round_name, commands, note='', stale=(), current=None):
    """Ready launch or continue actions for gate seats the planner has not started; the brief
    and receive commands still due go to commands. A stale role (#844: its verdict's head moved,
    or #902 it has no initial verdict in delta) and a delta whose seat is lost (#902) read the
    current head on a fresh seat, a launch the Agent guard accepts."""
    worktree = data['items'][item].get('worktree')
    actions = []
    rows = brief.events(root) if round_name == 'initial' else []

    def fresh(role):
        if not (current and worktree):
            return
        name = f'{base(role)}-{item}-{current[:7]}'
        logged = [row['payload'] for row in brief.events(root) if row['kind'] == 'brief written'
                  and row['payload'].get('name') == name]
        receive = 'wuwei dispatch receive ' + ' '.join(map(shlex.quote, (item, role, name))) + (
            ' --round delta' if round_name == 'delta' else '')
        first = _record(data, item, role, 'initial')
        feedback = (f"\nDelta review: the fix round changed {first['head']}..{current}. The {role} gate said "
                    f"{first['verdict']} at {first['head']}:\n" + '\n'.join(first['findings'] or ['no finding'])
                    + '\nA new finding on lines this fix round did not change is blocks: no, unless it is a '
                    'trust-boundary security finding.' if round_name == 'delta' and first else '')
        if not logged:
            commands.append(f'wuwei seat brief {base(role)} {item} {name} --gate --worktree '
                            f'{shlex.quote(worktree)} --body ' + shlex.quote(GATE_BODY.format(item=item) + note + feedback))
        elif name not in data['seats']:
            actions.append({**brief.seat_action('sentinel-' + base(role), root / logged[-1]['path'],
                                                logged[-1]['worktree'], root), 'receive': receive})
        elif data['seats'][name]['status'] == 'stopped':
            commands.append(receive)

    for role in roles:
        if role in stale and '@' not in role:  # review F2: a stale second opinion reruns through opinion
            fresh(role)
            continue
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
                commands.append(f'wuwei seat brief {role} {item} {role}-{item} --gate --worktree '
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
            if not delta_due(data, item, role, name, root):
                if not seat or seat['status'] not in ('running', 'stopped') or (
                        seat['status'] == 'stopped' and not seat.get('agent_id')):
                    fresh(role)  # #902, charter Evidence 6: the original seat is lost
                continue
            # #669: the fix round moved the head; record it so an in-session resume can
            # write a true Head: line ('head' stays the initial head for delta_due).
            worktree = data['items'][item]['worktree']
            head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                              str((root / worktree).resolve()), root=root)['sha']
            if seat.get('delta_head') != head:
                state._write_state(lambda fresh: fresh['seats'][name].update(delta_head=head),
                                   root, kind='gate.delta_head',
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


def delta_due(data, item, role, name, root=None):
    """#614: seat name is due its delta continue: the item is in delta, role's initial FIX came
    from that seat, no delta verdict yet, and the seat stopped with an agent id at the initial
    head (not continued since). One rule for _seats and the launch guard."""
    row = data['items'].get(item)
    first = _record(data, item, role, 'initial')
    seat = data['seats'].get(name)
    return bool(row and row['phase'] == 'delta' and first and rechecks(data, item, role, root)
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


def _fix_feedback(roles, records):
    return '\n'.join(f'Gate {role} {record["verdict"]}: fix only the blocking findings (blocks: yes) '
                     f'in {record["file"]}.' for role, record in zip(roles, records))


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
    state._write_state(update, root, kind='polish.skipped',
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
    key = f'{item}:{role}:{round_name}'
    # #902: a gate with no initial verdict in delta reads the current head first (decide)
    late = round_name == 'initial' and data['items'][item]['phase'] == 'delta' and key not in data['gate_verdicts']
    if data['items'][item]['phase'] != ('gate' if round_name == 'initial' else 'delta') and not late:
        raise Refused(f'gate round does not match item phase {data["items"][item]["phase"]};run bin/wuwei dispatch next {item} for the right round')
    if round_name == 'delta':
        first = _record(data, item, role, 'initial')
        if first is None or not rechecks(data, item, role, root):
            raise Refused(f'gate did not need a delta; drop --round delta, or run bin/wuwei dispatch next {item} for what is open')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise Refused('unsafe seat name; use the seat name that bin/wuwei dispatch next returned')
    seat = brief.seats(data).get(name)
    if not seat or seat['item'] != item or seat['role'] != sentinel or seat['status'] != 'stopped':
        raise Refused('matching sentinel must stand down before receive; wait for the seat to stop, then rerun the same bin/wuwei dispatch receive')
    runtime = role.partition('@')[2] or None
    if seat.get('runtime') != runtime or (runtime and not name.endswith('-' + runtime)):
        raise Refused(f'gate role {role} needs its own runtime seat; start it with bin/wuwei dispatch opinion {item}')
    from wuwei import derive  # #844: a stale receipt (its head moved) is replaced by the re-read
    row = data['items'][item]
    now = derive.head(Path(root) / row['worktree']) if row.get('worktree') else None
    replaced = data['gate_verdicts'].get(key)
    if replaced is not None and derive.counted(root, row, replaced, now) is not None:
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
    expected = (str(seat.get('delta_head') or seat.get('head') or '') if round_name == 'delta'
                else str(seat.get('delta_head') or '') if replaced is not None else '')
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
    if not late and any(record and record['head'] != head and record is not replaced
                        and derive.counted(root, row, record, now) is not None for record in current):
        raise Refused(f'gate HEAD differs from sibling verdict; rerun the odd gate on the current HEAD via bin/wuwei dispatch next {item}')
    if sentinel == 'sentinel-security' and data['items'][item]['flags']['agent_surface']:
        from wuwei import scanner
        if not trees or trees[0] == 'none':
            raise OSError('scanner: unmeasured: missing reviewed worktree; write the security brief again with --worktree <absolute path>, then receive the verdict again')
        merge_base = re.findall(r'^Merge-base: ([0-9a-fA-F]+)', brief_text, re.M)
        if not merge_base:
            raise OSError('scanner: unmeasured: the security brief has no Merge-base line; write the security brief again with --worktree <absolute path>, then receive the verdict again')
        changed = {row['path'] for row in brief.read(vcs.diff_stat, str(tree), merge_base[0], current_head, root=root)}
        findings = scanner.rows(tree, item, data['items'][item]['flags'],
                                workspace.load_config(root), root, changed)
        measured_head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                                   str(tree), root=root)['sha']
        if measured_head != current_head:
            raise OSError(f'scanner: unmeasured: worktree HEAD changed during audit; {RACE}')
        text = scanner.merge(text, findings)
        code, message = verdict.lint(text, class_sweep=True)
        if code:
            raise OSError(f'scanner: unmeasured: {message}; fix the verdict as named, then receive it again with bin/wuwei dispatch receive')
    result = re.search(verdict.VERDICT_ROW, text, re.M)[1]
    blocks = sorted(verdict.finding_blocks(text),  # #677: blocking findings first
                    key=lambda block: not re.search(verdict.BLOCKS_YES, block, re.I))
    notes = [block.strip() for block in blocks if not re.search(verdict.BLOCKS_YES, block, re.I)]
    # a late initial is recorded as a later round's, outside merge's round-one HEAD agreement
    value = {'item': item, 'role': role, 'round': 'delta' if late else round_name, **({'late': True} if late else {}),
             'verdict': result,
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
        if (fresh['items'][item]['phase'] != data['items'][item]['phase']
                or fresh['gate_verdicts'].get(key) != replaced):
            raise Refused(f'gate state changed during receive; {RACE}')
        fresh['gate_verdicts'][key] = value

    stale = _stale_scratch(text, brief_text, root)  # #734: before the write, so damage records nothing
    state._write_state(update, root, kind='gate.received',
                       payload={'item': item, 'role': role, 'round': round_name, 'verdict': result})
    from wuwei import scanner
    scanner.trace_sweep(root, workspace.load_config(root))  # #847: pages and parks; not this exit
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
    _item(data, item)
    data = _released(root, config, data, item)
    row = data['items'][item]
    second = (row.get('gates') or {}).get('second_opinion')
    if not second:
        raise Refused(f'item has no second opinion; the owner enables one with bin/wuwei config set gates.second_opinion')
    gate = gate_set(row)[-1]
    sentinel = 'sentinel-' + base(gate)
    round_name = {'gate': 'initial', 'delta': 'delta'}.get(row['phase'])
    if round_name is None:
        raise Refused(f'item phase {row["phase"]} has no second-opinion round; run bin/wuwei dispatch next {item} for the current step')
    from wuwei import derive  # #902 review F2: a stored verdict answers only while it counts at HEAD
    kept = _record(data, item, gate, round_name)
    current = derive.head(Path(root) / row['worktree']) if row.get('worktree') else None
    if kept and derive.counted(root, row, kept, current) is not None:
        return kept
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
    if seat is None or seat['status'] != 'running':
        running = len(brief.live(data))  # #898
        ceiling = host(root, config, running=running, policy=data['seat_policy'])['seats']  # #528
        if running >= ceiling:
            raise Refused(f'running seats at host seat ceiling host.seats={ceiling}; wait for a seat to finish. Or the owner raises host.seats with bin/wuwei config set')
        head = brief.read(registry.load('vcs', config).head, row['worktree'], root=root)['sha']
        if round_name == 'delta' and seat is None:
            raise Refused(f'second-opinion seat is missing; run bin/wuwei why {item}, then bin/wuwei dispatch next {item}')
        if seat is None or round_name == 'initial' and (seat['status'] == 'unmeasured' or seat.get('failed') or kept):
            # #871: a failed or unmeasured seat has no thread to continue; it starts again
            if seat and seat['status'] == 'unmeasured' and seat.get('job'):  # one job per verdict file
                found = build._data(runtime.status(seat['job'], root=root), 'status')
                if found.get('status') in ('queued', 'running'):
                    build._data(runtime.cancel(seat['job'], root=root), 'cancel')
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
            if ((data.get('builds', {}).get(item) or {}).get('runtime')  # #845: a routed build's record
                    or data['seat_policy'].get('builder', {}).get('runtime')) == second['runtime']:
                raise Refused('second opinion cannot resume on the builder runtime; set gates.second_opinion to a runtime other than the builder. The owner runs bin/wuwei config set')
            feedback = (_recheck_feedback(row, first, head=head) if round_name == 'delta' else
                        'Your verdict was rejected by the verdict lint. Reply with your whole verdict, '
                        'rewritten to the verdict format, as your final message, in plain lines, not '
                        'in a code block; WUWEI writes it to '
                        f'{directory.relative_to(root)}/decisions/gate-{name}.md.')  # #871 L1
            ci = brief.ci_block(row.get('ci_jobs', ()), root / row['worktree']) if round_name == 'delta' else ''
            feedback += '\n' + ci if ci else ''  # #733
            job = build._data(runtime.continue_job(seat['job'], feedback, root=root), 'continuation')
        seat = {'id': name, 'role': sentinel, 'item': item, 'brief': relative, 'head': head,
                'status': 'running', 'started_at': workspace.now().isoformat(),
                'runtime': second['runtime'], 'model': second['model'], 'job': job}
        state._write_state(lambda fresh: fresh['seats'].update({name: seat}), root,
                           kind='seat launched', payload={'name': name, 'item': item})
    try:
        status = build.wait(runtime, seat['job'], config, root)
    except RuntimeError as exc:  # #871: a failed job frees its host seat; the rerun relaunches
        state._write_state(lambda fresh: fresh['seats'][name].update(
            status='stopped', stopped_at=workspace.now().isoformat(), failed=str(exc)), root,
            kind='seat stopped', payload={'name': name, 'failed': str(exc)})
        raise
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
    state._write_state(stop, root, kind='seat.usage',
                       payload={'item': item, 'role': sentinel, 'gate': gate, 'usage': usage,
                                'runtime': second['runtime']})
    if result.get('windows'):
        save_windows(root, second['runtime'], result['windows'])
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
