"""The loop's contract (#844, #849): what the derived `next` must offer for any day.

Three parts:

1. A property test over generated item states. Each case is a world (the plan file, the
   worktree, the builder seat, the verdict files, the round count, the cached PR listing and the
   outward duties) that `materialise` writes as the day files the commands leave. An oracle says
   what the loop must offer for that world; each invariant is one test: every ready launch
   offered, every due duty offered, at most one owner decision and only when nothing is ready,
   never past the round cap, never a gate, raise or merge before its evidence, and never done
   with an open duty.
2. One test per recorded scheduler dead end and state drift case from the two study days.
3. Deleting state.json between two `next` calls changes no answer.

A change to the loop keeps the worlds, the oracle and the invariants; it may change only
`materialise` (where `next` reads its inputs) and `answer` (how its output reads as offers).
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
         owner_merge=False, duties=None, moved=False, agents=False):
    """One item of a world. stage: queued, building (builder running), gating (builder
    stopped), raised or merged; a gating item's verdicts map its gates to GATE_KINDS. moved: a
    rebase or a push moved the PR head past the verdicts; agents: the gate seats recorded an
    agent id (a stale verdict re-reads on its seat, else on a fresh brief)."""
    started = plan == 'approved' and stage != 'queued'
    if stage in ('raised', 'merged') and verdicts is None:
        verdicts = {role: 'PASS' for role in ROLES[tier]}
    return {'name': name, 'plan': plan, 'stage': stage if plan == 'approved' else None, 'tier': tier,
            'worktree': started, 'builder': ('running' if stage == 'building' else 'stopped') if started else None,
            'verdicts': verdicts or {}, 'rounds': rounds,
            'pr': 'merged' if stage == 'merged' else pr, 'owner_merge': owner_merge, 'duties': duties or {},
            'moved': moved, 'agents': agents}


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
        if stage == 'raised':
            fields['moved'] = rng.random() < 0.3
        if stage == 'gating':
            fields['agents'] = rng.random() < 0.5
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
    return text + ('## Findings\n' + FINDING if kind in ('FIX', 'ESCALATE', 'PARK') else '')


def record(name, role, kind, round_name):
    """The gate_verdicts row receive writes; a malformed file or an absent one records nothing,
    and a stale one is a PASS received before the builder moved the head."""
    result = 'PASS' if kind == 'stale' else kind
    blocks = result in ('FIX', 'ESCALATE', 'PARK')
    return {'item': name, 'role': role, 'round': round_name, 'verdict': result,
            'head': OLD if kind == 'stale' else HEAD, 'blocks': blocks, 'notes': [],
            'file': f'.wuwei/days/2026-10-11/decisions/gate-{role}-{name}.md',
            'findings': [FINDING.strip()] if blocks else []}


def full(sha):
    return sha + '0' * (40 - len(sha))


def materialise(root, day):
    """Write the world as the day files: plan.md, the records through the state writer (the
    event log is the truth, state.json only its cache), the builder briefs, the verdict files,
    the worktrees (a linked worktree's .git pointer and git's registry files), the cached PR
    listing (prs.json) and the duty records (duty.done events)."""
    directory = workspace.day_dir(root)
    (directory / 'decisions').mkdir(parents=True, exist_ok=True)
    (directory / 'briefs').mkdir(exist_ok=True)
    plan = ['# Plan']
    data = {'gate_approved': True, 'cap': day['cap'], 'planner_session_id': 'S', 'builds': {},
            'approved_items': [], 'items': {}, 'seats': {}, 'gate_verdicts': {}, 'raised_prs': []}
    pulls, events = [], []
    for number, row in enumerate(day['items'], 1):
        name, current = row['name'], phase(row)
        plan.append(f"- {name}: {row['plan']}")
        entry = {'phase': current, 'status': 'queued' if current == 'planned' else 'running'}
        if row['plan'] != 'planned':
            data['approved_items'].append(name)
        if current == 'parked':
            entry.update(resume_phase='gate', disposition={'kind': 'parked', 'reason': 'parked by a verdict'})
        if row['worktree']:
            tree, registry = root / 'trees' / name, root / 'project/.git/worktrees' / name
            tree.mkdir(parents=True, exist_ok=True)
            registry.mkdir(parents=True, exist_ok=True)
            (tree / '.git').write_text(f'gitdir: {registry}\n')
            (registry / 'HEAD').write_text(full(HEAD) + '\n')
            (registry / 'commondir').write_text('../..\n')
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
                if row['agents']:
                    (directory / 'briefs' / f'{role}-{name}.md').write_text(f'Review {name}.\n')
                    data['seats'][f'{role}-{name}'].update(
                        agent_id=f'agent-{role}-{name}', brief=f'.wuwei/days/2026-10-11/briefs/{role}-{name}.md')
            if current == 'delta':  # the round before: every gate asked for the fix
                data['gate_verdicts'][f'{name}:{role}:initial'] = record(name, role, 'FIX', 'initial')
            if kind not in ('absent', 'malformed'):
                round_name = 'delta' if current == 'delta' else 'initial'
                data['gate_verdicts'][f'{name}:{role}:{round_name}'] = record(name, role, kind, round_name)
        if row['pr']:
            entry.update(pr=f'{REPO}#{100 + number}', owner_merge={  # #904: the record plan set writes
                'value': row['owner_merge'], 'by': 'owner', 'at': '2026-10-11T09:00:00+00:00'})
            data['raised_prs'].append(entry['pr'])
            pulls.append({'ref': entry['pr'], 'state': 'merged' if row['pr'] == 'merged' else 'open',
                          'checks': None if row['pr'] == 'merged' else row['pr'],
                          'head': 'c' * 40 if row['moved'] else full(HEAD),
                          'labels': ['owner-merge'] if row['owner_merge'] else []})
        events += [('duty.done', {'item': name, 'duty': duty}) for duty, done in row['duties'].items() if done]
        data['items'][name] = entry
    (directory / 'plan.md').write_text('\n'.join(plan) + '\n')
    (directory / 'prs.json').write_text(json.dumps({'fetched_at': NOW, 'pulls': pulls}))
    state._write_state(lambda fresh: fresh.update(workspace.copy_data(data)), root,
                       kind='plan.approved', payload={'items': data['approved_items']})
    for kind, payload in events:
        state.append_event(kind, payload, root)


def configure(root, extra=''):
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text(
        # the channels the ping and tracker duties need (#844, G7): a review channel, a page
        'shepherd.review_channel = "C0REVIEW"\noutbound.owner.pages = ["https://pages.example/day"]\n'
        f'[[repos]]\nname = "{REPO}"\npath = "project"\ndefault_branch = "main"\n'
        '[spec]\nengine = "none"\n[gates]\npolish = "never"\n[duties]\non = ["ping", "tracker"]\n' + extra)


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
        if stage == 'raised' and row['moved']:  # the verdicts do not cover the PR head: re-read first
            (decisions if capped else launches).add(('owner' if capped else 'fix', name))
        elif stage == 'raised' and row['pr'] == 'red':
            (decisions if capped else launches).add(('owner' if capped else 'fix', name))
        elif stage == 'raised' and row['pr'] == 'green':
            (decisions if row['owner_merge'] else launches).add(('owner' if row['owner_merge'] else 'merge', name))
        if stage in ('raised', 'merged') and not row['duties'].get('ping'):
            duties.add(('ping', name))
        if stage == 'merged' and not row['duties'].get('tracker'):
            duties.add(('tracker', name))
    return {'launches': launches, 'duties': duties, 'decisions': decisions}


# --- next, read as offers ---------------------------------------------------------------------

def answer(root):
    """next as a list of (kind, item) offers: every launch, every due duty and the one owner
    decision of the set, or the day row."""
    from wuwei import registry
    from fakes.host import Fake as ProcessHost
    load = registry.load
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(registry, 'load', lambda kind, config: ProcessHost() if kind == 'host' else load(kind, config))
        row = next_command.step(root)
    if row['state'] != 'set':
        return [(row['state'], row.get('item', ''))]
    return ([(launch['kind'], launch['item']) for launch in row['launches']]
            + [(duty['duty'], duty['item']) for duty in row['duties']]
            + ([('owner', row['decision']['item'])] if row['decision'] else []))


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
    assert {row['moved'] for row in rows if row['stage'] == 'raised'} == {True, False}
    assert {row['agents'] for row in rows if 'stale' in row['verdicts'].values()} == {True, False}


def test_every_ready_launch_is_offered(results):
    found = broken(results, lambda day, expected, offers: all(
        launch in offers for launch in expected['launches']))
    assert not found, found[:3]


def test_every_due_duty_is_offered(results):
    found = broken(results, lambda day, expected, offers: expected['duties'] <= set(offers))
    assert not found, found[:3]


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


def _case_never_a_gate_before_the_builder_stops(results):
    found = broken(results, lambda day, expected, offers: not any(
        kind == 'gates' and row['name'] == name and row['builder'] == 'running'
        for kind, name in offers for row in day['items']))
    assert not found, found[:3]


def _case_never_a_raise_without_a_pass_at_head(results):
    found = broken(results, lambda day, expected, offers: not any(
        kind == 'raise' and row['name'] == name and set(row['verdicts'].values()) != {'PASS'}
        for kind, name in offers for row in day['items']))
    assert not found, found[:3]


def _case_never_a_merge_without_the_policy(results):
    found = broken(results, lambda day, expected, offers: not any(
        kind == 'merge' and row['name'] == name and (row['pr'] != 'green' or row['owner_merge'])
        for kind, name in offers for row in day['items']))
    assert not found, found[:3]


@pytest.mark.parametrize("scenario_fn", [
    _case_never_a_gate_before_the_builder_stops,
    _case_never_a_raise_without_a_pass_at_head,
    _case_never_a_merge_without_the_policy,
])
def test_never_a_cases_343(results, scenario_fn):
    scenario_fn(results)


def test_never_done_with_an_open_duty(results):
    found = broken(results, lambda day, expected, offers: not expected['duties'] or not any(
        kind in ENDINGS for kind, _ in offers))
    assert not found, found[:3]


# --- 3. state.json is a cache --------------------------------------------------------------------

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
    state._write_state(update, root)


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
    action, = [launch for launch in next_command.resolve(next_command.step(root), root)['launches']
               if launch['kind'] == 'fix']
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
    assert offers == [('owner', 'item-1')]  # #844: owner_merge is the owner's decision at once
    state.append_event('merge.policy_blocked', {'pr': f'{REPO}#101', 'owner': True,
                                                'reason': 'owner_merge'}, root)
    assert answer(root) == [('owner', 'item-1')]
    seat_state(root, lambda data: data['items']['item-1'].update(phase='merged'))
    offers = answer(root)
    assert not [offer for offer in offers if offer[1] == 'item-1' and offer[0] not in ('tracker',)]
    assert ('tracker', 'item-1') in offers


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
    assert command.startswith('wuwei seat brief shepherd item-1 shepherd-item-1 ')
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


def test_669_a_pass_at_an_old_head_is_no_pass(run):
    _, offers = run({'cap': 1, 'items': [item('item-1', 'gating', tier='standard', verdicts={
        'arch': 'stale', 'quality': 'stale', 'security': 'stale'})]})
    assert offers == [('gates', 'item-1')]


def test_677_q_prefixed_findings_block_like_f_prefixed_ones():
    text = ('Verdict: FIX\nHead: a1b2c3d\n## Findings\n- Q1 | src/a.py:1 | breaks the parser | blocks: yes\n'
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


def test_729_a_pr_merged_on_the_host_is_merged(run):
    root, _ = run({'cap': 1, 'items': [item('item-1', 'raised', pr='green', duties={'ping': True})]})
    listing = workspace.day_dir(root) / 'prs.json'
    listing.write_text(listing.read_text().replace('"open"', '"merged"'))
    assert answer(root) == [('tracker', 'item-1')]  # no launch at all; its tracker duty comes due


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


# --- lead calls (#844, batch 8) --------------------------------------------------------------------

def fix_round(root, moved_by_fix):
    """A standard item at its delta after one fix round from OLD: arch and security passed at OLD,
    quality asked for the fix and passed its delta at HEAD. moved_by_fix: the recorded fix round
    took the head from OLD to HEAD; else the head moved some other way."""
    decisions = workspace.day_dir(root) / 'decisions'
    for role, head in (('arch', OLD), ('quality', HEAD), ('security', OLD)):
        (decisions / f'gate-{role}-item-1.md').write_text(
            f'Head: {head}\nVerdict: PASS\nProbes: tested\nAUTH: PASS\nSimplicity: checked\n'
            'Design: checked\nBlocked: none\nGap: none\nChange: none\n')

    def update(data):
        verdicts = data['gate_verdicts']
        for role in ('arch', 'security'):
            verdicts[f'item-1:{role}:initial'] = record('item-1', role, 'stale', 'initial')
            verdicts.pop(f'item-1:{role}:delta')
        verdicts['item-1:quality:initial'] = {**record('item-1', 'quality', 'FIX', 'initial'), 'head': OLD}
        data['items']['item-1']['fix_heads'] = [[full(OLD), full(HEAD)]] if moved_by_fix else []
    seat_state(root, update)


@pytest.mark.parametrize('moved_by_fix', [True, False])
def test_after_a_fix_round_only_the_gate_that_asked_rereads(run, moved_by_fix):
    """Design 5.3 gate cost: the gates that passed keep their PASS for the head the fix round
    produced; a head moved any other way makes their PASS stale (#669)."""
    root, _ = run({'cap': 1, 'items': [item('item-1', 'gating', tier='standard', rounds=1, verdicts={
        'arch': 'PASS', 'quality': 'PASS', 'security': 'PASS'})]})
    fix_round(root, moved_by_fix)
    assert answer(root) == [('raise' if moved_by_fix else 'gates', 'item-1')]


@pytest.mark.parametrize('moved_by_fix', [True, False])
def test_the_raise_check_takes_a_pass_carried_by_a_fix_round_only(run, moved_by_fix):
    from wuwei import merge
    root, _ = run({'cap': 1, 'items': [item('item-1', 'gating', tier='standard', rounds=1, verdicts={
        'arch': 'PASS', 'quality': 'PASS', 'security': 'PASS'})]})
    fix_round(root, moved_by_fix)
    code, reason = merge.gate_check(root, root / 'trees/item-1', workspace.load_config(root),
                                    sha=full(HEAD), item='item-1')
    assert (code, reason) == (0, '') if moved_by_fix else (code == 1 and 'arch, security' in reason)


def test_open_duties_carry_across_days(run):
    """A day carried without close keeps its open duties in next and close."""
    from wuwei import closing
    root, _ = run({'cap': 1, 'items': [item('item-1', 'raised', pr='pending', duties={'ping': True})]})
    prior = root / '.wuwei/days/2026-10-10'
    old = f'{REPO}#99'
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['old-1'], raised_prs=[old],
        items={'old-1': {'phase': 'raised', 'status': 'running', 'pr': old}}),
        directory=prior, kind='plan.approved')
    assert ('ping', 'old-1') in answer(root)
    code, reason = closing.unresolved(root, [])
    assert code == 1 and 'old-1: ping' in reason
    state.append_event('duty.done', {'item': 'old-1', 'duty': 'ping'}, root)
    assert ('ping', 'old-1') not in answer(root)
    state.append_event('duty.done', {'item': 'old-1', 'duty': 'ping'}, directory=prior)
    (prior / 'events.jsonl').chmod(0o644)
    state.append_event('day.closed', {}, directory=prior)
    assert ('ping', 'old-1') not in answer(root)


