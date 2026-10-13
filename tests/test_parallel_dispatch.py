"""Issue #474: the day starts in parallel, through the hooks on the fixture day."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GOALS = ('A', 'G-1', 1), ('B', 'G-2', 2), ('C', 'G-1', 3), ('D', 'G-2', 5)
CLAUDE = {'builder': {'runtime': 'claude', 'model': 'scripted'}}


def test_lead_prompt_and_charter_explain_candidate_kind():
    from wuwei.commands.next import LEAD_BODY

    charter = (ROOT / 'charters/lead.md').read_text()
    assert 'kind' in LEAD_BODY and 'review' in LEAD_BODY and 'measure' in LEAD_BODY
    assert 'kind' in charter and 'review' in charter and 'measure' in charter
# #658: one seat runtime that launches its own process puts the day on the memory rule
PROCESS = {**CLAUDE, 'sentinel-security': {'runtime': 'codex', 'model': 'scripted'}}


@pytest.fixture
def day(tmp_path, monkeypatch):
    from fakes.day import Day
    return Day(tmp_path / 'workspace', monkeypatch)


def approved(day, cap=None, extra='', policy=CLAUDE):
    config = day.root / '.wuwei/config.toml'
    config.write_text((f'cap = {cap}\n' if cap else '') + config.read_text() + extra)
    goals = day.root / '.wuwei/memory/goals.md'
    goals.write_text(goals.read_text() + '## G-2\noutcome: Second result\nmeasure: shipped\n'
                     'target: 1\ndate: 2026-10-30\npriority: 2\n')
    score = {'value': 5, 'time_criticality': 3, 'risk_reduction': 2}
    candidates = [{'id': name, 'goal': goal, 'evidence': f'recorded issue {name}',
                   'scope': 'one value', 'overlap': 'none', 'track': 'SLICE',
                   'flags': {'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False},
                   'score': {**score, 'job_size': size},
                   'evidence_lines': {key: f'recorded issue {name}' for key in (*score, 'job_size')}}
                  for name, goal, size in GOALS]
    source = day.root / 'proposal.json'
    source.write_text(json.dumps({
        'goals': ['G-1', 'G-2'], 'cap': 1,  # the lead's cap is not used (#528)
        'seat_policy': policy,
        'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
        'sweep': {'processes': 'measured: none'}, 'candidates': candidates}))
    day.run('plan', 'propose', source)
    day.run('plan', 'approve', '--items', 'A', 'B', 'C', 'D', '--goals-confirmed')
    day.run('plan', 'session', 'planner')


def launch_set(day, expected=0):
    value = json.loads(day.run('dispatch', 'next', '--all', expected=expected))
    return [(row['item'], row['action']) for row in value['entries']], value['entries']


def brief(day, item, role='builder', name=None):
    return day.run('seat', 'brief', role, item, name or f'{item}-builder', '--worktree', day.repo,
                   '--file', '-', stdin='Implement or review the demo value.').strip()


def agent(day, action):
    return {'subagent_type': action['agent_type'], 'description': 'Parallel seat',
            'prompt': action['prompt']}


def guard(day, relative, role='builder'):
    from wuwei.guards import agent_launch
    return agent_launch.check({'cwd': str(day.root), 'tool_input': {
        'subagent_type': role, 'description': 'Seat', 'prompt': 'WUWEI brief: ' + relative}})


def test_first_dispatch_turn_launches_cap_builders_and_the_fourth_waits(day):
    approved(day, 3)
    assert 'Seats per goal: 3 seats: G-1 2, G-2 1 (CAP 3)' in (day.directory / 'plan.md').read_text()
    assert day.data['goal_seats'] == {'G-1': 2, 'G-2': 1}
    entries, rows = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'start'), ('C', 'start'), ('D', 'wait')]
    assert 'CAP 3' in rows[3]['reason']
    for item in 'ABC':
        brief(day, item)
    entries, rows = launch_set(day)
    assert entries == [('A', 'launch'), ('B', 'launch'), ('C', 'launch'), ('D', 'wait')]
    # One planner message: every PreToolUse runs before any seat stops.
    for minute, row in enumerate(rows[:3]):
        day.patch.setenv('WUWEI_NOW', f'2026-09-29T12:0{minute}:00Z')
        day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, row))
    running = [seat for seat in day.data['seats'].values() if seat['status'] == 'running']
    assert sorted(seat['item'] for seat in running) == ['A', 'B', 'C']
    code, reason = guard(day, brief(day, 'D'))
    # #901: no build record for D; the build next it names waits at CAP instead of starting one
    assert code == 1 and 'no build record for D' in reason and 'bin/wuwei build next D' in reason
    assert 'CAP 3 reached (3 building)' in day.run('build', 'next', 'D', expected=2)
    (day.root / '.wuwei/calibration.json').write_text('{"acme/widget": {"date": "2026-09-29"}}\n')
    step = json.loads(day.run('next', '--json'))
    assert step['state'] == 'wait'
    assert 'D waits' in step['why'] and 'A-builder started first' in step['why']
    assert 'seats 3/3 by owner (builder, builder, builder)' in day.run('status', '--line')


def test_owner_cap_one_stays_sequential(day):
    approved(day, 1)
    entries, _ = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'wait'), ('C', 'wait'), ('D', 'wait')]
    brief(day, 'A')
    _, rows = launch_set(day)
    day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, rows[0]))
    code, reason = guard(day, brief(day, 'B'))
    assert code == 1 and 'no build record for B' in reason
    assert 'CAP 1 reached' in day.run('build', 'next', 'B', expected=2)


def test_gate_sentinels_run_together_and_the_item_moves_after_all_verdicts(day):
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        brief(day, 'A', role, f'{role}-initial')
    entries, rows = launch_set(day)
    assert entries == [('A', 'gates')]
    actions = rows[0]['seats']
    assert [row['action'] for row in actions] == ['launch'] * 3
    for action in actions:
        day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, action))
    running = [seat['role'] for seat in day.data['seats'].values() if seat['status'] == 'running']
    assert sorted(running) == ['sentinel-arch', 'sentinel-quality', 'sentinel-security']
    for number, action in enumerate(actions, 1):
        day.runtime.finish(action['agent_type'].removeprefix('wuwei:'), Path(action['brief']))
        day.run(*action['receive'].split()[1:])
        result = day.next()
        if number < 3:
            assert result['action'] == 'gates' and day.data['items']['A']['phase'] == 'gate'
    assert {key: result[key] for key in ('action', 'notes')} == {'action': 'raise', 'notes': []}


def two_of_three_gates(day):
    """#910: three briefed gate seats on host.seats = 2; the two that fit launch and stop."""
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        brief(day, 'A', role, f'{role}-initial')
    config = day.root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '[host]\nseats = 2\n')
    entries, rows = launch_set(day)
    assert entries == [('A', 'gates')] and rows[0]['deferred'] == 1 and 'host.seats=2' in rows[0]['reason']
    first = rows[0]['seats']
    assert len(first) == 2
    for action in first:
        day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, action))
    assert sum(seat['status'] == 'running' for seat in day.data['seats'].values()) == 2
    assert launch_set(day)[0] == []  # the batch runs; the item is offered again when it stops
    for action in first:
        day.runtime.finish(action['agent_type'].removeprefix('wuwei:'), Path(action['brief']))
        day.run(*action['receive'].split()[1:])
    return first


