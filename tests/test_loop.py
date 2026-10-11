"""Characterise the loop before the derived next (#844).

Three parts, run against today's `next`:

1. A property test over generated item states. Each case is a world (the plan file, the
   worktree, the builder seat, the verdict files, the round count, the cached PR listing and the
   outward duties) that `materialise` writes as the day files today's commands would have left.
   An oracle says what the loop must offer for that world; each invariant of #844 is one test.
2. One test per recorded scheduler dead end and state drift case from the two study days.
3. Deleting state.json between two `next` calls changes no answer.

Every assertion today's `next` violates is xfail(strict=True) with the gap as its reason, so the
suite stays green today and each xfail must turn into a pass in the rewrite. The rewrite owns
`materialise` (where the derived next reads its inputs) and `answer` (how its output reads as
offers); the worlds, the oracle and the invariants stay.
"""

import json
import random
import re
import subprocess

import pytest

from wuwei import brief, dispatch, state, tracker, verdict, workspace
from wuwei.commands import next as next_command
from wuwei.registry import Result


NOW = '2026-10-11T10:00:00+00:00'
SEED, CASES = 844, 300
REPO = 'example/project'
GATE_KINDS = ('absent', 'PASS', 'FIX', 'PARK', 'ESCALATE', 'malformed', 'stale')
PR_KINDS = ('pending', 'red', 'green')
CAP_ROUNDS = 2  # gates.max_rounds default (#623)
HEAD, OLD = 'a1b2c3d4e5f6', '0f9e8d7c6b5a'
ROLES = {'light': ['quality'], 'standard': ['arch', 'quality', 'security']}
FINDING = '- P1 | src/example.py:1 | fails on an empty input | blocks: yes\n'
ENDINGS = ('close', 'closed', 'retro', 'promote', 'retro-applied', 'report', 'done')


# --- worlds ---------------------------------------------------------------------------------

def item(name, stage='queued', plan='approved', tier='light', rounds=0, verdicts=None, pr=None,
         owner_merge=False, duties=None):
    """One item of a world. stage: queued, building (builder running), gating (builder
    stopped), raised or merged; a gating item's verdicts map its gates to GATE_KINDS."""
    started = plan == 'approved' and stage != 'queued'
    if stage in ('raised', 'merged') and verdicts is None:
        verdicts = {role: 'PASS' for role in ROLES[tier]}
    return {'name': name, 'plan': plan, 'stage': stage if plan == 'approved' else None, 'tier': tier,
            'worktree': started, 'builder': ('running' if stage == 'building' else 'stopped') if started else None,
            'verdicts': verdicts or {}, 'rounds': rounds,
            'pr': 'merged' if stage == 'merged' else pr, 'owner_merge': owner_merge, 'duties': duties or {}}


def world(rng):
    """One day: 1 to 4 items over the plan file, CAP 1 to 3."""
    items = []
    for index in range(rng.randint(1, 4)):
        plan = rng.choice(('planned', 'approved', 'approved', 'approved', 'parked'))
        stage = rng.choice(('queued', 'building', 'gating', 'gating', 'gating', 'raised', 'merged'))
        tier = rng.choice(tuple(ROLES))
        fields = {'tier': tier, 'rounds': 0 if stage == 'queued' else rng.randint(0, 3)}
        if stage == 'gating':
            fields['verdicts'] = {role: rng.choice(GATE_KINDS) for role in ROLES[tier]}
        if stage in ('raised', 'merged'):
            fields.update(rounds=min(fields['rounds'], CAP_ROUNDS), owner_merge=rng.random() < 0.3,
                          pr=rng.choice(PR_KINDS), duties={'ping': rng.random() < 0.5})
        if stage == 'merged':
            fields['duties']['tracker'] = rng.random() < 0.5
        items.append(item(f'item-{index + 1}', stage, plan, **fields))
    return {'cap': rng.randint(1, 3), 'items': items}


WORLDS = [world(random.Random(SEED * 1000 + case)) for case in range(CASES)]


# --- the day files today's commands would have left ------------------------------------------

def phase(row):
    """The phase today's commands record for the world (state.json, today's truth)."""
    if row['plan'] != 'approved':
        return 'parked' if row['plan'] == 'parked' else 'planned'
    if row['stage'] == 'building':
        return 'fix' if row['rounds'] else 'implement'
    if row['stage'] == 'gating':
        return 'delta' if row['rounds'] else 'gate'
    return {'queued': 'planned', 'raised': 'raised', 'merged': 'merged'}[row['stage']]