def test_deleting_state_json_between_any_two_next_calls_changes_no_answer(tmp_path_factory):
    """Every world: delete state.json between two next calls, and again after a write between
    them; no answer changes."""
    found = []
    with pytest.MonkeyPatch.context() as patch:
        for case, day in enumerate(WORLDS):
            root = tmp_path_factory.mktemp(f'any{case}')
            environment(patch, root)
            configure(root)
            materialise(root, day)
            cache = workspace.day_dir(root) / 'state.json'
            first = answer(root)
            cache.unlink()
            second = answer(root)
            seat_state(root, lambda data: data['seats'].update({'note': {
                'item': 'day', 'role': 'steward', 'status': 'stopped'}}))
            third = answer(root)
            cache.unlink()
            if (first, third) != (second, answer(root)):
                found.append((day, first, second, third))
    assert not found, found[:3]


def test_a_park_at_the_round_cap_is_the_owners_plan_resume_decision(run):
    """The round cap parks in code; the owner decides on plan resume's Owner step card until
    they answer, and a No leaves it parked."""
    from fakes import owner
    from wuwei import plan
    root, _ = run({'cap': 1, 'items': [item('item-1', 'gating', rounds=CAP_ROUNDS, verdicts={'quality': 'FIX'})]})
    reason = 'round cap 2 reached: quality still blocks'
    plan.park('item-1', reason, root)
    found = next_command.step(root)
    assert found['decision']['command'] == 'wuwei plan resume item-1' and answer(root) == [('owner', 'item-1')]
    owner.answer(root, 'bin/wuwei plan resume item-1', plan.resume_token(root, 'item-1'), 'No',
                 detail=f'Resume item-1: {reason}')
    assert answer(root) != [('owner', 'item-1')]