def test_three_gates_on_two_seats_launch_two_then_the_third(day):
    # #910: the seats that fit launch, their verdicts are received, then the rest; never over two
    first = two_of_three_gates(day)
    entries, rows = launch_set(day)
    assert entries == [('A', 'gates')] and 'deferred' not in rows[0]
    [third] = rows[0]['seats']
    assert third['agent_type'] not in {action['agent_type'] for action in first}
    heads = {row['payload']['head'] for row in day.events if row['kind'] == 'brief written'
             and row['payload'].get('gate')}
    assert heads == {day.data['builds']['A']['checked']}  # one set, one checked head
    day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, third))
    assert sum(seat['status'] == 'running' for seat in day.data['seats'].values()) == 1
    day.runtime.finish(third['agent_type'].removeprefix('wuwei:'), Path(third['brief']))
    day.run(*third['receive'].split()[1:])
    assert day.next()['action'] == 'raise'


def test_a_head_move_refuses_the_deferred_gate_seat_and_its_siblings_verdicts(day):
    # #910 risk: the deferred seat reads the head its siblings read or not at all
    from adapters.vcs import git
    from wuwei import derive
    first = two_of_three_gates(day)
    [third] = launch_set(day)[1][0]['seats']
    (day.repo / 'memory/demo.py').write_text('VALUE = 99\n')
    assert git.workspace_commit(day.repo, ['memory/demo.py']).exit == 0
    code, reason = guard(day, str(Path(third['brief']).relative_to(day.root)), third['agent_type'])
    assert code == 1 and 'HEAD changed' in reason
    row = day.data['items']['A']
    for action in first:
        role = action['agent_type'].removeprefix('wuwei:sentinel-')
        record = day.data['gate_verdicts'][f'A:{role}:initial']
        assert derive.counted(day.root, row, record, day.head) is None