def verdict_text(kind):
    if kind == 'malformed':
        return 'Looks fine to me.\n'
    text = f"Verdict: {'PASS' if kind == 'stale' else kind}\nHead: {OLD if kind == 'stale' else HEAD}\n"
    return text + (FINDING if kind in ('FIX', 'ESCALATE', 'PARK') else '')


def record(name, role, kind, round_name):
    """The gate_verdicts row receive writes; a malformed file or an absent one records nothing,
    and a stale one is a PASS received before the builder moved the head."""
    result = 'PASS' if kind == 'stale' else kind
    blocks = result in ('FIX', 'ESCALATE', 'PARK')
    return {'item': name, 'role': role, 'round': round_name, 'verdict': result,
            'head': OLD if kind == 'stale' else HEAD, 'blocks': blocks, 'notes': [],
            'file': f'.wuwei/days/2026-10-11/decisions/gate-{role}-{name}.md',
            'findings': [FINDING.strip()] if blocks else []}


def materialise(root, day):
    """Write the world as the day files: plan.md, state.json (today's truth, the derived next's
    cache), the builder briefs, the verdict files, the worktree directories, the cached PR
    listing (prs.json) and the duty records (duty.recorded events). The doctor row already ran,
    so health never takes the answer."""
    directory = workspace.day_dir(root)
    (directory / 'decisions').mkdir(parents=True, exist_ok=True)
    (directory / 'briefs').mkdir(exist_ok=True)
    plan = ['# Plan']
    data = {**workspace.copy_data(state.DAY_DEFAULTS), 'gate_approved': True, 'cap': day['cap'],
            'planner_session_id': 'S', 'builds': {}}
    listing, events = [], [('next.action', {'state': 'x', 'action': 'run', 'item': '', 'named': [],
                                            'traces': 0, 'done': [['doctor', '']]})]
    for number, row in enumerate(day['items'], 1):
        name, current = row['name'], phase(row)
        plan.append(f"- {name}: {row['plan']}")
        entry = {'phase': current, 'status': 'queued' if current == 'planned' else 'running'}
        if row['plan'] != 'planned':
            data['approved_items'].append(name)
        if current == 'parked':
            entry.update(resume_phase='gate', disposition={'kind': 'parked', 'reason': 'parked by a verdict'})
        if row['worktree']:
            (root / 'trees' / name).mkdir(parents=True, exist_ok=True)
            entry.update(worktree=f'trees/{name}', head=HEAD,
                         gates={'tier': row['tier'], 'roles': ROLES[row['tier']]})
        if row['builder']:
            data['seats'][f'builder-{name}'] = {'item': name, 'role': 'builder', 'status': row['builder']}
            path = directory / 'briefs' / f'builder-{name}.md'
            path.write_text('Build the item.\n')
            # the record build next leaves (tests/test_pr_actions.completed_build's shape)
            data['builds'][name] = {
                'brief': str(path.relative_to(root)), 'worktree': str(root / 'trees' / name),
                'runtime': 'claude', 'repo': REPO, 'commands': ['test'], 'iteration': 1, 'repeats': 0,
                'signature': None, 'status': 'running' if row['builder'] == 'running' else 'done',
                'agent_id': f'agent-{name}', 'action': {'action': 'done'}, 'fix_rounds': row['rounds']}
        for role, kind in row['verdicts'].items():
            if kind != 'absent':
                (directory / 'decisions' / f'gate-{role}-{name}.md').write_text(verdict_text(kind))
                data['seats'][f'{role}-{name}'] = {'item': name, 'role': f'sentinel-{role}', 'status': 'stopped'}
            if current == 'delta':  # the round before: every gate asked for the fix
                data['gate_verdicts'][f'{name}:{role}:initial'] = record(name, role, 'FIX', 'initial')
            if kind not in ('absent', 'malformed'):
                round_name = 'delta' if current == 'delta' else 'initial'
                data['gate_verdicts'][f'{name}:{role}:{round_name}'] = record(name, role, kind, round_name)
        if row['pr']:
            entry.update(pr=f'{REPO}#{100 + number}', owner_merge=row['owner_merge'])
            data['raised_prs'].append(entry['pr'])
            listing.append({'ref': entry['pr'], 'item': name, 'state': row['pr'],
                            'owner_merge': row['owner_merge']})
        events += [('duty.recorded', {'item': name, 'duty': duty}) for duty, done in row['duties'].items() if done]
        data['items'][name] = entry
    (directory / 'plan.md').write_text('\n'.join(plan) + '\n')
    (directory / 'prs.json').write_text(json.dumps(listing))
    (directory / 'state.json').write_text(json.dumps(data))
    for kind, payload in events:
        state.append_event(kind, payload, root)