# --- review fixes (#844) -------------------------------------------------------------------------

def test_a_stale_gate_is_never_an_empty_launch(tmp_path_factory):
    """F2: every gating world with a stale PASS resolves its gates into a seat or a command, with
    and without the seat's agent id."""
    found = []
    with pytest.MonkeyPatch.context() as patch:
        for case, day in enumerate(WORLDS):
            names = [row['name'] for row in day['items'] if row['stage'] == 'gating' and row['plan'] == 'approved'
                     and 'stale' in row['verdicts'].values()]
            if not names:
                continue
            root = tmp_path_factory.mktemp(f'stale{case}')
            environment(patch, root)
            configure(root)
            materialise(root, day)
            for name in names:
                try:
                    action = dispatch.next_step(name, root)
                except dispatch.Refused as exc:
                    found.append((name, str(exc)))
                    continue
                if action['action'] == 'gates' and not (action['seats'] or action.get('commands')):
                    found.append((name, action))
    assert not found, found[:3]


def test_f1_a_pr_head_moved_past_the_verdicts_is_never_merged(run):
    from wuwei import merge
    root, offers = run({'cap': 1, 'items': [item('item-1', 'raised', pr='green', duties={'ping': True},
                                                 moved=True)]})
    assert offers == [('fix', 'item-1')]
    code, _ = merge.gate_check(root, root / 'trees/item-1', workspace.load_config(root), sha='c' * 40,
                               item='item-1')
    assert code == 1
    assert dispatch.next_step('item-1', root)['action'] == 'fix'  # the round every gate re-reads
    row = state.read_state(root)['items']['item-1']
    assert row['phase'] == 'fix' and row['fix_heads'][-1][0] == 'c' * 40


