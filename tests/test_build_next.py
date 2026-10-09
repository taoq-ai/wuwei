"""Build actions are driven by producer-owned seat and check evidence."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from adapters.runtime import claude
from wuwei import decision, registry, state, workspace
from wuwei.__main__ import main
from wuwei.commands import build
from wuwei.guards import agent_launch
from test_build import setup, events


@pytest.fixture
def seat(tmp_path, monkeypatch):
    repo, original, day, runtime = setup(tmp_path, monkeypatch, [])
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('runtime="codex"', 'runtime="claude"'))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    path = day / 'briefs/builder.md'
    path.parent.mkdir()
    path.write_text(original.read_text())
    state.append_event('brief written', {'name': 'builder', 'item': 'A', 'role': 'builder',
        'gate': False, 'path': str(path.relative_to(tmp_path)), 'worktree': str(repo),
        'head': 'a' * 40, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, tmp_path)
    results = []
    checks = SimpleNamespace(run=lambda *a, **kw: results.pop(0))
    vcs = SimpleNamespace(head=lambda *a, **kw: registry.Result(0, {'sha': 'a' * 40}),
                          status=lambda *a, **kw: registry.Result(0, []),
                          repo_context=lambda *a, **kw: registry.Result(0, {
                              'path': str(repo), 'common_dir': str(repo / '.git')}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {
        'runtime': claude, 'checks': checks, 'vcs': vcs}[kind])
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *a: 8 * 1024**3)
    return tmp_path, repo, path, day, results


def launch(seat, action, resume=None):
    root, _, _, _, _ = seat
    inputs = {'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': action['prompt']}
    if resume:
        inputs['resume'] = resume
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': inputs})
    assert code == 0, reason
    with (root / 'agent.jsonl').open('a') as stream:
        stream.write(json.dumps({'type': 'user', 'message': {'content': action['prompt']}}) + '\n')


def stop(seat, agent_id='agent-builder', **usage):
    root, _, path, _, _ = seat
    transcript = root / 'agent.jsonl'
    if state.read_state(root)['builds']['A']['status'] == 'running':
        with transcript.open('a') as stream:
            stream.write(json.dumps({'type': 'assistant', 'message': {
                'content': [{'type': 'text', 'text': 'Blocked: none\nGap: none\nChange: none'}]}}) + '\n')
    return agent_launch.stop({'cwd': str(root), 'agent_type': 'wuwei:builder',
        'agent_id': agent_id, 'agent_transcript_path': str(transcript),
        'last_assistant_message': 'Blocked: none\nGap: none\nChange: none', **usage})


def test_claude_stop_records_available_usage(seat):
    root, _, _, day, _ = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat, usage={'input_tokens': 14, 'output_tokens': 6, 'duration': 3.2,
                             'model': 'sonnet'}) == (0, '')
    recorded = next(e['payload']['usage'] for e in events(day) if e['kind'] == 'seat.usage')
    assert recorded == {'input_tokens': 14, 'output_tokens': 6,
                        'cost': 'unmeasured', 'model': 'sonnet', 'duration': 3.2}


def test_unknown_build_item_exits_two(seat, capsys):
    assert main(['build', 'next', 'missing']) == 2
    assert 'build: unknown item' in capsys.readouterr().err


def test_agent_launch_refuses_role_assigned_to_codex(seat):
    root, _, _, _, _ = seat
    state._write_state(lambda data: data.update(seat_policy={
        'builder': {'runtime': 'codex', 'model': 'test'}}), root, reserved=False)
    action = build.next_action('A', root=root)
    assert action['runtime'] == 'codex'
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': action['prompt']}})
    assert code == 1 and 'Codex' in reason
    assert not state.read_state(root)['seats']


def test_step_build_parks_missing_pytest_without_continue(seat):
    root, _, _, day, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results.append(registry.Result(1, {'test_ids': [], 'error': 'No module named pytest',
                                       'environment': 'pytest not found'}))
    assert main(['build', 'check', 'A']) == 1
    action = build.next_action('A', root=root)
    assert action['action'] == 'park'
    assert action['reason'] == 'environment: pytest not found'
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 1


def test_claude_launch_check_continue_done_idempotent(seat, monkeypatch, capsys):
    root, repo, path, day, results = seat
    from wuwei import dispatch
    tracker_calls = []
    monkeypatch.setattr(dispatch, 'tracker_call', lambda *args: tracker_calls.append(args))
    action = build.next_action('A', root=root)
    assert action['action'] == 'launch'
    assert tracker_calls == [('A', 'claim', root)]
    assert action['prompt'].splitlines()[0] == 'WUWEI brief: ' + str(path.relative_to(root))
    before = (day / 'events.jsonl').read_bytes()
    assert build.next_action('A', root=root) == action
    assert (day / 'events.jsonl').read_bytes() == before
    launch(seat, action)
    with pytest.raises(ValueError, match='running'):
        build.next_action('A', root=root)
    assert stop(seat) == (0, '')
    check = build.next_action('A', root=root)
    assert check['action'] == 'check' and 'build check A' in check['command']
    assert build.next_action('A', root=root) == check
    results.append(registry.Result(1, {'test_ids': ['test_one'], 'error': 'failure'}))
    capsys.readouterr()
    assert main(['build', 'check', 'A']) == 1
    err = capsys.readouterr().err
    assert 'failure' in err and 'test_one' in err
    action = build.next_action('A', root=root)
    assert action['action'] == 'continue' and 'test_one' in action['feedback']
    assert json.loads(action['feedback'].split(': ', 1)[1]) == {'test_ids': ['test_one'], 'error': 'failure'}
    assert '"test_ids"' in err
    assert action['resume'] == 'agent-builder'
    assert build.next_action('A', root=root) == action
    launch(seat, action, action['resume'])
    assert stop(seat) == (0, '')
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    assert build.next_action('A', root=root)['action'] == 'done'
    # A consumed brief with no pending continue never authorizes another launch.
    assert agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'builder', 'description': 'Build', 'prompt': action['prompt']}})[0] == 1
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 2
    assert len([e for e in events(day) if e['kind'] == 'seat stopped']) == 2
    assert stop(seat) == (0, '')
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 2
    assert len([e for e in events(day) if e['kind'] == 'seat stopped']) == 2


def test_fresh_agent_binds_the_pending_continue(seat, capsys):
    # #614: Claude Code's Agent has no resume; a fresh launch of the continue prompt binds the
    # stopped builder's round, and the fresh agent's stop (a new id) records it.
    root, _, _, day, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results.append(registry.Result(1, {'test_ids': ['test_one'], 'error': 'failure'}))
    assert main(['build', 'check', 'A']) == 1
    action = build.next_action('A', root=root)
    assert action['action'] == 'continue' and action['resume'] == 'agent-builder'
    launch(seat, action)
    data = state.read_state(root)
    assert data['builds']['A']['status'] == data['seats']['builder']['status'] == 'running'
    assert stop(seat, 'agent-builder') == (0, '')  # the replaced agent's late stop records nothing
    assert state.read_state(root)['builds']['A']['status'] == 'running'
    assert stop(seat, 'agent-fresh') == (0, '')
    record = state.read_state(root)['builds']['A']
    assert record['status'] == 'check' and record['agent_id'] == 'agent-fresh'
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 2
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    assert build.next_action('A', root=root)['action'] == 'done'
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': action['prompt']}})
    assert code == 1 and 'brief already used' in reason


def test_stop_uses_measured_failure_and_parks_valid_decision(seat):
    root, repo, path, day, _ = seat
    for iteration in range(3):
        action = build.next_action('A', root=root)
        launch(seat, action, action.get('resume'))
        # Dedicated fast-check producer evidence, never assistant prose.
        state._write_state(lambda data: data.setdefault('fast_checks', {}).update({'app': {
            'test': {'sha': 'a' * 40, 'exit': 1, 'worktree': str(repo), 'clean': True,
                     'build': {'item': 'A', 'brief': str(path.relative_to(root)), 'iteration': iteration + 1},
                     'data': {'test_ids': ['test_one'], 'error': 'same failure'}}}}),
            root, reserved=False, kind='fast_checks.record')
        assert stop(seat) == (0, '')
        if iteration < 2:
            assert build.next_action('A', root=root)['action'] == 'continue'
    action = build.next_action('A', root=root)
    assert action['action'] == 'park'
    assert 'same' in action['reason']
    records = list((day / 'decisions').glob('D-*.md'))
    assert len(records) == 1
    assert decision.lint_file(records[0], record=False)[0] == 0
    before = (day / 'events.jsonl').read_bytes()
    assert build.next_action('A', root=root) == action
    assert (day / 'events.jsonl').read_bytes() == before


@pytest.mark.parametrize('args', [['build', 'A'], ['build', 'A', 'brief.md', 'repo']])
def test_old_claude_form_names_next(seat, args, capsys):
    assert main(args) == 2
    assert 'build next' in capsys.readouterr().err


def test_next_cli_returns_one_json_action(seat, capsys):
    assert main(['build', 'next', 'A']) == 0
    assert json.loads(capsys.readouterr().out)['action'] == 'launch'


@pytest.mark.parametrize('kind', ['build.checked', 'build.check_started', 'seat.usage'])
def test_build_evidence_is_producer_only(seat, kind, capsys):
    assert main(['event', kind, '{}']) == 1
    assert 'reserved' in capsys.readouterr().err
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('builds.A', {'action': 'done'}, seat[0])


def test_codex_uses_next_action(tmp_path, monkeypatch):
    repo, brief, _, _ = setup(tmp_path, monkeypatch, [registry.Result(0)])
    original = build.next_action
    seen = []
    def next_action(*args, **kwargs):
        action = original(*args, **kwargs)
        seen.append(action['action'])
        return action
    monkeypatch.setattr(build, 'next_action', next_action)
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert seen == ['launch', 'check', 'done']


@pytest.mark.parametrize('case', ['old-iteration', 'wrong-tree', 'wrong-head', 'missing-data'])
def test_stop_does_not_reuse_stale_or_incomplete_checks(seat, case):
    root, repo, path, _, results = seat
    action = build.next_action('A', root=root)
    launch(seat, action)
    evidence = {'sha': 'a' * 40, 'exit': 1, 'measured_at': workspace.now().isoformat(),
                'data': {'test_ids': ['old_test'], 'error': 'old'}, 'worktree': str(repo), 'clean': True,
                'build': {'item': 'A', 'brief': str(path.relative_to(root)), 'iteration': 1}}
    if case == 'old-iteration':
        evidence['build']['iteration'] = 0
    if case == 'wrong-tree':
        evidence['worktree'] = str(root / 'another-tree')
    if case == 'wrong-head':
        evidence['sha'] = 'b' * 40
    if case == 'missing-data':
        del evidence['data']
    state._write_state(lambda data: data.setdefault('fast_checks', {}).update({'app': {'test': evidence}}),
                       root, reserved=False)
    assert stop(seat) == (0, '')
    assert build.next_action('A', root=root)['action'] == 'check'


def test_checks_are_recorded_by_real_producer_before_stop(seat, monkeypatch):
    from wuwei import fast_checks
    root, repo, _, _, results = seat
    action = build.next_action('A', root=root)
    launch(seat, action)
    vcs = registry.load('vcs', {})
    monkeypatch.setattr(fast_checks, 'context', lambda *args, **kwargs: (
        {'name': 'app', 'fast_checks': ['test']}, {'path': str(repo)}, vcs))
    results.append(registry.Result(1, {'test_ids': ['test_real'], 'error': 'broken'}))
    assert fast_checks.record(repo) == 1
    assert stop(seat) == (0, '')
    action = build.next_action('A', root=root)
    assert action['action'] == 'continue' and 'test_real' in action['feedback']


def test_maximum_iterations_parks_despite_changing_signature(seat):
    root, _, _, day, results = seat
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('max_iterations=8', 'max_iterations=2'))
    for iteration in range(2):
        action = build.next_action('A', root=root)
        launch(seat, action, action.get('resume'))
        assert stop(seat) == (0, '')
        results.append(registry.Result(1, {'test_ids': [f'test_{iteration}'], 'error': 'broken'}))
        assert main(['build', 'check', 'A']) == 1
    action = build.next_action('A', root=root)
    assert action['action'] == 'park' and 'maximum' in action['reason']
    assert decision.lint_file(root / action['decision'], record=False)[0] == 0


@pytest.mark.parametrize('case', ['unmeasured', 'invalid-exit', 'invalid-usage', 'missing-id'])
def test_failed_measurement_never_completes_build(seat, case, capsys):
    root, _, _, _, results = seat
    launch(seat, build.next_action('A', root=root))
    if case == 'missing-id':
        assert stop(seat, None)[0] == 2
        with pytest.raises(ValueError, match='running'):
            build.next_action('A', root=root)
        return
    if case == 'invalid-usage':
        with pytest.raises(ValueError, match='usage'):
            build.record_result('A', {'usage': {'cost': 'bad'}}, root=root)
        return
    assert stop(seat) == (0, '')
    results.append(registry.Result(2, reason='tool missing') if case == 'unmeasured' else registry.Result(True))
    assert main(['build', 'check', 'A']) == 2
    assert capsys.readouterr().err
    assert build.next_action('A', root=root)['action'] == 'check'


def test_new_brief_after_done_starts_new_build(seat):
    root, repo, path, _, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    new = path.with_name('fix.md')
    new.write_text('Fix the gate finding')
    state.append_event('brief written', {'name': 'fix', 'item': 'A', 'role': 'builder',
        'gate': False, 'path': str(new.relative_to(root)), 'worktree': str(repo),
        'head': 'a' * 40, 'sha256': hashlib.sha256(new.read_bytes()).hexdigest()}, root)
    action = build.next_action('A', root=root)
    assert action['action'] == 'launch' and 'fix.md' in action['prompt']


def test_replayed_stop_cannot_release_resumed_builder(seat):
    root, _, _, day, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results.append(registry.Result(1, {'error': 'broken'}))
    assert build.check('A', root=root) == 1
    action = build.next_action('A', root=root)
    launch(seat, action, action['resume'])
    # Transcript now contains the resumed user turn but no new assistant result.
    payload = {'cwd': str(root), 'agent_type': 'wuwei:builder', 'agent_id': 'agent-builder',
        'agent_transcript_path': str(root / 'agent.jsonl'),
        'last_assistant_message': 'Blocked: none\nGap: none\nChange: none'}
    agent_launch.stop(payload)
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == 'running'
    assert data['builds']['A']['status'] == 'running' and data['builds']['A']['iteration'] == 1
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 1
    assert stop(seat, 'wrong-agent')[0] == 2
    assert state.read_state(root)['seats']['builder']['status'] == 'running'


def test_delayed_checks_cannot_complete_later_iteration(seat, monkeypatch):
    root, _, _, _, _ = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    runner = registry.load('checks', {})
    def delayed(*args, **kwargs):
        build.complete_checks('A', [registry.Result(1, {'error': 'broken'})], root=root)
        action = build.next_action('A', root=root)
        launch(seat, action, action['resume'])
        assert stop(seat) == (0, '')
        return registry.Result(0)
    monkeypatch.setattr(runner, 'run', delayed)
    with pytest.raises(ValueError, match='changed'):
        build.check('A', root=root)
    assert build.next_action('A', root=root)['action'] == 'check'


@pytest.mark.parametrize('when_dirty', ['during-check', 'after-check'])
def test_cached_pass_never_skips_checking_uncommitted_changes(seat, monkeypatch, when_dirty):
    from wuwei import fast_checks
    root, repo, _, _, results = seat
    launch(seat, build.next_action('A', root=root))
    vcs = registry.load('vcs', {})
    monkeypatch.setattr(fast_checks, 'context', lambda *args, **kwargs: (
        {'name': 'app', 'fast_checks': ['test']}, {'path': str(repo)}, vcs))
    if when_dirty == 'during-check':
        monkeypatch.setattr(vcs, 'status', lambda *args, **kw: registry.Result(0, [{'path': 'changed.py'}]))
    results.append(registry.Result(0))
    assert fast_checks.record(repo) == 0
    if when_dirty == 'after-check':
        monkeypatch.setattr(vcs, 'status', lambda *args, **kw: registry.Result(0, [{'path': 'changed.py'}]))
    else:
        monkeypatch.setattr(vcs, 'status', lambda *args, **kw: registry.Result(0, []))
    assert stop(seat) == (0, '')
    assert build.next_action('A', root=root)['action'] == 'check'


def test_delayed_stop_cannot_consume_a_resumed_iteration(seat, monkeypatch):
    root, _, _, _, _ = seat
    launch(seat, build.next_action('A', root=root))
    original = build.record_result
    def delayed(*args, **kwargs):
        original(*args, **kwargs)
        build.complete_checks('A', [registry.Result(1, {'error': 'broken'})], root=root)
        action = build.next_action('A', root=root)
        launch(seat, action, action['resume'])
        return original(*args, **kwargs)
    monkeypatch.setattr(build, 'record_result', delayed)
    code, reason = stop(seat)
    assert code == 2 and 'changed' in reason
    data = state.read_state(root)
    assert data['seats']['builder']['status'] == data['builds']['A']['status'] == 'running'
    assert data['builds']['A']['iteration'] == 1


def phase(root, value=None):
    if value is not None:
        path = workspace.day_dir(root) / 'state.json'
        data = json.loads(path.read_text())
        data['items']['A']['phase'] = value
        path.write_text(json.dumps(data))
    return state.read_state(root)['items']['A']['phase']


def test_launch_moves_planned_to_implement_once(seat):
    root, _, _, day, _ = seat
    phase(root, 'planned')
    action = build.next_action('A', root=root)
    assert phase(root) == 'implement'
    before = (day / 'events.jsonl').read_bytes()
    assert build.next_action('A', root=root) == action
    assert (day / 'events.jsonl').read_bytes() == before


@pytest.mark.parametrize('start,end', [('planned', 'gate'), ('implement', 'gate'), ('fix', 'delta')])
def test_build_done_hands_item_to_next_phase(seat, start, end):
    root, _, _, _, results = seat
    phase(root, start)
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    assert build.next_action('A', root=root)['action'] == 'done'
    assert phase(root) == end
    assert 'fix_rounds' not in state.read_state(root)['builds']['A']


def test_build_next_needs_a_ticket_and_claims_it(seat, monkeypatch, capsys):
    from fakes.tracker import Fake
    root, _, _, _, _ = seat
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('[adapters]\n', '[adapters]\ntracker="linear"\n'))
    fake = Fake({'claim': registry.Result(0, {})})
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake if kind == 'tracker'
                        else load(kind, config))
    assert main(['build', 'next', 'A']) == 1
    assert 'bin/wuwei tracker create A' in capsys.readouterr().err
    assert 'builds' not in state.read_state(root)
    state._write_state(lambda data: data.update(tickets={'A': {'id': 'ENG-7', 'source': 'set'}}),
                       root, reserved=False)
    assert build.next_action('A', root=root)['action'] == 'launch'
    assert [call[:2] for call in fake.calls] == [('claim', ('ENG-7',))]


def test_checked_event_counts_passed_and_failed(seat):
    root, _, _, day, _ = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    record = state.read_state(root)['builds']['A']
    state._write_state(lambda data: data['builds']['A'].update(commands=['one', 'two']),
                       root, reserved=False)
    build.complete_checks('A', [registry.Result(0), registry.Result(1, {'error': 'broken'})],
                          root=root)
    checked, = [e['payload'] for e in events(day) if e['kind'] == 'build.checked']
    assert (checked['item'], checked['passed'], checked['failed']) == ('A', 1, 1)
    assert record['status'] == 'check'


def test_check_in_flight_refuses_next_and_a_second_check(seat, capsys):
    import subprocess
    import sys
    root, _, _, _, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        state._write_state(lambda data: data['builds']['A'].update(check={
            'started_at': '2026-09-28T12:00:00+00:00', 'pid': child.pid}), root, reserved=False)
        for args in (['build', 'next', 'A'], ['build', 'check', 'A']):
            capsys.readouterr()
            assert main(args) == 2
            err = capsys.readouterr().err
            assert 'running since 12:00' in err and 'bin/wuwei build next A' in err
    finally:
        child.kill()
        child.wait()
    assert build.next_action('A', root=root)['action'] == 'check'
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0


@pytest.mark.parametrize('result, code', [
    (registry.Result(0), 0),
    (registry.Result(1, {'test_ids': ['t'], 'error': 'failure'}), 1),
    (registry.Result(1, {'test_ids': [], 'error': 'x', 'environment': 'pytest not found'}), 1)])
def test_check_in_flight_marker_is_recorded_then_cleared(seat, monkeypatch, result, code):
    import os
    from wuwei import fast_checks
    root, _, _, day, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results.append(result)
    seen, original = [], fast_checks.record
    def record(path):
        seen.append(state.read_state(root)['builds']['A'].get('check'))
        return original(path)
    monkeypatch.setattr(fast_checks, 'record', record)
    assert main(['build', 'check', 'A']) == code
    assert seen == [{'started_at': '2026-09-28T12:00:00+00:00', 'pid': os.getpid()}]
    assert any(e['kind'] == 'build.check_started' for e in events(day))
    assert 'check' not in state.read_state(root)['builds']['A']