def configure(root, extra=''):
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text(
        f'[[repos]]\nname = "{REPO}"\npath = "project"\ndefault_branch = "main"\n'
        '[spec]\nengine = "none"\n[gates]\npolish = "never"\n' + extra)


def environment(patch, root):
    """The day's clock and workspace, and no subprocess: the loop reads files only."""
    def refuse(*args, **kwargs):
        raise AssertionError(f'a subprocess ran in the loop test: {args[:1]}')
    patch.setenv('WUWEI_NOW', NOW)
    patch.setenv('WUWEI_WORKSPACE', str(root))
    patch.delenv('WUWEI_SESSION_ID', raising=False)
    patch.setattr(subprocess, 'run', refuse)
    patch.setattr(subprocess, 'Popen', refuse)


# --- what the loop must offer ------------------------------------------------------------------

def oracle(day):
    """{'launches', 'duties', 'decisions'}: sets of (kind, item) the loop must offer."""
    launches, duties, decisions = set(), set(), set()
    free = day['cap'] - sum(row['stage'] == 'building' for row in day['items'])
    for row in day['items']:
        name, stage, capped = row['name'], row['stage'], row['rounds'] >= CAP_ROUNDS
        if stage == 'queued' and free > 0:
            launches.add(('build', name))
            free -= 1
        if stage == 'gating':  # today's precedence (dispatch.next_step); a stale PASS is no PASS
            kinds = set(row['verdicts'].values())
            if kinds & {'absent', 'malformed', 'stale'}:
                launches.add(('gates', name))
            elif kinds & {'FIX', 'PARK', 'ESCALATE'} and capped:
                decisions.add(('owner', name))
            elif 'PARK' in kinds:
                pass  # a PARK verdict parks the item in code, no card
            elif 'ESCALATE' in kinds:
                decisions.add(('owner', name))
            elif 'FIX' in kinds:
                launches.add(('fix', name))
            else:
                launches.add(('raise', name))
        if stage == 'raised' and row['pr'] == 'red':
            (decisions if capped else launches).add(('owner' if capped else 'fix', name))
        if stage == 'raised' and row['pr'] == 'green':
            (decisions if row['owner_merge'] else launches).add(('owner' if row['owner_merge'] else 'merge', name))
        if stage in ('raised', 'merged') and not row['duties'].get('ping'):
            duties.add(('ping', name))
        if stage == 'merged' and not row['duties'].get('tracker'):
            duties.add(('tracker', name))
    return {'launches': launches, 'duties': duties, 'decisions': decisions}


# --- today's next, read as offers ----------------------------------------------------------------

def gate(root, name):
    """Today's gate step for an item at gate or delta, as one offer; None asks the day again."""
    try:
        found = dispatch.next_step(name, root)
    except dispatch.Refused:
        return ('refused', name)
    return {'gates': ('gates', name), 'raise': ('raise', name), 'polish': ('raise', name),
            'escalate': ('owner', name)}.get(found['action'])


def offer(data, row):
    name = row.get('item', '')
    if row['state'] == 'build':
        return ('fix' if data['items'][name]['phase'] == 'fix' else 'build', name)
    return {'merge': ('owner', name), 'pr': ('pr', name)}.get(row['state'], (row['state'], name))


