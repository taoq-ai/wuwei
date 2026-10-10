"""In-process Agent guard table, including metadata and stale-evidence bypasses."""

import importlib
import json
import os

import pytest

from test_brief import day, brief, set_seats
from wuwei import registry, state


@pytest.fixture
def launch(day, monkeypatch):
    root, directory, vcs, code_host = day
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'gate', '--worktree', 'tree') == 0
    path = str((directory / 'briefs/gate.md').relative_to(root))
    payload = {'cwd': str(root), 'tool_name': 'Agent', 'tool_input': {
        'prompt': 'WUWEI brief: ' + path, 'description': 'Gate X',
        'subagent_type': 'wuwei:sentinel-arch', 'name': 'gate'}}
    return day, payload


def check(payload):
    return importlib.import_module('wuwei.guards.agent_launch').check(payload)


@pytest.mark.parametrize('case,code,hint', [
    ('clean', 0, ''), ('unlogged', 1, 'logged'), ('wrong-role', 1, 'role'),
    ('wrong-name', 1, 'name'), ('modified', 1, 'modified'), ('missing-file', 2, 'brief'),
    ('phase', 1, 'phase'), ('dirty', 1, 'dirty'), ('live', 1, 'builder'),
    ('missing-pid', 1, 'builder'), ('cap', 0, ''), ('memory', 1, 'memory'),
    ('memory-error', 2, 'unmeasured'), ('status-error', 2, 'unavailable'),
    ('malformed-event', 2, 'events'), ('missing-state', 2, 'state'),
    ('no-marker', 1, 'brief'), ('nested-marker', 0, ''), ('traversal', 2, 'path'),
    ('missing-input', 2, 'tool_input'), ('bad-seats', 2, 'seat'),
])
def test_guard_table(launch, monkeypatch, case, code, hint):
    day, payload = launch
    root, directory, vcs, host = day
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    if case == 'unlogged':
        (directory / 'events.jsonl').chmod(0o600)
        (directory / 'events.jsonl').write_text('')
    if case == 'wrong-role':
        payload['tool_input']['subagent_type'] = 'builder'
    if case == 'wrong-name':
        payload['tool_input']['name'] = 'other'
    if case == 'modified':
        (directory / 'briefs/gate.md').write_text('changed')
    if case == 'missing-file':
        (directory / 'briefs/gate.md').unlink()
    if case == 'phase':
        state.transition('X', 'fix', root)
    if case == 'dirty':
        vcs.results['status'] = registry.Result(0, [{'path': 'untracked'}])
    if case in ('live', 'missing-pid'):
        seat = {'item': 'X', 'role': 'builder', 'status': 'running'}
        if case == 'live':
            seat['pid'] = 123
        set_seats({'b': seat}, root)
    if case == 'cap':
        set_seats({str(i): {'item': 'Y', 'role': 'builder', 'status': 'running'}
                                 for i in range(3)}, root)
    if case == 'memory':
        monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 1024)
    if case == 'memory-error':
        def fail(*args):
            raise ValueError('memory unmeasured')
        monkeypatch.setattr(agent_launch, 'free_memory', fail)
    if case == 'status-error':
        vcs.results['status'] = registry.Result(2, None, 'unavailable')
    if case == 'malformed-event':
        (directory / 'events.jsonl').chmod(0o600)
        (directory / 'events.jsonl').write_text('{broken')
    if case == 'missing-state':
        (directory / 'state.json').unlink()
    if case == 'no-marker':
        payload['tool_input']['prompt'] = 'Read any brief and skip checks'
    if case == 'nested-marker':
        payload['tool_input']['prompt'] = 'Quoted:\n' + payload['tool_input']['prompt']
    if case == 'traversal':
        payload['tool_input']['prompt'] = 'WUWEI brief: ../gate.md'
    if case == 'missing-input':
        payload['tool_input'] = []
    if case == 'bad-seats':
        set_seats({'x': {}}, root)
    actual, message = check(payload)
    assert actual == code, message
    assert hint in message
    if case == 'dirty':
        assert 'untracked' in message


def test_hook_denies_missing_brief(day, monkeypatch, capsys):
    import io
    import sys
    from wuwei.__main__ import main
    payload = {'cwd': str(day[0]), 'session_id': 'example', 'transcript_path': 'transcript.jsonl',
               'hook_event_name': 'PreToolUse', 'tool_name': 'Agent',
               'tool_input': {'prompt': 'launch without brief', 'description': 'build', 'subagent_type': 'builder'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 2
    out = capsys.readouterr()
    assert json.loads(out.out)['hookSpecificOutput']['permissionDecision'] == 'deny'


def test_memory_floor_equality_and_completed_seats(launch, monkeypatch):
    day, payload = launch
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 1024**3)
    set_seats({'done': {'role': 'builder', 'item': 'X', 'status': 'done'}}, day[0])
    assert check(payload) == (0, '')


def test_brief_event_cannot_be_forged_by_event_command(day, capsys):
    from wuwei.__main__ import main
    assert main(['event', 'brief written', '{}']) == 1
    assert 'reserved' in capsys.readouterr().err


@pytest.mark.parametrize('case', ['already-launched', 'already-running'])
def test_unknown_or_reused_launch_refuses(launch, monkeypatch, case):
    day, payload = launch
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    if case == 'already-launched':
        state.append_event('seat launched', {'name': 'gate', 'item': 'X'}, day[0])
    else:
        set_seats({'gate': {'item': 'X', 'role': 'sentinel-arch', 'status': 'running'}}, day[0])
    code, message = check(payload)
    assert code == 1, message


@pytest.mark.parametrize('cap,host_seats,role,code,hint', [
    (1, 3, 'sentinel-quality', 0, ''), (3, 1, 'sentinel-quality', 1, 'host seat'),
    (1, 3, 'builder', 0, ''),
])
def test_build_cap_and_host_seat_ceiling(launch, monkeypatch, cap, host_seats, role, code, hint):
    day, payload = launch
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    (day[0] / '.wuwei/config.toml').write_text(f'cap = {cap}\n[host]\nseats = {host_seats}\n')
    set_seats({'other': {'item': 'Y', 'role': role, 'status': 'running'}}, day[0])
    actual, message = check(payload)
    assert actual == code, message
    assert hint in message


@pytest.mark.parametrize('result,code', [(registry.Result(0, 8 * 1024**3), 0),
    (registry.Result(0, 1024), 1), (registry.Result(2, None, 'unmeasured'), 2),
    (registry.Result(0, None), 2), (registry.Result(0, True), 2)])
def test_memory_port_results(launch, monkeypatch, result, code):
    from fakes.host import Fake
    day, payload = launch
    host = Fake({'free_memory': result})
    previous = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'host' else previous(kind, config))
    assert check(payload)[0] == code
    assert host.calls == [('free_memory', (), day[0])]