def test_docs_skill_and_charter_name_the_parallel_start():
    skill = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    assert 'wuwei dispatch next --all' in (ROOT / 'cli/wuwei/derive.py').read_text()  # #551, #844
    assert 'in one message' in skill and 'concurrently' in skill
    assert '### Seats per goal' in (ROOT / 'docs/site/concepts.md').read_text()
    row = next(line for line in (ROOT / 'docs/site/configuration.md').read_text().splitlines()
               if line.startswith('| `cap`'))
    assert 'morning gate' in row
    assert 'seats' in (ROOT / 'charters/lead.md').read_text()


def test_fresh_workspace_derives_cap_from_the_host_and_starts_four(day):
    # #528 US1, #658: subagent seats, 4 cores, no cap and no host.seats in config.
    approved(day)
    text = 'cap 4 (host.seats): subagent runtime, free memory not read; host.seats unset, 4 cores'
    assert f'CAP: {text}; host.seats 4' in (day.directory / 'plan.md').read_text()
    assert json.loads((day.directory / 'proposal.json').read_text())['cap'] == 4
    widget = json.loads(day.run('plan', 'gate'))[0]
    options = {row['label']: row['description'] for row in widget['options']}
    assert text[:1].upper() + text[1:] in options['Approve'] and 'config cap' in options['Change something']
    assert (day.data['cap'], day.data['cap_bound']) == (4, 'host.seats')
    assert 'seats 0/4 by host.seats |' in day.run('status', '--line')
    entries, _ = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'start'), ('C', 'start'), ('D', 'start')]
    assert json.loads(day.run('dispatch', 'next', '--all'))['bound'] == 'host.seats'


def test_owner_cap_names_what_the_host_fits(day):
    approved(day, 1)
    assert ('CAP: cap 1 (owner): config cap; the host fits 4 (subagent runtime, free memory not read; '
            'host.seats unset, 4 cores)'
            in (day.directory / 'plan.md').read_text())
    assert json.loads(day.run('plan', 'template'))['cap'] == 1
    config = day.root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('cap = 1\n', ''))
    assert json.loads(day.run('plan', 'template'))['cap'] == 4