def answer(root):
    """Today's next as a list of (kind, item) offers: the resolved row, looping like next.run on
    a row that asks the day again. A dispatch row is the whole launch set (launch_set without the
    host measure): every gate step, every build not running and the planned items within CAP.
    Queue rows carry a command, not a launch, so they are not offers."""
    for _ in range(8):
        row = next_command.step(root)
        data = state.read_state(root)
        if row['state'] == 'verdicts':
            found = gate(root, row['item'])
            if found is None:
                continue
            return [found]
        if row['state'] != 'dispatch':
            return [offer(data, row)]
        names = [name for name in next_command.approved(data)
                 if data['items'][name]['phase'] not in next_command.TERMINAL]
        busy = {name for _, _, name in state.in_flight(data)}
        found = []
        for name in (name for name in names if name not in busy):
            if data['items'][name]['phase'] in ('gate', 'delta'):
                found.append(gate(root, name))
            elif data['items'][name]['phase'] in state.BUILD_PHASES:
                found.append(offer(data, {'state': 'build', 'item': name}))
        building = sum(data['items'][name]['phase'] in state.BUILD_PHASES for name in names)
        planned = [name for name in names if data['items'][name]['phase'] == 'planned']
        found += [('build', name) for name in planned[:max(0, data['cap'] - building)]]
        return [entry for entry in found if entry]
    raise AssertionError('the day did not settle on one action')


def covered(launch, offers):
    """A pr act row stands in for the PR's own fix or merge step (it delegates both)."""
    return launch in offers or (launch[0] in ('merge', 'fix') and ('pr', launch[1]) in offers)


# --- 1. the property test ------------------------------------------------------------------------

@pytest.fixture(scope='module')
def results(tmp_path_factory):
    """(world, oracle, offers, offers after state.json was deleted) per case, computed once.
    The deletion runs on every third case: the same world twice, one with state.json removed
    between two next calls, compared with the control's second call."""
    found = []
    with pytest.MonkeyPatch.context() as patch:
        for case, day in enumerate(WORLDS):
            root = tmp_path_factory.mktemp(f'case{case}')
            environment(patch, root)
            configure(root)
            materialise(root, day)
            offers = answer(root)
            deleted = None
            if case % 3 == 0:
                control = answer(root)
                other = tmp_path_factory.mktemp(f'deleted{case}')
                environment(patch, other)
                configure(other)
                materialise(other, day)
                answer(other)
                (workspace.day_dir(other) / 'state.json').unlink()
                try:
                    deleted = (control, answer(other))
                except next_command.ERRORS:  # next prints its unmeasured row
                    deleted = (control, [('unmeasured', '')])
            found.append((day, oracle(day), offers, deleted))
    return found


def broken(results, check):
    return [(day, expected, offers) for day, expected, offers, _ in results if not check(day, expected, offers)]


def test_the_generator_covers_every_dimension(results):
    rows = [row for day, *_ in results for row in day['items']]
    assert {kind for row in rows if row['stage'] == 'gating' for kind in row['verdicts'].values()} == set(GATE_KINDS)
    assert {row['pr'] for row in rows} == {None, *PR_KINDS, 'merged'}
    assert {row['rounds'] for row in rows} == {0, 1, 2, 3}
    assert {row['plan'] for row in rows} == {'planned', 'approved', 'parked'}
    assert {row['builder'] for row in rows} == {None, 'running', 'stopped'}
    assert {(duty, done) for row in rows for duty, done in row['duties'].items()} == {
        ('ping', True), ('ping', False), ('tracker', True), ('tracker', False)}
    assert {row['owner_merge'] for row in rows if row['pr'] == 'green'} == {True, False}


@pytest.mark.xfail(strict=True, reason=(
    "#844: today's next answers one row: a second ready item waits in the queue without its "
    'prompt, an owner decision on one item hides ready launches on others, and a PASS recorded '
    'at an old head counts as passed, so the stale gate is never rerun'))
def test_every_ready_launch_is_offered(results):
    found = broken(results, lambda day, expected, offers: all(
        covered(launch, offers) for launch in expected['launches']))
    assert not found, found[:3]


@pytest.mark.xfail(strict=True, reason=(
    '#844 outward duties: today next has no duty rows; a raised PR is never pinged and a merged '
    'item never gets its tracker update from next'))
def test_every_due_duty_is_offered(results):
    found = broken(results, lambda day, expected, offers: expected['duties'] <= set(offers))
    assert not found, found[:3]


@pytest.mark.xfail(strict=True, reason=(
    '#844: a PR red at the round cap comes back as a pr act row to run, not as the one owner '
    'decision it is'))
def test_nothing_ready_is_exactly_one_owner_decision(results):
    found = broken(results, lambda day, expected, offers: bool(
        expected['launches'] or expected['duties'] or not expected['decisions'])
        or (len(offers) == 1 and offers[0] in expected['decisions']))
    assert not found, found[:3]