def test_brief_logged_for_another_day_does_not_authorize_launch(launch, monkeypatch):
    _, payload = launch
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    assert check(payload)[0] == 2


@pytest.mark.parametrize('inputs', [None, {}, {'subagent_type': 'wuwei:builder'}])
def test_outside_workspace_passes(tmp_path, monkeypatch, inputs):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check({'cwd': str(tmp_path), 'tool_input': inputs}) == (0, '')


@pytest.mark.parametrize('role', ['Explore', 'general-purpose', 'other:helper'])
def test_unrelated_agents_pass_before_parsing(day, role):
    # #676: in a day an untyped launch registers an adhoc seat, so its scope (and the config
    # it reads) decides relevance; before the day nothing past the scope is read or written.
    drop_day(day[1])
    assert check({'cwd': str(day[0]), 'tool_input': {'subagent_type': role}}) == (0, '')
    (day[0] / '.wuwei/config.toml').write_text('broken config')
    assert check({'cwd': str(day[0]), 'tool_input': {'subagent_type': role}})[0] == 2
    assert not (day[1] / 'state.json').exists()


@pytest.mark.parametrize('role', ['builder', 'other:builder', 'wuwei:unknown'])
def test_wuwei_roles_require_briefs(day, role):
    code, message = check({'cwd': str(day[0]), 'tool_input': {
        'subagent_type': role, 'prompt': 'body', 'description': 'work'}})
    assert code == 1 and 'brief' in message


def test_plugin_prefix_matches_logged_charter(launch, monkeypatch):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    launch[1]['tool_input']['subagent_type'] = 'other:sentinel-arch'
    assert check(launch[1]) == (0, '')


@pytest.mark.parametrize('role', ['builder', 'sentinel-arch'])
def test_changed_head_refuses_launch(day, monkeypatch, role):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    assert brief(monkeypatch, 'body', role, 'X', 'head', '--worktree', 'tree') == 0
    day[2].results['head'] = registry.Result(0, {'sha': 'b' * 40})
    path = str((day[1] / 'briefs/head.md').relative_to(day[0]))
    code, message = check({'cwd': str(day[0]), 'tool_input': {
        'subagent_type': role, 'prompt': 'WUWEI brief: ' + path, 'description': 'work'}})
    assert code == 1 and 'HEAD' in message
    assert state.read_state(day[0])['seats'] == {}


@pytest.mark.parametrize('same_brief', [False, True])
def test_concurrent_launches_reserve_once(day, monkeypatch, same_brief):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    (day[0] / '.wuwei/config.toml').write_text('cap = 1\n[host]\nseats = 3\n')
    payloads = []
    for name in ('one', 'two'):
        assert brief(monkeypatch, 'body', 'builder', 'X', name) == 0
        path = str((day[1] / f'briefs/{name}.md').relative_to(day[0]))
        payloads.append({'cwd': str(day[0]), 'tool_input': {
            'subagent_type': 'builder', 'prompt': 'WUWEI brief: ' + path, 'description': 'work'}})
    barrier = Barrier(2)
    def launch(payload):
        barrier.wait(timeout=5)
        return check(payload)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(launch, [payloads[0]] * 2 if same_brief else payloads))
    assert sorted(code for code, _ in results) == [0, 1], results
    assert len(state.read_state(day[0])['seats']) == 1


def test_reservation_stop_and_reuse(launch, monkeypatch):
    import io
    import sys
    from wuwei.__main__ import main
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    day, payload = launch
    assert check(payload) == (0, '')
    seat = state.read_state(day[0])['seats']['gate']
    assert seat.items() >= {'id': 'gate', 'role': 'sentinel-arch', 'item': 'X',
        'brief': payload['tool_input']['prompt'].removeprefix('WUWEI brief: '),
        'head': day[2].results['head'].data['sha'], 'status': 'running'}.items()
    transcript = day[0] / 'agent.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {
        'content': payload['tool_input']['prompt']}}) + '\n')
    stop = {'agent_transcript_path': str(transcript),
            'cwd': str(day[0]), 'session_id': 'session', 'transcript_path': 'transcript.jsonl',
            'last_assistant_message': 'Blocked: none\nGap: none\nChange: none',
            'hook_event_name': 'SubagentStop', 'agent_id': 'gate', 'agent_type': 'sentinel-arch'}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(stop)))
    assert main(['hook', 'SubagentStop']) == 0
    assert state.read_state(day[0])['seats']['gate']['status'] == 'stopped'
    assert check(payload)[0] == 1
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'next', '--worktree', 'tree') == 0
    payload['tool_input']['prompt'] = payload['tool_input']['prompt'].replace('gate.md', 'next.md')
    payload['tool_input']['name'] = 'next'
    assert check(payload) == (0, '')