def test_cap_follows_free_memory_at_each_sweep(day):
    # #528 US1 scenario 3, #658: process seats; each sweep records its reading and CAP is
    # the median of today's readings, so one roomy reading does not lift it alone.
    from wuwei.registry import Result
    day.memory.results['free_memory'] = Result(0, 3 * 1024**3)
    approved(day, policy=PROCESS)
    entries, rows = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'start'), ('C', 'wait'), ('D', 'wait')]
    assert 'CAP 2' in rows[2]['reason'] and day.data['cap'] == 2
    day.memory.results['free_memory'] = Result(0, 8 * 1024**3)
    launch_set(day)
    assert day.data['cap'] == 2
    entries, _ = launch_set(day)
    assert entries == [(item, 'start') for item in 'ABCD'] and day.data['cap'] == 4
    derived = [row['payload'] for row in day.events if row['kind'] == 'cap.derived']
    assert [(row['cap'], row['bound'], row['reading']) for row in derived] == [
        (2, 'memory', 2), (2, 'memory', 4), (4, 'memory', 4)]
    assert 'CAP: cap 2 (memory): ' in (day.directory / 'plan.md').read_text()
    assert 'seats 0/4 by memory' in day.run('status', '--line')


def test_subagent_cap_is_host_seats(day):
    # #658 US1 scenario 2: 3 GiB free does not move a configured host.seats.
    from wuwei.registry import Result
    day.memory.results['free_memory'] = Result(0, 3 * 1024**3)
    approved(day, extra='[host]\nseats = 6\n')
    launch_set(day)
    assert (day.data['cap'], day.data['cap_bound']) == (6, 'host.seats')
    assert ('CAP: cap 6 (host.seats): subagent runtime, free memory not read; host.seats 6'
            in (day.directory / 'plan.md').read_text())
    assert 'seats 0/6 by host.seats' in day.run('status', '--line')


def usage(day, *rows):
    """seat.usage rows (ts, tokens, runtime or None) in today's log."""
    path = day.root / '.wuwei/days/2026-09-29/events.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        for ts, tokens, runtime in rows:
            stream.write(json.dumps({'ts': ts, 'kind': 'seat.usage', 'payload': {
                'item': 'Z', **({'runtime': runtime} if runtime else {}),
                'usage': {'input_tokens': tokens, 'output_tokens': 0}}}) + '\n')


def spent(day, runtime='claude', reset='2026-09-29T14:00:00+00:00'):
    (day.root / '.wuwei/windows.json').write_text(json.dumps({runtime: {'five_hour': {
        'used_percent': 100, 'resets_at': reset}}}))


def test_window_fitting_two_seats_starts_two(day):
    # #845 (was #528 US2): 100000 of a 300000-token 5-hour window used at 100000 a seat fits two.
    usage(day, ('2026-09-29T10:00:00+00:00', 100000, None))
    approved(day, extra='[budget.claude]\nfive_hour = 300000\n')
    entries, rows = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'start'), ('C', 'wait'), ('D', 'wait')]
    assert [row.get('until') for row in rows] == [None, None] + ['2026-09-29T15:00:00+00:00'] * 2
    assert 'claude' in rows[2]['reason'] and 'claude five_hour 100000 of 300000 used, room 2' in json.loads(
        day.run('dispatch', 'next', '--all'))['capacity']


ROUTED = {'builder': {'runtime': 'claude', 'model': 'scripted', 'alternate': 'codex'}}


@pytest.mark.parametrize('policy,codex,cap,expected', [
    (ROUTED, 200000, None, ['run', 'run', 'wait', 'wait']),
    (CLAUDE, 200000, None, ['wait'] * 4),
    (ROUTED, 100000, 3, ['run', 'wait', 'wait', 'wait']),
], ids=['alternate', 'no-alternate', 'codex-room-one'])
def test_a_spent_runtime_routes_builders_to_the_alternate(day, policy, codex, cap, expected):
    # #845 US2: Claude's window is spent, Codex's has room: builders start on Codex as wuwei build runs.
    usage(day, ('2026-09-29T10:00:00+00:00', 100000, 'claude'))
    approved(day, cap, extra=f'[budget.codex]\nfive_hour = {codex}\n', policy=policy)
    spent(day)
    for item in 'AB':
        brief(day, item)
    entries, rows = launch_set(day)
    assert [action for _, action in entries] == expected
    for row in rows:
        if row['action'] == 'run':
            record = day.data['builds'][row['item']]
            assert row['runtime'] == record['runtime'] == 'codex'
            assert row['command'].startswith(f"wuwei build {row['item']} ") and row['command'].endswith(record['worktree'])
        elif 'CAP' not in row['reason']:
            assert row['until'] == '2026-09-29T14:00:00+00:00' and 'claude' in row['reason']