def test_f5_a_gone_or_unreadable_worktree_never_raises(run):
    import shutil
    root, offers = run({'cap': 1, 'items': [item('item-1', 'gating', verdicts={'quality': 'PASS'})]})
    assert offers == [('raise', 'item-1')]
    head = root / 'project/.git/worktrees/item-1/HEAD'
    head.write_text('ref: refs/heads/feature\n')  # an unborn ref: no HEAD to read
    assert answer(root) == [('owner', 'item-1')]
    assert 'trees/item-1' in next_command.step(root)['decision']['why']
    shutil.rmtree(root / 'trees/item-1')
    assert answer(root) == [('owner', 'item-1')]


def test_f3_a_verdict_edited_after_receipt_is_not_received_again(run):
    root, offers = run({'cap': 1, 'items': [item('item-1', 'gating', verdicts={'quality': 'FIX'})]})
    path = workspace.day_dir(root) / 'decisions/gate-quality-item-1.md'
    path.write_text(f'Verdict: PASS\nHead: {HEAD}\n')
    assert answer(root) == offers == [('fix', 'item-1')]  # the receipt stands
    with pytest.raises(dispatch.Refused, match='already received'):
        dispatch.receive('item-1', 'quality', 'quality-item-1', root=root)


def test_f9_a_pr_closed_on_the_host_is_one_owner_decision(run):
    root, _ = run({'cap': 1, 'items': [item('item-1', 'raised', pr='pending', duties={'ping': True})]})
    listing = workspace.day_dir(root) / 'prs.json'
    listing.write_text(listing.read_text().replace('"open"', '"closed"'))
    found = next_command.step(root)
    assert answer(root) == [('owner', 'item-1')] and found['launches'] == []
    assert found['decision']['command'] == 'wuwei plan park item-1 --reason "PR closed unmerged on the code host"'
    assert found['decision']['card']['record'] == found['decision']['command']