def test_old_state_gets_empty_seats(launch, monkeypatch):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    day, payload = launch
    data = state.read_state(day[0])
    del data['seats']
    (day[1] / 'state.json').chmod(0o600)
    (day[1] / 'state.json').write_text(json.dumps(data))
    assert check(payload) == (0, '')


def test_reserved_builder_blocks_gate_without_pid(day, monkeypatch):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    assert brief(monkeypatch, 'body', 'builder', 'X', 'build') == 0
    path = str((day[1] / 'briefs/build.md').relative_to(day[0]))
    assert check({'cwd': str(day[0]), 'tool_input': {
        'subagent_type': 'builder', 'prompt': 'WUWEI brief: ' + path, 'description': 'work'}}) == (0, '')
    assert brief(monkeypatch, 'body', 'sentinel-arch', 'X', 'gate', '--worktree', 'tree') == 1


@pytest.mark.parametrize('age,cap,host_seats,item,code,hint', [
    (14401, 3, 3, 'Y', 0, ''),
    (14401, 1, 3, 'Y', 0, ''),
    (14401, 3, 1, 'Y', 1, 'host seat'),
    (14401, 3, 3, 'X', 1, 'builder'),
    (14399, 1, 3, 'Y', 0, ''),
])
def test_stale_reservation_is_named(launch, monkeypatch, age, cap, host_seats, item, code, hint):
    from datetime import timedelta
    from wuwei import workspace
    from wuwei.guards import agent_launch
    day, payload = launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    (day[0] / '.wuwei/config.toml').write_text(
        f'cap = {cap}\n[host]\nseats = {host_seats}\n')
    set_seats({'old-seat': {'item': item, 'role': 'builder', 'status': 'running',
        'started_at': (workspace.now() - timedelta(seconds=age)).isoformat()}}, day[0])
    result, message = check(payload)
    assert result == code, message
    assert hint in message
    if code:
        assert ('stale' in message) == (age > 14400)
        if age > 14400:
            assert 'old-seat' in message
    assert state.read_state(day[0])['seats']['old-seat']['status'] == 'running'


def test_stand_down_event_cannot_release_reservation(launch, monkeypatch, capsys):
    from wuwei.__main__ import main
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    day, payload = launch
    assert check(payload) == (0, '')
    assert main(['event', 'seat stood down', '{"name":"gate"}']) == 1
    assert 'reserved' in capsys.readouterr().err
    assert state.read_state(day[0])['seats']['gate']['status'] == 'running'


@pytest.mark.parametrize('blocks', [False, True])
@pytest.mark.parametrize('next_day', [False, True])
def test_subagent_stop_resolves_runtime_id_from_brief(launch, monkeypatch, blocks, next_day):
    import io
    import sys
    from wuwei.__main__ import main
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    day, payload = launch
    assert check(payload) == (0, '')
    if next_day:
        monkeypatch.setenv('WUWEI_NOW', '2026-09-29T00:01:00+00:00')
        set_seats({'runtime-id': {'role': 'sentinel-arch', 'item': 'Y',
                                 'status': 'running'}}, day[0])
    content = payload['tool_input']['prompt']
    if blocks:
        content = [{'type': 'text', 'text': content}]
    transcript = day[0] / 'agent-runtime.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}}) + '\n')
    stop = {'cwd': str(day[0]), 'session_id': 'session', 'transcript_path': 'parent.jsonl',
            'last_assistant_message': 'Blocked: none\nGap: none\nChange: none',
            'hook_event_name': 'SubagentStop', 'agent_id': 'runtime-id',
            'agent_type': 'wuwei:sentinel-arch', 'agent_transcript_path': str(transcript)}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(stop)))
    assert main(['hook', 'SubagentStop']) == 0
    assert state.read_state(directory=day[1])['seats']['gate']['status'] == 'stopped'
    if next_day:
        assert state.read_state(day[0])['seats']['runtime-id']['status'] == 'running'


def test_builder_stop_requests_discovery(launch, monkeypatch):
    from wuwei.guards import agent_launch
    from wuwei import dispatch
    day, payload = launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    assert check(payload) == (0, '')
    state._write_state(lambda data: data['seats']['gate'].update(role='builder'),
                       day[0], reserved=False)
    transcript = day[0] / 'builder.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {
        'content': payload['tool_input']['prompt']}}) + '\n')
    seen = []
    monkeypatch.setattr(dispatch, 'discovery', lambda trigger, root: seen.append((trigger, root)))
    stop = {'cwd': str(day[0]), 'agent_type': 'builder', 'last_assistant_message': 'done',
            'agent_transcript_path': str(transcript)}
    assert agent_launch.stop(stop) == (0, '')
    assert seen == [('seat-free', day[0])]


def test_builder_stop_reports_unmeasured_discovery(launch, monkeypatch):
    from wuwei.guards import agent_launch
    from wuwei import dispatch
    day, payload = launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    assert check(payload) == (0, '')
    state._write_state(lambda data: data['seats']['gate'].update(role='builder'),
                       day[0], reserved=False)
    transcript = day[0] / 'builder.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {
        'content': payload['tool_input']['prompt']}}) + '\n')
    monkeypatch.setattr(dispatch, 'discovery',
                        lambda trigger, root: (_ for _ in ()).throw(OSError('unreadable queue')))
    code, reason = agent_launch.stop({
        'cwd': str(day[0]), 'agent_type': 'builder', 'last_assistant_message': 'done',
        'agent_transcript_path': str(transcript)})
    assert (code, reason) == (2, 'discovery unmeasured: unreadable queue')
    assert state.read_state(day[0])['seats']['gate']['status'] == 'stopped'
    event = json.loads((day[1] / 'events.jsonl').read_text().splitlines()[-1])
    assert event['kind'] == 'discovery.unmeasured'
    assert 'unreadable queue' in event['payload']['reason']