def test_a_held_build_is_not_bound_moved_or_claimed(day):
    # #845 F4: the window is checked before build next writes a record.
    approved(day, policy=CLAUDE)
    spent(day)
    brief(day, 'A')
    entries, rows = launch_set(day)
    assert entries[0] == ('A', 'wait') and rows[0]['until'] == '2026-09-29T14:00:00+00:00'
    assert day.data['items']['A']['phase'] == 'planned' and 'A' not in day.data.get('builds', {})


def test_a_build_loop_that_ended_at_once_backs_off(day):
    # #845 F2, D2: a claimed loop counts as running while its pid lives and for two minutes
    # after it started, so a loop that fails at once is not offered again every turn.
    from wuwei import state
    usage(day, ('2026-09-29T10:00:00+00:00', 100000, 'claude'))
    approved(day, extra='[budget.codex]\nfive_hour = 900000\n', policy=ROUTED)
    spent(day)
    for item in 'AB':
        brief(day, item)
    entries, _ = launch_set(day)
    assert entries[:2] == [('A', 'run'), ('B', 'run')]
    state._write_state(lambda data: data['builds']['A'].update(
        loop={'pid': 2**22 + 7, 'started_at': '2026-09-29T12:00:00+00:00'}), day.root)  # a dead pid
    entries, _ = launch_set(day)
    assert [item for item, action in entries if action == 'run'] == ['B'], entries
    day.patch.setenv('WUWEI_NOW', '2026-09-29T12:03:00Z')
    entries, _ = launch_set(day)
    assert [item for item, action in entries if action == 'run'][:2] == ['A', 'B'], entries


def test_a_loop_that_died_at_once_is_a_timed_wait(day):
    # #845 E1: a dead loop is not in flight; its back-off is a wait with until, so next sleeps.
    from wuwei import state
    usage(day, ('2026-09-29T10:00:00+00:00', 100000, 'claude'))
    approved(day, 1, extra='[budget.codex]\nfive_hour = 900000\n', policy=ROUTED)
    spent(day)
    brief(day, 'A')
    assert launch_set(day)[0][0] == ('A', 'run')
    state._write_state(lambda data: data['builds']['A'].update(
        loop={'pid': 2**22 + 7, 'started_at': '2026-09-29T12:00:00+00:00'}), day.root)  # a dead pid
    step = json.loads(day.run('next', '--json'))
    assert (step['state'], step['action'], step['until']) == ('wait', 'background', '2026-09-29T12:02:01+00:00')
    assert step['command'].startswith('sleep ') and 'A' in step['why']
    day.patch.setenv('WUWEI_NOW', '2026-09-29T12:03:00Z')
    assert [launch['action'] for launch in json.loads(day.run('next', '--json'))['launches']][0] == 'run'


def test_a_routed_builder_seat_takes_its_build_runtime_room(day):
    # #845 E2: a Claude builder seat routed from a Codex policy counts against Claude's room.
    usage(day, ('2026-09-29T10:00:00+00:00', 100000, 'claude'))
    approved(day, 4, extra='[budget.claude]\nfive_hour = 300000\n',
             policy={'builder': {'runtime': 'codex', 'model': 'scripted', 'alternate': 'claude'}})
    spent(day, 'codex')
    for item in 'AB':
        brief(day, item)
    entries, rows = launch_set(day)
    assert entries[:2] == [('A', 'launch'), ('B', 'launch')]
    for row in rows[:2]:
        day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, row))
    entries, _ = launch_set(day)
    assert entries == [('C', 'wait'), ('D', 'wait')]