def test_never_two_owner_decisions(results):
    found = broken(results, lambda day, expected, offers: sum(kind == 'owner' for kind, _ in offers) <= 1)
    assert not found, found[:3]


def test_never_past_the_round_cap(results):
    found = broken(results, lambda day, expected, offers: not any(
        kind == 'fix' and row['name'] == name and row['rounds'] >= CAP_ROUNDS
        for kind, name in offers for row in day['items']))
    assert not found, found[:3]


def test_never_a_gate_before_the_builder_stops(results):
    found = broken(results, lambda day, expected, offers: not any(
        kind == 'gates' and row['name'] == name and row['builder'] == 'running'
        for kind, name in offers for row in day['items']))
    assert not found, found[:3]


@pytest.mark.xfail(strict=True, reason=(
    '#844, #669: today next raises on the recorded verdicts; a PASS received before the builder '
    'moved the head still counts, so the PR is raised without a pass at head'))
def test_never_a_raise_without_a_pass_at_head(results):
    found = broken(results, lambda day, expected, offers: not any(
        kind == 'raise' and row['name'] == name and set(row['verdicts'].values()) != {'PASS'}
        for kind, name in offers for row in day['items']))
    assert not found, found[:3]


def test_never_a_merge_without_the_policy(results):
    found = broken(results, lambda day, expected, offers: not any(
        kind == 'merge' and row['name'] == name and (row['pr'] != 'green' or row['owner_merge'])
        for kind, name in offers for row in day['items']))
    assert not found, found[:3]


@pytest.mark.xfail(strict=True, reason=(
    '#844 outward duties: today next closes the day while a merged item has no tracker update '
    'and a raised PR has no ping recorded'))
def test_never_done_with_an_open_duty(results):
    found = broken(results, lambda day, expected, offers: not expected['duties'] or not any(
        kind in ENDINGS for kind, _ in offers))
    assert not found, found[:3]


# --- 3. state.json is a cache --------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=(
    "#844: today state.json is the truth; without it next starts the day again at the session "
    'row'))
def test_deleting_state_json_between_two_calls_changes_no_answer(results):
    pairs = [deleted for *_, deleted in results if deleted is not None]
    assert len(pairs) == CASES // 3
    found = [pair for pair in pairs if pair[0] != pair[1]]
    assert not found, found[:3]


# --- 2. recorded dead ends and drift cases ---------------------------------------------------------

@pytest.fixture
def run(tmp_path, monkeypatch):
    """Materialise one world and return (root, today's offers)."""
    def call(day, extra=''):
        configure(tmp_path, extra)
        materialise(tmp_path, day)
        return tmp_path, answer(tmp_path)
    environment(monkeypatch, tmp_path)
    return call


def seat_state(root, update):
    state._write_state(update, root, reserved=False)


# Scheduler dead ends.

def test_603_two_repositories_worktree_add_names_the_repository(run):
    root, _ = run({'cap': 1, 'items': [item('item-1')]},
                  '[[repos]]\nname = "example/other"\npath = "other"\ndefault_branch = "main"\n')
    (workspace.day_dir(root) / 'proposal.json').write_text(json.dumps(
        {'candidates': [{'id': 'item-1', 'repo': 'example/other', 'scope': 's', 'evidence': 'e'}]}))
    commands = dispatch._start(root, 'item-1', workspace.load_config(root)['repos'])
    assert commands[0] == 'wuwei worktree add item-1 --repo example/other'


def test_614_a_fix_round_is_a_fresh_agent_with_its_prompt(run):
    root, offers = run({'cap': 1, 'items': [item('item-1', 'gating', verdicts={'quality': 'FIX'})]})
    assert offers == [('fix', 'item-1')]
    action = state.read_state(root)['builds']['item-1']['action']
    assert action['action'] == 'continue' and 'gate-quality-item-1.md' in action['prompt']
    assert 'fresh Agent' in next_command.THEN['continue']