def test_builder_stop_retry_does_not_repeat_discovery_failure(launch, monkeypatch):
    from wuwei.guards import agent_launch
    from wuwei import dispatch
    day, payload = launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    assert check(payload) == (0, '')
    state._write_state(lambda data: data['seats']['gate'].update(role='builder'),
                       day[0], reserved=False)
    transcript = day[0] / 'builder.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {
        'content': payload['tool_input']['prompt']}}) + '\n')
    calls = []
    def failing_discovery(trigger, root):
        calls.append(trigger)
        raise OSError('tracker down')
    monkeypatch.setattr(dispatch, 'discovery', failing_discovery)
    stop = {'cwd': str(day[0]), 'agent_type': 'builder', 'last_assistant_message': 'done',
            'agent_transcript_path': str(transcript)}
    assert agent_launch.stop(stop) == (2, 'discovery unmeasured: tracker down')
    assert agent_launch.stop({**stop, 'stop_hook_active': True}) == (0, '')
    assert calls == ['seat-free']
    events = [json.loads(line) for line in (day[1] / 'events.jsonl').read_text().splitlines()]
    assert sum(event['kind'] == 'discovery.unmeasured' for event in events) == 1


def test_head_rechecked_after_memory_probe(launch, monkeypatch):
    from wuwei.guards import agent_launch
    day, payload = launch
    def memory(*args):
        day[2].results['head'] = registry.Result(0, {'sha': 'b' * 40})
        return 8 * 1024**3
    monkeypatch.setattr(agent_launch, 'free_memory', memory)
    code, message = check(payload)
    assert code == 1 and 'HEAD' in message
    assert state.read_state(day[0])['seats'] == {}


@pytest.mark.parametrize('case', ['missing-path', 'missing-file', 'no-match', 'invalid-path', 'wrong-role'])
def test_unmatched_stop_records_event_and_allows(launch, monkeypatch, case):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    day, payload = launch
    assert check(payload) == (0, '')
    stop = {'cwd': str(day[0]), 'agent_type': 'sentinel-arch', 'agent_id': 'gate'}
    transcript = day[0] / 'agent.jsonl'
    if case != 'missing-path':
        stop['agent_transcript_path'] = str(transcript)
    content = payload['tool_input']['prompt']
    if case == 'no-match':
        content = content.replace('gate.md', 'absent.md')
    if case == 'invalid-path':
        content = 'WUWEI brief: ../outside/briefs/gate.md'
    if case == 'wrong-role':
        stop['agent_type'] = 'builder'
    if case != 'missing-file':
        transcript.write_text(json.dumps({'type': 'user', 'message': {'content': content}}) + '\n')
    assert agent_launch.stop(stop) == (0, '')
    assert state.read_state(day[0])['seats']['gate']['status'] == 'running'
    event = json.loads((day[1] / 'events.jsonl').read_text().splitlines()[-1])
    assert event['kind'] == 'seat stop unmatched'
    assert event['payload']['agent_id'] == 'gate'
    assert event['payload']['reason']


@pytest.mark.parametrize('inputs', [{}, {'subagent_type': ''}, {'subagent_type': None},
                                    {'subagent_type': '  '}])
def test_default_general_purpose_agent_passes_before_validation(day, inputs):
    drop_day(day[1])
    assert check({'cwd': str(day[0]), 'tool_input': inputs}) == (0, '')
    assert not (day[1] / 'state.json').exists()


def test_default_capacity_fits_builder_and_three_gates(day, monkeypatch):
    from wuwei import workspace
    from wuwei.guards import agent_launch
    root, directory, _, _ = day
    (root / '.wuwei/config.toml').write_text('')
    assert workspace.load_config(root)['host']['seats'] == 0  # derived (#528)
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    monkeypatch.setattr(os, 'cpu_count', lambda: 4)
    state._write_state(lambda data: data['items'].update({'Y': {}}), root, reserved=False)
    for role, item, name in [('builder', 'Y', 'builder'),
                             ('sentinel-arch', 'X', 'arch'),
                             ('sentinel-quality', 'X', 'quality'),
                             ('sentinel-security', 'X', 'security')]:
        assert brief(monkeypatch, 'body', role, item, name, '--worktree', 'tree') == 0
        relative = str((directory / f'briefs/{name}.md').relative_to(root))
        code, reason = check({'cwd': str(root), 'tool_input': {
            'subagent_type': role, 'description': name, 'prompt': 'WUWEI brief: ' + relative}})
        assert code == 0, reason
    assert len(state.read_state(root)['seats']) == 4


def test_ceiling_refusal_names_configuration_key(launch, monkeypatch):
    from wuwei.guards import agent_launch
    day, payload = launch
    (day[0] / '.wuwei/config.toml').write_text('[host]\nseats=1\n')
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    set_seats({'other': {'item': 'Y', 'role': 'sentinel-quality', 'status': 'running'}}, day[0])
    code, reason = check(payload)
    assert code == 1 and 'host.seats' in reason


def test_non_builder_resume_keeps_existing_fresh_brief_contract(launch, monkeypatch):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    launch[1]['tool_input']['resume'] = 'prior-sentinel'
    assert check(launch[1]) == (0, '')


def test_delta_continues_the_stopped_sentinel_by_agent_id(launch, monkeypatch):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    day, payload = launch
    assert check(payload) == (0, '')
    transcript = day[0] / 'agent.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {
        'content': payload['tool_input']['prompt']}}) + '\n')
    assert agent_launch.stop({'cwd': str(day[0]), 'agent_id': 'agent-7',
                              'agent_type': 'wuwei:sentinel-arch', 'last_assistant_message': 'done',
                              'agent_transcript_path': str(transcript)}) == (0, '')
    assert state.read_state(day[0])['seats']['gate']['agent_id'] == 'agent-7'
    day[2].results['head'] = registry.Result(0, {'sha': 'b' * 40})
    for resume in (None, 'agent-other'):
        payload['tool_input'].pop('resume', None)
        if resume:
            payload['tool_input']['resume'] = resume
        code, message = check(payload)
        assert code == 1 and 'brief already used' in message
    payload['tool_input']['resume'] = 'agent-7'
    assert check(payload) == (0, '')
    seat = state.read_state(day[0])['seats']['gate']
    assert seat['status'] == 'running' and seat['head'] == 'b' * 40