def test_g1_a_green_pr_the_policy_holds_is_waiting_not_a_merge_spin(run):
    root, offers = run({'cap': 1, 'items': [item('item-1', 'raised', pr='green', duties={'ping': True})]})
    assert offers == [('merge', 'item-1')]
    state.append_event('merge.policy_blocked', {'pr': f'{REPO}#101', 'exit': 1, 'owner': False,
                                                'reason': 'merge policy: waits: approvals missing'}, root)
    assert answer(root) == [('wait', '')]
    assert 'nothing changed' in next_command.THEN['set']


def test_g5_next_records_the_park_of_a_park_verdict(run, capsys):
    from wuwei.__main__ import main
    root, offers = run({'cap': 1, 'items': [item('item-1', 'gating', verdicts={'quality': 'PARK'})]})
    assert offers == []
    assert main(['next', '--json']) in (0, 1)
    assert state.read_state(root)['items']['item-1']['phase'] == 'parked'


def test_the_owners_resume_at_the_cap_grants_one_re_read_of_a_moved_pr_head(run):
    """D3: at the round cap a moved PR head parks; the owner's Yes on plan resume grants one
    re-read round, as for PARK and ESCALATE, never the same park again."""
    from fakes import owner
    from wuwei import plan
    root, offers = run({'cap': 1, 'items': [item('item-1', 'raised', pr='green', rounds=CAP_ROUNDS,
                                                 duties={'ping': True}, moved=True)]})
    assert offers == [('owner', 'item-1')]
    assert dispatch.next_step('item-1', root)['action'] == 'escalate'
    reason = state.read_state(root)['items']['item-1']['disposition']['reason']
    owner.answer(root, 'bin/wuwei plan resume item-1', plan.resume_token(root, 'item-1'), 'Yes',
                 detail=f'Resume item-1: {reason}')
    plan.resume('item-1', root)
    assert answer(root) == [('fix', 'item-1')]
    assert dispatch.next_step('item-1', root)['action'] == 'fix'