def test_617_one_steward_at_a_time_on_the_newest_brief(run):
    root, _ = run({'cap': 1, 'items': [item('item-1', 'merged', duties={'ping': True, 'tracker': True})]})
    for name in ('steward-1', 'steward-2'):
        state.append_event('steward.run', {'brief': f'.wuwei/days/2026-10-11/briefs/{name}.md'}, root)
    row = next_command.step(root)
    assert (row['state'], row['brief']) == ('steward', '.wuwei/days/2026-10-11/briefs/steward-2.md')
    seat_state(root, lambda data: data['seats'].update({'steward-1': {
        'item': 'day', 'role': 'steward', 'status': 'running'}}))
    assert next_command.step(root)['state'] != 'steward'


def test_623_at_the_round_cap_a_blocking_verdict_is_one_owner_decision(run):
    root, offers = run({'cap': 1, 'items': [item('item-1', 'gating', rounds=CAP_ROUNDS,
                                                 verdicts={'quality': 'FIX'})]})
    assert offers == [('owner', 'item-1')]
    assert state.read_state(root)['builds']['item-1']['fix_rounds'] == CAP_ROUNDS


def test_624_the_steward_waits_while_an_item_is_mid_round(run):
    root, _ = run({'cap': 1, 'items': [item('item-1', 'building', rounds=1)]})
    state.append_event('steward.run', {'brief': '.wuwei/days/2026-10-11/briefs/steward-1.md'}, root)
    assert next_command.step(root)['state'] == 'wait'


@pytest.mark.xfail(strict=True, reason=(
    '#637 (open): depends_on is not read; an item whose dependency has not shipped takes a seat'))
def test_637_an_item_waiting_on_another_takes_no_seat(run):
    day = {'cap': 2, 'items': [item('item-1'), item('item-2')]}
    root, _ = run(day)
    (workspace.day_dir(root) / 'proposal.json').write_text(json.dumps({'candidates': [
        {'id': 'item-1'}, {'id': 'item-2', 'depends_on': ['item-1']}]}))
    offers = answer(root)
    assert ('build', 'item-1') in offers and ('build', 'item-2') not in offers


def test_648_an_item_held_on_a_broken_main_takes_no_seat(run):
    root, _ = run({'cap': 2, 'items': [item('fix-1', 'building'), item('item-2', 'building')]})
    seat_state(root, lambda data: (data['seats']['builder-item-2'].update(status='stopped'),
                                   data['builds']['item-2'].update(status='done', action={
                                       'action': 'wait', 'fix': 'fix-1'})))
    offers = answer(root)
    assert offers == [('wait', '')] and state.held(state.read_state(root), 'item-2') == 'fix-1'


def test_666_a_pr_waiting_on_people_never_hides_runnable_work(run):
    root, offers = run({'cap': 2, 'items': [
        item('item-1', 'raised', pr='pending', duties={'ping': True}),
        item('item-2', 'gating', verdicts={'quality': 'absent'})]})
    assert offers == [('gates', 'item-2')]
    assert [row['state'] for row in next_command.step(root)['rows']] == ['verdicts', 'pr']


def test_729_an_owner_merge_row_ends_when_the_pr_merges(run):
    root, offers = run({'cap': 1, 'items': [item('item-1', 'raised', pr='green', owner_merge=True,
                                                 duties={'ping': True})]})
    assert offers == [('pr', 'item-1')]
    state.append_event('merge.policy_blocked', {'pr': f'{REPO}#101', 'owner': True,
                                                'reason': 'owner_merge'}, root)
    assert answer(root) == [('owner', 'item-1')]
    seat_state(root, lambda data: data['items']['item-1'].update(phase='merged'))
    assert ('owner', 'item-1') not in answer(root)


def test_732_a_blocking_verdict_gives_the_fix_round_or_one_owner_decision(run, tmp_path):
    _, offers = run({'cap': 1, 'items': [item('item-1', 'gating', tier='standard', verdicts={
        'arch': 'PASS', 'quality': 'FIX', 'security': 'PASS'})]})
    assert offers == [('fix', 'item-1')]
    (tmp_path / '.wuwei').rename(tmp_path / 'first')
    _, offers = run({'cap': 1, 'items': [item('item-1', 'gating', verdicts={'quality': 'ESCALATE'})]})
    assert offers == [('owner', 'item-1')]


def test_783_every_gate_passed_gives_the_shepherd_that_raises_with_wuwei(run):
    root, offers = run({'cap': 1, 'items': [item('item-1', 'gating', verdicts={'quality': 'PASS'})]})
    assert offers == [('raise', 'item-1')]
    command = dispatch.next_step('item-1', root)['commands'][0]
    assert command.startswith('wuwei brief shepherd item-1 shepherd-item-1 ')
    assert 'pr raise' in command and '--item item-1' in command