def test_second_opinion_brief_is_never_an_agent_launch(launch, monkeypatch):
    from wuwei import brief as writer
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    (root, directory, _, _), payload = launch
    writer.write('sentinel-arch', 'X', 'gate-codex', 'body', worktree='tree', root=root,
                 second_opinion={'role': 'arch', 'runtime': 'codex', 'model': 'm1'})
    second = {**payload, 'tool_input': {**payload['tool_input'], 'name': 'gate-codex',
              'prompt': 'WUWEI brief: ' + str((directory / 'briefs/gate-codex.md').relative_to(root))}}
    code, message = check(second)
    assert code == 1 and message == 'seat not registered: second-opinion brief runs through wuwei dispatch opinion, not Agent'
    assert state.read_state(root)['seats'] == {}
    assert check(payload) == (0, '')


def test_mcp_gate_is_its_own_guard_record(launch, monkeypatch):
    # #331: the seats level never relaxes the MCP launch gate, which applies its own posture.
    from wuwei import mcp
    from wuwei.guards import agent_launch
    assert [(g.event, g.matcher, g.check.__name__) for g in agent_launch.GUARDS] == [
        ('PreToolUse', 'Agent', 'check_mcp'), ('PreToolUse', 'Agent', 'check'),
        ('SubagentStop', None, 'stop')]
    day, payload = launch
    refused = registry.Result(1, reason='MCP registry findings: x')
    calls = []
    monkeypatch.setattr(mcp, 'cached', lambda root: calls.append(root) or refused)
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    assert agent_launch.check_mcp(payload) == (1, 'MCP registry findings: x')
    assert len(calls) == 1
    assert agent_launch.check(payload) == (0, '')
    assert len(calls) == 1
    other = {**payload, 'tool_input': {**payload['tool_input'], 'subagent_type': 'Explore'}}
    assert agent_launch.check_mcp(other) == (0, '')


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_mcp_gate_off_without_scanner(launch, monkeypatch, posture):
    # #424: adapters.scanner = "none" turns the registry gate off in every posture.
    from wuwei import mcp
    from wuwei.guards import agent_launch
    (root, _, _, _), payload = launch
    (root / '.mcp.json').write_text('{"mcpServers": {"docs": {"command": "fake-server"}}}')
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write(f'[security]\nposture = "{posture}"\n')
    assert agent_launch.check_mcp(payload) == (0, mcp.NO_SCANNER)