def test_running_seats_take_their_runtime_room(day):
    # #845 D1: room 2 with A and B running offers nothing more on that runtime.
    usage(day, ('2026-09-29T10:00:00+00:00', 100000, None))
    approved(day, 4, extra='[budget.claude]\nfive_hour = 300000\n')
    for item in 'AB':
        brief(day, item)
    entries, rows = launch_set(day)
    assert entries[:2] == [('A', 'launch'), ('B', 'launch')]
    for row in rows[:2]:
        day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, row))
    entries, rows = launch_set(day)
    assert entries == [('C', 'wait'), ('D', 'wait')] and all(row.get('until') for row in rows)


def test_an_unbriefed_start_takes_its_routed_runtime_room(day):
    usage(day, ('2026-09-29T10:00:00+00:00', 100000, 'claude'))
    approved(day, extra='[budget.codex]\nfive_hour = 100000\n', policy=ROUTED)
    spent(day)
    entries, rows = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'wait'), ('C', 'wait'), ('D', 'wait')]
    assert rows[0]['runtime'] == 'codex' and rows[1]['until'] == '2026-09-29T14:00:00+00:00'


def test_a_spent_window_holds_new_seats_and_leaves_running_ones(day):
    # #845 FR-013: a running seat is never stopped; gate seats wait with the reset.
    approved(day)
    brief(day, 'A')
    _, rows = launch_set(day)
    day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, rows[0]))
    before = day.data['seats'], day.data['builds']
    spent(day)
    entries, rows = launch_set(day)
    assert (day.data['seats'], day.data['builds']) == before
    assert entries == [('B', 'wait'), ('C', 'wait'), ('D', 'wait')]
    assert {row['until'] for row in rows} == {'2026-09-29T14:00:00+00:00'}


def test_gate_seats_wait_for_a_spent_window(day):
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        brief(day, 'A', role, f'{role}-initial')
    spent(day)
    entries, rows = launch_set(day)
    assert entries == [('A', 'wait')] and rows[0]['until'] == '2026-09-29T14:00:00+00:00'


@pytest.mark.parametrize('policy, refused', [(CLAUDE, False), (PROCESS, True)])
def test_launch_guard_compares_with_the_cap_derived_at_launch(day, policy, refused):
    # #528: the day's snapshot says 4; at D's launch, with free memory at the floor, process
    # seats fit only the three running; #658: subagent seats do not read memory and launch.
    from wuwei.registry import Result
    approved(day, policy=policy)
    for item in 'ABC':
        brief(day, item)
    _, rows = launch_set(day)
    for minute, row in enumerate(rows[:3]):
        day.patch.setenv('WUWEI_NOW', f'2026-09-29T12:0{minute}:00Z')
        day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, row))
    day.memory.results['free_memory'] = Result(0, 1024**3)
    relative = brief(day, 'D')
    day.run('build', 'next', 'D')  # #901: under the day's CAP 4 the build is recorded first
    code, reason = guard(day, relative)
    assert (code == 1 and 'CAP 3' in reason) if refused else code == 0, reason
    assert day.data['cap'] == 4


def test_a_day_value_never_changes_cap_or_holds_a_launch(day):
    import os
    from wuwei import state
    approved(day)
    state._write_state(lambda data: data.update(pace='careful'), day.root)
    entries, _ = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'start'), ('C', 'start'), ('D', 'start')]
    day.patch.setattr(os, 'getloadavg', lambda: (34.0, 30.0, 20.0))
    day.patch.setattr(os, 'cpu_count', lambda: 10)
    state._write_state(lambda data: data.update(pace='fast'), day.root)
    entries, _ = launch_set(day)
    assert all(action != 'wait' for _, action in entries)
    assert day.data['cap_bound'] != 'load'
    line = day.run('status', '--line')
    assert 'pace' not in line and 'held by load' not in line
