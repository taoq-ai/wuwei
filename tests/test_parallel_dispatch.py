"""Issue #474: the day starts in parallel, through the hooks on the fixture day."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GOALS = ('A', 'G-1', 1), ('B', 'G-2', 2), ('C', 'G-1', 3), ('D', 'G-2', 5)
CLAUDE = {'builder': {'runtime': 'claude', 'model': 'scripted'}}
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
    return day.run('brief', role, item, name or f'{item}-builder', '--worktree', day.repo,
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
    assert code == 1 and 'CAP 3' in reason
    (day.root / '.wuwei/calibration.json').write_text('{"acme/widget": {"date": "2026-09-29"}}\n')
    step = json.loads(day.run('next', '--json'))
    while step['state'] in ('calibrate', 'telemetry'):  # the first day's cards come once (#551)
        step = json.loads(day.run('next', '--json'))
    assert step['state'] == 'wait'
    assert 'D waits' in step['why'] and 'A-builder started first' in step['why']
    assert 'seats 3/3 by owner (builder, builder, builder)' in day.run('status', '--line')
    assert 'by owner (builder, builder, builder) · builders G-1 2, G-2 1' in day.run('status')


def test_owner_cap_one_stays_sequential(day):
    approved(day, 1)
    entries, _ = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'wait'), ('C', 'wait'), ('D', 'wait')]
    brief(day, 'A')
    _, rows = launch_set(day)
    day.hook('PreToolUse', tool_name='Agent', tool_input=agent(day, rows[0]))
    code, reason = guard(day, brief(day, 'B'))
    assert code == 1 and 'CAP 1' in reason


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


def test_gate_seats_wait_when_host_seats_cannot_hold_them_together(day):
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        brief(day, 'A', role, f'{role}-initial')
    config = day.root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '[host]\nseats = 2\n')
    entries, rows = launch_set(day)
    assert entries == [('A', 'wait')] and 'host.seats=2' in rows[0]['reason']


def test_docs_skill_and_charter_name_the_parallel_start():
    skill = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    assert 'wuwei dispatch next --all' in (ROOT / 'cli/wuwei/commands/next.py').read_text()  # #551
    assert 'in one message' in skill and 'concurrently' in skill
    assert '### Seats per goal' in (ROOT / 'docs/site/concepts.md').read_text()
    row = next(line for line in (ROOT / 'docs/site/configuration.md').read_text().splitlines()
               if line.startswith('| `cap`'))
    assert 'calibrate' in row and 'morning gate' in row
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


def test_token_budget_fitting_two_seats_starts_two(day):
    # #528 US2: the prior day measured 100000 tokens per seat; 200000 a day fits two.
    prior = day.root / '.wuwei/days/2026-09-28/events.jsonl'
    prior.parent.mkdir(parents=True)
    prior.write_text(''.join(json.dumps({'ts': '2026-09-28T10:00:00+00:00', 'kind': 'seat.usage',
                                         'payload': {'item': 'A', 'usage': {
                                             'input_tokens': 60000, 'output_tokens': 40000}}}) + '\n'
                             for _ in range(2)))
    approved(day, extra='[budget]\ntokens_per_day = 200000\n')
    assert 'CAP: cap 2 (budget)' in (day.directory / 'plan.md').read_text()
    entries, _ = launch_set(day)
    assert entries == [('A', 'start'), ('B', 'start'), ('C', 'wait'), ('D', 'wait')]
    assert 'seats 0/2 by budget |' in day.run('status', '--line') and 'bound budget' not in day.run('status')


def test_derived_cap_records_are_reserved(day, capsys):
    from wuwei import signal, state
    from wuwei.__main__ import main
    approved(day)
    assert main(['event', 'cap.derived', '{}']) == 1
    assert 'wuwei dispatch next --all' in capsys.readouterr().err
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('cap_bound', 'host', day.root)
    assert 'cap.derived' in signal.SILENT


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
    code, reason = guard(day, brief(day, 'D'))
    assert (code == 1 and 'CAP 3' in reason) if refused else code == 0, reason
    assert day.data['cap'] == 4