def test_hook_denies_launch_on_mcp_floor_while_seats_warn(day, monkeypatch, capsys):
    import io
    import sys
    from wuwei import mcp
    from wuwei.__main__ import main
    monkeypatch.setattr(mcp, 'cached', lambda root: registry.Result(1, reason='MCP registry findings: x'))
    with (day[0] / '.wuwei/config.toml').open('a') as config:
        config.write('\n[security.areas]\nintegrity = "off"\n')
    payload = {'cwd': str(day[0]), 'session_id': 'example', 'transcript_path': 'transcript.jsonl',
               'hook_event_name': 'PreToolUse', 'tool_name': 'Agent',
               'tool_input': {'prompt': 'launch without brief', 'description': 'build', 'subagent_type': 'builder'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 2
    reason = json.loads(capsys.readouterr().out)['hookSpecificOutput']['permissionDecisionReason']
    assert reason == 'MCP registry findings: x'


@pytest.mark.parametrize('settings,ticket,code', [
    ('[adapters]\ntracker = "linear"\n', None, 1),
    ('[adapters]\ntracker = "linear"\n', 'ENG-1', 0),
    ('', None, 0),
])
def test_launch_needs_the_item_ticket(launch, monkeypatch, settings, ticket, code):
    day, payload = launch
    root = day[0]
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(settings)
    if ticket:
        state._write_state(lambda data: data.update(tickets={'X': {'id': ticket, 'source': 'set'}}),
                           root, reserved=False)
    actual, message = check(payload)
    assert actual == code, message
    assert ('X has no ticket' in message) == (code == 1)
    assert bool(state.read_state(root)['seats']) == (code == 0)


def test_seat_launched_records_free_mib_and_running(launch, monkeypatch):
    from test_brief import events
    from wuwei.guards import agent_launch
    day, payload = launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 6 * 1024**3)
    set_seats({'other': {'item': 'Y', 'role': 'builder', 'status': 'running'}}, day[0])
    assert check(payload) == (0, '')
    launched = [e for e in events(day[1]) if e['kind'] == 'seat launched'][-1]['payload']
    assert launched['free_mib'] == 6144 and launched['running'] == 1


def test_builder_cap_is_derived_at_launch(day, monkeypatch):
    # #528: the guard derives CAP at launch (here the owner's 3), not the day's snapshot of 1.
    from wuwei.guards import agent_launch
    root, directory, _, _ = day
    (root / '.wuwei/config.toml').write_text('cap = 3\n[host]\nseats = 8\n')
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    state._write_state(lambda data: data.update(cap=1), root, reserved=False)
    for name in ('one', 'two', 'three', 'four'):
        assert brief(monkeypatch, 'body', 'builder', 'X', name) == 0
        relative = str((directory / f'briefs/{name}.md').relative_to(root))
        code, reason = check({'cwd': str(root), 'tool_input': {
            'subagent_type': 'builder', 'description': name, 'prompt': 'WUWEI brief: ' + relative}})
        assert (code, 'CAP 3' in reason) == ((1, True) if name == 'four' else (0, False)), reason


def drop_day(directory):
    for name in ('state.json', state.SNAPSHOT):
        (directory / name).chmod(0o600)
        (directory / name).unlink()


ADHOC_PROMPT = 'Review PR 16 for data access\nRead the diff only.'


def adhoc_launch(root, prompt=ADHOC_PROMPT, **inputs):
    return {'cwd': str(root), 'session_id': 'P', 'tool_name': 'Agent', 'tool_input': {
        'prompt': prompt, 'description': 'Fable review', **inputs}}


def set_posture(root, posture, seats=None):
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write(f'[security]\nposture = "{posture}"\n')
        if seats:
            config.write(f'[security.areas]\nseats = "{seats}"\n')


@pytest.mark.parametrize('posture', ['observe', 'guarded'])
@pytest.mark.parametrize('inputs,kind', [({'subagent_type': 'general-purpose'}, 'general-purpose'),
                                         ({}, 'general-purpose'), ({'subagent_type': ' '}, 'general-purpose'),
                                         ({'subagent_type': 'Explore'}, 'Explore')])
def test_untyped_launch_registers_adhoc_seat(day, posture, inputs, kind):
    # #676: an agent outside the WUWEI seat types is an auditable seat below strict.
    from test_brief import events
    from wuwei import brief as module
    root, directory, _, _ = day
    set_posture(root, posture)
    state._write_state(lambda data: data.update(planner_session_id='P'), root, reserved=False)
    assert check(adhoc_launch(root, **inputs)) == (0, '')
    seat = state.read_state(root)['seats']['adhoc-1']
    assert seat.pop('started_at')
    assert seat == {'id': 'adhoc-1', 'role': 'adhoc', 'item': 'adhoc-1', 'type': kind,
                    'label': kind, 'launcher': 'planner', 'prompt': 'Review PR 16 for data access',
                    'prompt_sha256': module.prompt_digest(ADHOC_PROMPT), 'status': 'running'}
    last = events(directory)[-1]
    assert last['kind'] == 'seat launched' and last['payload']['name'] == 'adhoc-1'
    assert check(adhoc_launch(root, 'Other work', **inputs)) == (0, '')
    assert state.read_state(root)['seats']['adhoc-2']['launcher'] == 'planner'


def test_adhoc_seat_redacts_prompt_and_names_launcher(day):
    root = day[0]
    payload = adhoc_launch(root, 'Use ghp_' + 'a' * 36 + ' to read', subagent_type='general-purpose')
    payload['session_id'] = 'unknown'
    assert check(payload) == (0, '')
    seat = state.read_state(root)['seats']['adhoc-1']
    assert 'ghp_' not in seat['prompt'] and seat['launcher'] == 'adhoc'


@pytest.mark.parametrize('prompt', [None, '', '  '])
def test_untyped_launch_needs_a_prompt_in_a_day(day, prompt):
    code, reason = check(adhoc_launch(day[0], prompt, subagent_type='general-purpose'))
    assert code == 2 and 'prompt' in reason
    assert state.read_state(day[0])['seats'] == {}


def test_untyped_launch_before_the_day_creates_nothing(day):
    root, directory, _, _ = day
    drop_day(directory)
    set_posture(root, 'strict')
    assert check(adhoc_launch(root, subagent_type='general-purpose')) == (0, '')
    assert not (directory / 'state.json').exists()


@pytest.mark.parametrize('seats', [None, 'block'])
def test_strict_refuses_unrecorded_untyped_launch(day, seats):
    root = day[0]
    set_posture(root, 'guarded' if seats else 'strict', seats)
    code, reason = check(adhoc_launch(root, subagent_type='general-purpose'))
    assert code == 1 and 'bin/wuwei seat start --role <role> --adhoc' in reason
    assert state.read_state(root)['seats'] == {}


def adhoc_stop(root, transcript, agent_id='a1', agent_type='general-purpose'):
    return {'cwd': str(root), 'session_id': 'P', 'hook_event_name': 'SubagentStop',
            'agent_id': agent_id, 'agent_type': agent_type, 'agent_transcript_path': str(transcript)}


def subagent_transcript(path, prompt=ADHOC_PROMPT):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': prompt}}) + '\n')
    return path


def test_untyped_stop_stops_its_adhoc_seat(day):
    from test_brief import events
    from wuwei.guards import agent_launch
    root, directory, _, _ = day
    assert check(adhoc_launch(root, subagent_type='general-purpose')) == (0, '')
    assert check(adhoc_launch(root, subagent_type='general-purpose')) == (0, '')
    state._write_state(lambda data: data['seats']['adhoc-2'].update(trace_sessions=['P:a2']),
                       root, reserved=False)
    transcript = subagent_transcript(root / 'agent-a2.jsonl')
    assert agent_launch.stop(adhoc_stop(root, transcript, 'a2')) == (0, '')
    seats = state.read_state(root)['seats']
    assert seats['adhoc-2']['status'] == 'stopped' and seats['adhoc-2']['agent_id'] == 'a2'
    assert seats['adhoc-1']['status'] == 'running'
    assert events(directory)[-1]['kind'] == 'seat stopped'
    assert agent_launch.stop(adhoc_stop(root, transcript, 'a1')) == (0, '')
    assert state.read_state(root)['seats']['adhoc-1']['status'] == 'stopped'


@pytest.mark.parametrize('case', ['no-seat', 'no-path', 'missing-file'])
def test_untraced_stop_is_recorded_and_allowed(day, case):
    from test_brief import events
    from wuwei.guards import agent_launch
    root, directory, _, _ = day
    transcript = root / 'agent-x.jsonl'
    if case != 'missing-file':
        subagent_transcript(transcript)
    payload = adhoc_stop(root, transcript, agent_type='Explore')
    if case == 'no-path':
        del payload['agent_transcript_path']
    assert agent_launch.stop(payload) == (0, '')
    last = events(directory)[-1]
    assert last['kind'] == 'subagent.untraced'
    assert last['payload']['agent_type'] == 'Explore' and last['payload']['agent_id'] == 'a1'
    assert last['payload']['reason']


def test_untraced_stop_before_the_day_records_nothing(day):
    from wuwei.guards import agent_launch
    root, directory, _, _ = day
    drop_day(directory)
    before = (directory / 'events.jsonl').read_text()
    assert agent_launch.stop(adhoc_stop(root, root / 'none.jsonl')) == (0, '')
    assert (directory / 'events.jsonl').read_text() == before
    assert not (directory / 'state.json').exists()


def test_seat_start_records_an_adhoc_reviewer(day, monkeypatch, capsys):
    # #676: under strict the planner registers an ad-hoc reviewer, then launches it.
    from test_brief import events
    from wuwei import brief as module
    from wuwei.__main__ import main
    root, directory, _, _ = day
    set_posture(root, 'strict')
    assert main(['seat', 'start', '--role', 'bad role', '--adhoc', ADHOC_PROMPT]) == 2
    assert main(['seat', 'start', '--role', 'reviewer', '--adhoc', '  ']) == 2
    capsys.readouterr()
    assert main(['seat', 'start', '--role', 'reviewer', '--adhoc', ADHOC_PROMPT]) == 0
    out = capsys.readouterr().out
    assert 'subagent_type general-purpose' in out and 'wuwei why adhoc' in out
    last = events(directory)[-1]
    assert last['kind'] == 'seat adhoc' and last['payload'] == {
        'role': 'reviewer', 'sha256': module.prompt_digest(ADHOC_PROMPT),
        'prompt': 'Review PR 16 for data access'}
    assert check(adhoc_launch(root, subagent_type='general-purpose')) == (0, '')
    assert state.read_state(root)['seats']['adhoc-1']['label'] == 'reviewer'
    assert check(adhoc_launch(root, 'Another prompt', subagent_type='general-purpose'))[0] == 1
    (root / 'report.md').write_text('Done.\n')
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    assert main(['seat', 'stop', 'adhoc-1', '--verdict', str(root / 'report.md')]) == 1
    assert '--unmeasured' in capsys.readouterr().err
    assert state.read_state(root)['seats']['adhoc-1']['status'] == 'running'


def test_seat_start_needs_the_day(day, capsys):
    from wuwei.__main__ import main
    drop_day(day[1])
    assert main(['seat', 'start', '--role', 'reviewer', '--adhoc', ADHOC_PROMPT]) == 2
    assert 'morning' in capsys.readouterr().err


def test_untyped_agent_is_traced_end_to_end(day, capsys):
    # #676 SC-001: launch, a tool call, why adhoc and the stop of a general-purpose agent.
    from wuwei.__main__ import main
    from wuwei.guards import agent_launch, traces
    root, directory, _, _ = day
    set_posture(root, 'observe')
    assert check(adhoc_launch(root, subagent_type='general-purpose')) == (0, '')
    transcript = subagent_transcript(root / 'P/subagents/agent-a1.jsonl')
    call = {'cwd': str(root), 'session_id': 'P', 'transcript_path': str(root / 'P.jsonl'),
            'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'tool_input': {'file_path': 'README.md'},
            'agent_id': 'a1', 'agent_type': 'general-purpose'}
    assert traces.check(call) == (0, '')
    spans = (directory / 'traces.jsonl').read_text()
    assert '"P:a1"' in spans and 'general-purpose' in spans
    assert state.read_state(root)['seats']['adhoc-1']['trace_sessions'] == ['P:a1']
    capsys.readouterr()
    assert main(['why', 'adhoc']) == 0
    out = capsys.readouterr().out
    assert 'adhoc seat adhoc-1: general-purpose' in out and 'traces: P:a1' in out
    assert agent_launch.stop(adhoc_stop(root, transcript)) == (0, '')
    assert state.read_state(root)['seats']['adhoc-1']['status'] == 'stopped'


def own_prompt(root, payload):
    # #660: WUWEI's launch prompt for the logged gate brief, as build next and dispatch next print it.
    from wuwei import brief as module, security
    relative = module.reference(payload['tool_input']['prompt'])
    return module.launch_prompt(root / relative, security.agent_path(root, 'sentinel-arch'), root=root)


NOTE = 'Planner note: watch the cache.'


@pytest.mark.parametrize('shape', ['appended', 'prepended', 'middle', 'bare'])
def test_planner_note_keeps_the_launch_registered(launch, monkeypatch, shape):
    # #660: a note around WUWEI's prompt, or the marker on any line, still registers the seat.
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    (root, _, _, _), payload = launch
    own = own_prompt(root, payload)
    marker = payload['tool_input']['prompt']
    payload['tool_input']['prompt'] = {
        'appended': own + '\n\n' + NOTE, 'prepended': NOTE + '\n\n' + own,
        'middle': 'Review the gate.\n' + marker + '\nKeep it short.', 'bare': own}[shape]
    assert check(payload) == (0, '')
    seat = state.read_state(root)['seats']['gate']
    assert seat.get('planner_note') == {'appended': NOTE, 'prepended': NOTE,
                                'middle': 'Review the gate.\n\nKeep it short.', 'bare': None}[shape]


@pytest.mark.parametrize('secret', [False, True])
def test_planner_note_is_redacted_and_capped(launch, monkeypatch, secret):
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    (root, _, _, _), payload = launch
    note = 'n' * 600 + (' ghp_' + 'a' * 36 if secret else '')
    payload['tool_input']['prompt'] = own_prompt(root, payload) + '\n\n' + note
    assert check(payload) == (0, '')
    stored = state.read_state(root)['seats']['gate']['planner_note']
    assert len(stored) <= 500 and 'ghp_' not in stored
    assert secret or stored == 'n' * 500


def test_planner_note_falls_back_when_the_prompt_cannot_be_rebuilt(launch, monkeypatch):
    from wuwei import brief as module
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    (root, _, _, _), payload = launch
    marker = payload['tool_input']['prompt']
    payload['tool_input']['prompt'] = own_prompt(root, payload) + '\n\n' + NOTE

    def fail(*args, **kwargs):
        raise ValueError('unavailable')
    monkeypatch.setattr(module, 'launch_prompt', fail)
    assert check(payload) == (0, '')
    expected = payload['tool_input']['prompt'].replace(marker, '', 1).strip()
    assert state.read_state(root)['seats']['gate']['planner_note'] == expected[:500]


def test_prepended_note_seat_stops_by_its_transcript(launch, monkeypatch):
    from test_brief import events
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *args: 8 * 1024**3)
    (root, directory, _, _), payload = launch
    payload['tool_input']['prompt'] = NOTE + '\n\n' + own_prompt(root, payload)
    assert check(payload) == (0, '')
    transcript = subagent_transcript(root / 'agent-g.jsonl', payload['tool_input']['prompt'])
    assert agent_launch.stop({'cwd': str(root), 'agent_id': 'g', 'agent_type': 'wuwei:sentinel-arch',
                              'last_assistant_message': 'done',
                              'agent_transcript_path': str(transcript)}) == (0, '')
    assert state.read_state(root)['seats']['gate']['status'] == 'stopped'
    assert all(row['kind'] != 'seat stop unmatched' for row in events(directory))