# State drift.

def test_658_subagent_seats_never_read_free_memory(run, monkeypatch):
    from wuwei.guards import agent_launch
    root, _ = run({'cap': 1, 'items': [item('item-1')]}, '[host]\nseats = 3\n')

    def unread(*args):
        raise AssertionError('free memory read for subagent seats')
    monkeypatch.setattr(agent_launch, 'free_memory', unread)
    limits = dispatch.host(root, workspace.load_config(root))
    assert (limits['cap'], limits['bound']) == (3, 'host.seats')


def test_660_a_launch_with_an_appended_note_still_names_its_brief():
    prompt = (brief.REFERENCE_PREFIX + '.wuwei/days/2026-10-11/briefs/builder-item-1.md\n\n'
              'Planner note: the owner asked for the short form.')
    assert brief.reference(prompt) == '.wuwei/days/2026-10-11/briefs/builder-item-1.md'


def test_667_a_brief_points_at_the_live_record_and_copies_none_of_it():
    line = brief.LIVE.format(item='item-1')
    assert 'wuwei why item-1 --json' in line and 'copies none' in line


@pytest.mark.xfail(strict=True, reason=(
    '#669, #844: next raises on a PASS recorded at an old head; the builder moved the head after '
    'the gate and the gate is never rerun at the current head'))
def test_669_a_pass_at_an_old_head_is_no_pass(run):
    _, offers = run({'cap': 1, 'items': [item('item-1', 'gating', tier='standard', verdicts={
        'arch': 'stale', 'quality': 'stale', 'security': 'stale'})]})
    assert offers == [('gates', 'item-1')]


def test_677_q_prefixed_findings_block_like_f_prefixed_ones():
    text = ('Verdict: FIX\nHead: a1b2c3d\n- Q1 | src/a.py:1 | breaks the parser | blocks: yes\n'
            '- Q2 | src/b.py:2 | drops a row | blocks: yes\n')
    blocks = verdict.finding_blocks(text)
    assert len(blocks) == 2 and all(re.search(verdict.BLOCKS_YES, row, re.I) for row in blocks)


def test_728_a_check_red_on_the_base_too_is_not_the_prs(monkeypatch):
    from wuwei import pr_actions
    base = 'b' * 40
    red = {'name': 'test', 'state': 'completed', 'conclusion': 'failure', 'sha': base}

    class Host:
        def checks(self, ref, head, root=None):
            return Result(0, [red])
    measured = {'pr': {'base_sha': base}, 'checks': [{**red, 'sha': 'c' * 40}]}
    assert pr_actions._base_red(Host(), f'{REPO}#1', measured, None) == f'base_red: test fails at {base} too'


@pytest.mark.xfail(strict=True, reason=(
    '#729, #844: next reads the phase from state.json; a PR merged on the host while the record '
    'says raised is still offered as a pr act'))
def test_729_a_pr_merged_on_the_host_is_merged(run):
    root, _ = run({'cap': 1, 'items': [item('item-1', 'raised', pr='green', duties={'ping': True})]})
    listing = workspace.day_dir(root) / 'prs.json'
    listing.write_text(listing.read_text().replace('"green"', '"merged"'))
    assert ('pr', 'item-1') not in answer(root)


def test_734_a_verdict_citing_scratch_older_than_its_brief_is_named(tmp_path):
    copy = tmp_path / '.wuwei/scratch/item-1/sentinel-quality'
    copy.mkdir(parents=True)
    (copy / 'probe.py').write_text('x = 1\n')
    cited = '.wuwei/scratch/item-1/sentinel-quality/probe.py'
    stale = dispatch._stale_scratch(f'Probe: ran {cited} clean\n', 'Written: 2099-01-01T00:00:00+00:00\n', tmp_path)
    assert stale == [cited]


def test_741_a_bare_ticket_number_is_stored_with_its_repository(run):
    root, _ = run({'cap': 1, 'items': [item('item-1')]}, '[adapters]\ntracker = "github"\n')
    config = workspace.load_config(root)
    assert tracker.full_id(config, '24') == f'{REPO}#24'
    assert tracker.full_id(config, f'{REPO}#24') == f'{REPO}#24'