UNBRIEFED_PROMPT = 'Review the gate of this item\nRead the diff only.'


def unbriefed(root, description='Gate X', prompt=UNBRIEFED_PROMPT):
    return {'cwd': str(root), 'session_id': 'P', 'tool_name': 'Agent', 'tool_input': {
        'prompt': prompt, 'description': description, 'subagent_type': 'wuwei:sentinel-arch'}}


@pytest.mark.parametrize('posture', ['observe', 'guarded'])
@pytest.mark.parametrize('description,item', [('Gate X', 'X'), ('Gate', None), ('Gate X and Y', None)])
def test_unbriefed_typed_launch_registers_an_adhoc_seat(day, posture, description, item):
    # #660: a WUWEI seat type launched with no marker is never silently unregistered.
    from test_brief import events
    from wuwei import brief as module
    root, directory, _, _ = day
    set_posture(root, posture)
    state._write_state(lambda data: data['items'].update(Y={'phase': 'planned'}), root, reserved=False)
    code, reason = check(unbriefed(root, description))
    assert code == 1
    named = item or "<item>"
    assert reason.startswith('unbriefed launch registered as adhoc seat adhoc-1 for '
                             + (item or "no item of today's plan")), reason
    assert f'bin/wuwei brief sentinel-arch {named} <name>' in reason
    seat = state.read_state(root)['seats']['adhoc-1']
    assert seat['role'] == 'adhoc' and seat['item'] == (item or 'adhoc-1')
    assert seat['label'] == 'sentinel-arch' and seat['type'] == 'wuwei:sentinel-arch'
    assert seat['prompt_sha256'] == module.prompt_digest(UNBRIEFED_PROMPT) and seat['status'] == 'running'
    last = events(directory)[-1]
    assert last['kind'] == 'seat launched' and last['payload']['item'] == (item or 'adhoc-1')


def test_strict_refuses_an_unbriefed_typed_launch(day, monkeypatch, capsys):
    from test_brief import events
    from wuwei.__main__ import main
    root, directory, _, _ = day
    set_posture(root, 'strict')
    assert main(['seat', 'start', '--role', 'reviewer', '--adhoc', UNBRIEFED_PROMPT]) == 0
    before = events(directory)
    code, reason = check(unbriefed(root))
    assert code == 1 and 'bin/wuwei brief sentinel-arch X <name>' in reason
    assert state.read_state(root)['seats'] == {} and events(directory) == before


def test_launch_refusals_say_the_seat_is_not_registered(launch, monkeypatch):
    (root, directory, _, _), payload = launch
    payload['tool_input']['prompt'] = 'WUWEI brief: ' + str((directory / 'briefs/other.md').relative_to(root))
    code, reason = check(payload)
    assert code == 1 and reason.startswith('seat not registered: no brief logged'), reason


def test_unbriefed_seat_stops_and_traces_as_adhoc(day):
    from test_brief import events
    from wuwei.guards import agent_launch, traces
    root, directory, _, _ = day
    assert check(unbriefed(root))[0] == 1
    transcript = subagent_transcript(root / 'P/subagents/agent-a1.jsonl', UNBRIEFED_PROMPT)
    call = {'cwd': str(root), 'session_id': 'P', 'transcript_path': str(root / 'P.jsonl'),
            'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'tool_input': {'file_path': 'README.md'},
            'agent_id': 'a1', 'agent_type': 'wuwei:sentinel-arch'}
    assert traces.check(call) == (0, '')
    assert state.read_state(root)['seats']['adhoc-1']['trace_sessions'] == ['P:a1']
    assert agent_launch.stop(adhoc_stop(root, transcript, agent_type='wuwei:sentinel-arch')) == (0, '')
    assert state.read_state(root)['seats']['adhoc-1']['status'] == 'stopped'
    assert check(unbriefed(root))[0] == 1
    assert agent_launch.stop(adhoc_stop(root, root / 'missing.jsonl', 'a2', 'wuwei:sentinel-arch')) == (0, '')
    assert events(directory)[-1]['kind'] == 'seat stop unmatched'
