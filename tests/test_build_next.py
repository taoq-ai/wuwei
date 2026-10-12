"""Build actions are driven by producer-owned seat and check evidence."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from adapters.runtime import claude
from wuwei import registry, state, workspace
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


def outside(seat, action):
    """A builder launched with no build record, as before #901: only with guards.enforce off
    does it register, with the refusal logged."""
    root = seat[0]
    set_enforce(root, False)
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': action['prompt']}})
    assert code == 1 and 'no build record' in reason, reason
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
    row = next(e['payload'] for e in events(day) if e['kind'] == 'seat.usage')
    recorded = row['usage']
    assert row['runtime'] == 'claude'  # #845: the build record's runtime
    assert recorded == {'input_tokens': 14, 'output_tokens': 6,
                        'cost': 'unmeasured', 'model': 'sonnet', 'duration': 3.2}


def test_unknown_build_item_exits_two(seat, capsys):
    assert main(['build', 'next', 'missing']) == 2
    assert 'build: unknown item' in capsys.readouterr().err


def test_agent_launch_refuses_role_assigned_to_codex(seat):
    root, _, _, _, _ = seat
    state._write_state(lambda data: data.update(seat_policy={
        'builder': {'runtime': 'codex', 'model': 'test'}}), root)
    action = build.next_action('A', root=root)
    assert action['runtime'] == 'codex'
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': action['prompt']}})
    assert code == 1 and 'Codex' in reason
    assert not state.read_state(root)['seats']


MISSING = {'test_ids': [], 'error': 'No module named pytest', 'environment': 'pytest not found'}


def resume_yes(root, capsys):
    from fakes import owner
    capsys.readouterr()
    assert main(['plan', 'resume', 'A']) == 1
    owner.answer_card(root, capsys.readouterr().err)
    assert main(['plan', 'resume', 'A']) == 0


def test_a_missing_interpreter_holds_for_a_recheck_and_the_repair_moves_on(seat):
    # #904: an environment failure is a build hold with a recheck action, not an owner park,
    # and no builder round is spent on it.
    root, _, _, day, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    results.append(registry.Result(1, MISSING))
    assert main(['build', 'check', 'A']) == 1
    action = build.next_action('A', root=root)
    assert action['action'] == 'check' and 'build check A' in action['command']
    assert action['reason'].startswith('environment: pytest not found')
    assert state.read_state(root)['items']['A']['phase'] == 'implement'
    results.append(registry.Result(0))  # the interpreter is repaired
    assert main(['build', 'check', 'A']) == 0
    assert build.next_action('A', root=root)['action'] == 'done'
    assert state.read_state(root)['items']['A']['phase'] == 'gate'
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 1


def test_an_unchanged_environment_failure_parks_and_a_resume_rechecks_once(seat, capsys):
    # #904: unchanged environment failures stay bounded (stuck_after rechecks, then the park the
    # owner decides); the owner's resume gives one recheck, and the same failure parks again.
    root, _, _, day, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    for _ in range(3):
        assert build.next_action('A', root=root)['action'] == 'check'
        results.append(registry.Result(1, MISSING))
        assert main(['build', 'check', 'A']) == 1
    action = build.next_action('A', root=root)
    assert action == {'action': 'park', 'reason': 'environment: pytest not found'}
    resume_yes(root, capsys)
    assert build.next_action('A', root=root)['action'] == 'check'
    results.append(registry.Result(1, MISSING))
    assert main(['build', 'check', 'A']) == 1
    assert build.next_action('A', root=root)['action'] == 'park'
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 1


def test_a_resumed_stuck_build_continues_its_builder_once(seat, capsys):
    # #904: plan resume resets the parked build action with the phase, so build next never
    # returns the park the owner just answered; the same failure parks again (bounded).
    root, repo, path, day, results = seat
    for _ in range(3):
        action = build.next_action('A', root=root)
        launch(seat, action, action.get('resume'))
        assert stop(seat) == (0, '')
        results.append(registry.Result(1, {'test_ids': ['test_one'], 'error': 'same failure'}))
        main(['build', 'check', 'A'])
    assert build.next_action('A', root=root)['action'] == 'park'
    resume_yes(root, capsys)
    assert state.read_state(root)['items']['A']['phase'] == 'implement'
    action = build.next_action('A', root=root)
    assert action['action'] == 'continue' and action['resume'] == 'agent-builder'
    assert 'same fast-check failure repeated' in action['feedback']
    launch(seat, action, action['resume'])
    assert stop(seat) == (0, '')
    results.append(registry.Result(1, {'test_ids': ['test_one'], 'error': 'same failure'}))
    assert main(['build', 'check', 'A']) == 1
    assert build.next_action('A', root=root)['action'] == 'park'



@pytest.mark.parametrize('kind', ['stuck', 'environment'])
def test_a_resumed_build_spends_the_resume_at_its_check(seat, capsys, kind):
    # #904 review F1: a build park's resume is answered by the build check; the item reaches its
    # gates with no round grant left, so a PARK, ESCALATE or Blocked card still asks the owner.
    from wuwei import dispatch
    root, _, _, _, results = seat
    failure = MISSING if kind == 'environment' else {'test_ids': ['test_one'], 'error': 'same failure'}
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    for _ in range(3):
        action = build.next_action('A', root=root)
        if action['action'] == 'continue':
            launch(seat, action, action['resume'])
            assert stop(seat) == (0, '')
        results.append(registry.Result(1, failure))
        main(['build', 'check', 'A'])
    assert build.next_action('A', root=root)['action'] == 'park'
    resume_yes(root, capsys)
    assert dispatch._resumed(root, 'A')
    action = build.next_action('A', root=root)
    if action['action'] == 'continue':
        launch(seat, action, action['resume'])
        assert stop(seat) == (0, '')
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    assert state.read_state(root)['items']['A']['phase'] == 'gate'
    assert not dispatch._resumed(root, 'A')


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


def test_stop_uses_measured_failure_and_parks(seat):
    root, repo, path, day, _ = seat
    for iteration in range(3):
        action = build.next_action('A', root=root)
        launch(seat, action, action.get('resume'))
        # Dedicated fast-check producer evidence, never assistant prose.
        state._write_state(lambda data: data.setdefault('fast_checks', {}).update({'app': {
            'test': {'sha': 'a' * 40, 'exit': 1, 'worktree': str(repo), 'clean': True,
                     'build': {'item': 'A', 'brief': str(path.relative_to(root)), 'iteration': iteration + 1},
                     'data': {'test_ids': ['test_one'], 'error': 'same failure'}}}}),
            root, kind='fast_checks.record')
        assert stop(seat) == (0, '')
        if iteration < 2:
            assert build.next_action('A', root=root)['action'] == 'continue'
    action = build.next_action('A', root=root)
    assert action['action'] == 'park'
    assert 'same' in action['reason']
    assert not list((day / 'decisions').glob('D-*.md'))
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
                       root)
    assert stop(seat) == (0, '')
    assert build.next_action('A', root=root)['action'] == 'check'


def test_checks_are_recorded_by_real_producer_before_stop(seat, monkeypatch):
    from wuwei import fast_checks
    root, repo, _, _, results = seat
    action = build.next_action('A', root=root)
    launch(seat, action)
    vcs = registry.load('vcs', {})
    monkeypatch.setattr(fast_checks.commit_push, 'context', lambda *args, **kwargs: (
        {'name': 'app', 'fast_checks': ['test'], 'check_timeout_seconds': 300}, {'path': str(repo)}, vcs))
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
    assert action == {'action': 'park', 'reason': action['reason']} and 'maximum' in action['reason']


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


def test_recorded_result_saves_its_window_readings(seat):
    # #845: a result's windows are saved under the build record's runtime.
    root, _, _, _, _ = seat
    launch(seat, build.next_action('A', root=root))
    record = state.read_state(root)['builds']['A']
    state._write_state(lambda data: data['builds']['A'].update(status='running'), root)
    reading = {'used_percent': 40, 'resets_at': '2026-10-12T14:00:00+00:00'}
    build.record_result('A', {'text': 'done', 'windows': {'five_hour': reading}}, root=root)
    assert json.loads((root / '.wuwei/windows.json').read_text()) == {record['runtime']: {'five_hour': reading}}


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
    monkeypatch.setattr(fast_checks.commit_push, 'context', lambda *args, **kwargs: (
        {'name': 'app', 'fast_checks': ['test'], 'check_timeout_seconds': 300}, {'path': str(repo)}, vcs))
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


def tracked(seat, monkeypatch):
    from fakes.tracker import Fake
    root = seat[0]
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('[adapters]\n', '[adapters]\ntracker="linear"\n'))
    fake = Fake({'claim': registry.Result(0, {})})
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake if kind == 'tracker'
                        else load(kind, config))
    return fake


def test_build_next_needs_no_ticket(seat, monkeypatch):
    root, _, _, day, _ = seat
    fake = tracked(seat, monkeypatch)
    assert main(['build', 'next', 'A']) == 0
    assert 'A' in state.read_state(root)['builds']
    assert not [e for e in events(day) if e['kind'].startswith('duty.')]


def test_build_next_claims_a_recorded_ticket_as_a_duty(seat, monkeypatch):
    root, _, _, day, _ = seat
    fake = tracked(seat, monkeypatch)
    state._write_state(lambda data: data.update(tickets={'A': {'id': 'ENG-7', 'source': 'set'}}),
                       root)
    assert build.next_action('A', root=root)['action'] == 'launch'
    assert [call[:2] for call in fake.calls] == [('claim', ('ENG-7',))]
    duties = [(e['kind'], e['payload']) for e in events(day) if e['kind'].startswith('duty.')]
    assert duties == [('duty.due', {'item': 'A', 'duty': 'tracker.claim', 'ticket': 'ENG-7',
                                    'command': 'wuwei tracker move A claim'}),
                      ('duty.done', {'item': 'A', 'duty': 'tracker.claim', 'ticket': 'ENG-7',
                                     'pr': None})]


def test_checked_event_counts_passed_and_failed(seat):
    root, _, _, day, _ = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    record = state.read_state(root)['builds']['A']
    state._write_state(lambda data: data['builds']['A'].update(commands=['one', 'two']),
                       root)
    build.complete_checks('A', [registry.Result(0), registry.Result(1, {'error': 'broken'})],
                          root=root)
    checked, = [e['payload'] for e in events(day) if e['kind'] == 'build.checked']
    assert (checked['item'], checked['passed'], checked['failed']) == ('A', 1, 1)
    assert record['status'] == 'check'


def checked(seat):
    root = seat[0]
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    if state.read_state(root)['builds']['A']['status'] != 'check':
        state._write_state(lambda data: data['builds']['A'].update(status='check'), root)
    return root, [registry.Result(0)] * len(state.read_state(root)['builds']['A']['commands'])


def test_park_during_passing_checks_keeps_the_item_parked(seat, monkeypatch):
    # #872 F1: a park that lands between the phase read and the move write wins.
    from wuwei import derive, plan
    root, results = checked(seat)
    real = derive.head

    def head(path):
        plan.park('A', 'scanner chain a -> b', root)
        return real(path)
    monkeypatch.setattr(derive, 'head', head)
    build.complete_checks('A', results, root=root)
    row = state.read_state(root)['items']['A']
    assert (row['phase'], row['resume_phase']) == ('parked', 'implement')


def test_checks_passing_while_parked_still_run_the_spec_step(seat, monkeypatch):
    # #872 F3: the spec-step check runs for the phase the item paused in.
    from wuwei import plan, specmode
    root, results = checked(seat)
    plan.park('A', 'scanner chain a -> b', root)
    monkeypatch.setattr(specmode, 'check', lambda *args, **kwargs: (1, 'tasks step missing'))
    assert build.complete_checks('A', results, root=root) == 1
    assert state.read_state(root)['builds']['A']['status'] != 'done'


def test_check_in_flight_refuses_next_and_a_second_check(seat, capsys):
    import subprocess
    import sys
    root, _, _, _, results = seat
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        state._write_state(lambda data: data['builds']['A'].update(check={
            'started_at': '2026-09-28T12:00:00+00:00', 'pid': child.pid}), root)
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


def no_checks(root, posture):
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks=["test"]\n', 'fast_checks=[]\n')
                      + f'[security]\nposture="{posture}"\n')


@pytest.mark.parametrize('posture', ['observe', 'guarded'])
def test_empty_fast_checks_launch_below_strict(seat, posture):
    root, _, _, day, _ = seat
    no_checks(root, posture)
    config = root / '.wuwei/config.toml'  # a stale tests key and day value change nothing
    config.write_text(config.read_text().replace('fast_checks=[]\n', 'fast_checks=[]\ntests="pytest"\n'))
    phase(root, 'planned')
    state._write_state(lambda data: data.update(pace='careful'), root)
    assert build.next_action('A', root=root)['action'] == 'launch'
    assert state.read_state(root)['builds']['A']['commands'] == []
    started = [e for e in events(day) if e['kind'] == 'build.started']
    assert started[-1]['payload']['checks'] == 'none configured'


def test_empty_fast_checks_check_completes_to_gate(seat):
    root, _, _, _, _ = seat
    no_checks(root, 'observe')
    launch(seat, build.next_action('A', root=root))
    assert stop(seat) == (0, '')  # zero checks: the stop completes the build itself
    assert build.next_action('A', root=root)['action'] == 'done'
    assert phase(root) == 'gate'


def test_dispatch_launches_a_briefed_item_with_no_fast_checks(seat):
    from wuwei import dispatch
    root, _, _, _, _ = seat
    no_checks(root, 'observe')
    phase(root, 'planned')
    state._write_state(lambda data: data.update(gate_approved=True, cap=3, approved_items=['A']),
                       root)
    entries = dispatch.launch_set(root)['entries']
    assert [(row['item'], row['action']) for row in entries] == [('A', 'launch')]


def test_strict_builds_without_fast_checks(seat):
    # #832: no fast checks is a state under strict too; CI and the gates are the evidence.
    root, _, _, _, _ = seat
    no_checks(root, 'strict')
    phase(root, 'planned')
    assert build.next_action('A', root=root)['action'] == 'launch'
    assert state.read_state(root)['builds']['A']['commands'] == []


def test_a_new_build_binds_the_routed_runtime(seat):
    # #845: the launch set passes the routed runtime; an existing record keeps its own.
    root = seat[0]
    assert build.next_action('A', root=root, runtime='codex')['runtime'] == 'codex'
    assert state.read_state(root)['builds']['A']['runtime'] == 'codex'
    assert build.next_action('A', root=root)['runtime'] == 'codex'


def test_a_new_build_on_a_spent_runtime_takes_the_alternate(seat):
    root = seat[0]
    state._write_state(lambda data: data.update(seat_policy={
        'builder': {'runtime': 'claude', 'model': 'm', 'alternate': 'codex'}}), root)
    (root / '.wuwei/windows.json').write_text(json.dumps({'claude': {'five_hour': {
        'used_percent': 100, 'resets_at': '2026-09-28T14:00:00+00:00'}}}))
    assert build.next_action('A', root=root)['runtime'] == 'codex'


def test_a_second_build_loop_for_an_item_exits_without_a_job(tmp_path, monkeypatch, capsys):
    # #845 F2: a live loop marker of another process makes a second run a no-op.
    import subprocess
    import sys
    repo, brief, _, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    build.next_action('A', str(brief), str(repo), root=tmp_path)
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        state._write_state(lambda data: data['builds']['A'].update(
            loop={'pid': child.pid, 'started_at': '2026-09-28T12:00:00+00:00'}), tmp_path)
        runtime.calls.clear()
        assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
        assert runtime.calls == [] and 'already running' in capsys.readouterr().err
    finally:
        child.kill()
        child.wait()
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0 and runtime.calls


@pytest.mark.parametrize('bound,policy,code', [('codex', 'claude', 0), ('claude', 'codex', 2)])
def test_run_loop_follows_the_build_record_runtime(tmp_path, monkeypatch, capsys, bound, policy, code):
    # #845: a routed build runs on the runtime its record binds, not the policy runtime.
    repo, brief, _, _ = setup(tmp_path, monkeypatch, [registry.Result(0)])
    build.next_action('A', str(brief), str(repo), root=tmp_path, runtime=bound)
    state._write_state(lambda data: data.update(seat_policy={'builder': {'runtime': policy, 'model': 'm'}}), tmp_path)
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == code
    assert ('Claude builders require' in capsys.readouterr().err) is (code == 2)


@pytest.mark.parametrize('bound,policy,code', [('claude', 'codex', 0), ('codex', 'claude', 1)])
def test_agent_launch_follows_the_build_record_runtime(seat, bound, policy, code):
    # #845: the Agent guard reads a builder's runtime from its build record over the policy.
    root = seat[0]
    state._write_state(lambda data: data.update(seat_policy={'builder': {'runtime': policy, 'model': 'm'}}), root)
    action = build.next_action('A', root=root, runtime=bound)
    found, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': action['prompt']}})
    assert found == code and (('Codex' in reason) is bool(code)), reason


@pytest.mark.parametrize('moved,legacy,headless', [
    (True, False, False), (True, True, False), (False, False, False), (False, True, True)])
def test_a_new_brief_replaces_an_unlaunched_build_past_its_brief_head(seat, moved, legacy, headless):
    # #889: a worktree that moved past an unlaunched build's brief (work done outside the
    # record) takes a new brief at the current HEAD; the build keeps its start head, so the
    # outside commits count as its change and still go through the checks and the gates. A
    # record from before start heads (legacy) starts at the old brief's logged HEAD. A brief
    # logged with no HEAD (headless) is one the guard never refuses: the refusal stands. A
    # fix round's feedback and CI block carry into the new launch.
    root, repo, path, _, results = seat
    if headless:
        log = workspace.day_dir(root) / 'events.jsonl'
        text = log.read_text().replace('"head": "' + 'a' * 40 + '"', '"head": null')
        log.chmod(0o644)
        log.write_text(text)
    (repo / '.git').mkdir()
    (repo / '.git/HEAD').write_text('a' * 40 + '\n')
    old = build.next_action('A', root=root)
    assert state.read_state(root)['builds']['A']['start'] == 'a' * 40
    if legacy:
        state._write_state(lambda data: data['builds']['A'].pop('start'), root)
    tail = '\n\ngate: fix the finding\nCI job: lint'
    state._write_state(lambda data: data['builds']['A']['action'].update(
        feedback='gate: fix the finding', prompt=old['prompt'] + tail), root)
    vcs = registry.load('vcs', None)
    head = 'b' * 40 if moved else 'a' * 40
    vcs.head = lambda *a, **kw: registry.Result(0, {'sha': head})
    vcs.touched = lambda *a, **kw: registry.Result(0, ['cli/app.py'])
    (repo / '.git/HEAD').write_text(head + '\n')
    if moved:
        code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
            'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': old['prompt']}})
        assert code == 1 and 'HEAD changed since brief' in reason
    new = path.with_name('handoff.md')
    new.write_text('Verify the commits already made and finish')
    state.append_event('brief written', {'name': 'handoff', 'item': 'A', 'role': 'builder',
        'gate': False, 'path': str(new.relative_to(root)), 'worktree': str(repo),
        'head': head, 'sha256': hashlib.sha256(new.read_bytes()).hexdigest()}, root)
    if not moved:  # the old brief still launches: the refusal stands
        with pytest.raises(ValueError, match='cannot replace an unfinished build'):
            build.next_action('A', root=root)
        return
    action = build.next_action('A', root=root)
    assert action['action'] == 'launch' and 'handoff.md' in action['prompt']
    assert action['feedback'] == 'gate: fix the finding' and action['prompt'].endswith(tail)
    record = state.read_state(root)['builds']['A']
    assert record['brief'].endswith('handoff.md') and record['start'] == 'a' * 40
    launch(seat, action)
    assert stop(seat) == (0, '')
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    assert build.next_action('A', root=root)['action'] == 'done'
    assert phase(root) == 'gate'


@pytest.mark.parametrize('ancestor', [True, False])
def test_a_fresh_build_starts_at_the_brief_merge_base(seat, ancestor):
    # #889 F4: a hand-back on a later day has no build record; the commits the branch already
    # holds over its base count as the build's change, so a seat that adds nothing is done.
    # A base that is no longer an ancestor of HEAD (a rebase since the brief) starts at HEAD.
    root, repo, path, _, results = seat
    (repo / '.git').mkdir()
    (repo / '.git/HEAD').write_text('a' * 40 + '\n')
    vcs = registry.load('vcs', None)
    vcs.touched = lambda *a, **kw: registry.Result(0, ['cli/app.py'])
    vcs.merge_base = lambda *a, **kw: registry.Result(0, {'sha': ('c' if ancestor else 'd') * 40})
    new = path.with_name('handback.md')
    new.write_text(f'Worktree: {repo}\nHEAD: {"a" * 40}\nMerge-base: {"c" * 40} (origin/main)\n\nFinish')
    state.append_event('brief written', {'name': 'handback', 'item': 'A', 'role': 'builder',
        'gate': False, 'path': str(new.relative_to(root)), 'worktree': str(repo),
        'head': 'a' * 40, 'sha256': hashlib.sha256(new.read_bytes()).hexdigest()}, root)
    launch(seat, build.next_action('A', root=root))
    assert state.read_state(root)['builds']['A']['start'] == ('c' if ancestor else 'a') * 40
    if not ancestor:
        return
    assert stop(seat) == (0, '')
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    assert phase(root) == 'gate'


@pytest.mark.parametrize('recorded', [False, True])
def test_a_brief_a_seat_already_ran_continues_that_seat(seat, recorded):
    # #892: a builder launched straight from its brief runs with no build record; the next
    # build next continues that stopped seat, so the launch registers, and the seat's own
    # commits (from its launch HEAD) count as the build's change. recorded: an older build
    # next already recorded a launch of that used brief (0.29.0 state).
    from wuwei import brief
    root, repo, path, _, results = seat
    (repo / '.git').mkdir()
    (repo / '.git/HEAD').write_text('a' * 40 + '\n')
    outside(seat, brief.seat_action('builder', path, repo, root))
    with pytest.raises(ValueError, match='still running'):
        build.next_action('A', root=root)
    with (root / 'agent.jsonl').open('a') as stream:
        stream.write(json.dumps({'type': 'assistant', 'message': {
            'content': [{'type': 'text', 'text': 'Blocked: none\nGap: none\nChange: none'}]}}) + '\n')
    assert agent_launch.stop({'cwd': str(root), 'agent_type': 'wuwei:builder', 'agent_id': 'agent-builder',
        'agent_transcript_path': str(root / 'agent.jsonl'),
        'last_assistant_message': 'Blocked: none\nGap: none\nChange: none'}) == (0, '')
    assert state.read_state(root)['seats']['builder']['status'] == 'stopped'
    (repo / '.git/HEAD').write_text('b' * 40 + '\n')  # the seat committed
    registry.load('vcs', None).touched = lambda *a, **kw: registry.Result(0, ['cli/app.py'])
    if recorded:
        state._write_state(lambda data: data.setdefault('builds', {}).update(A={
            'brief': str(path.relative_to(root)), 'worktree': str(repo), 'runtime': 'claude',
            'repo': 'app', 'commands': ['test'], 'iteration': 0, 'repeats': 0, 'signature': None,
            'status': 'ready', 'action': brief.seat_action('builder', path, repo, root)}), root)
    action = build.next_action('A', root=root)
    assert action['action'] == 'continue' and action['resume'] == 'agent-builder'
    assert state.read_state(root)['builds']['A']['start'] == 'a' * 40
    launch(seat, action)
    assert stop(seat, 'agent-fresh') == (0, '')
    results.append(registry.Result(0))
    assert main(['build', 'check', 'A']) == 0
    assert phase(root) == 'gate'


def test_an_unmeasured_seat_on_the_recorded_brief_takes_a_fresh_brief(seat):
    # #889 D1: a record an older build next wrote on a brief whose seat ended unmeasured: build
    # next asks for a fresh brief, and the fresh brief replaces the record at the same HEAD.
    from wuwei import brief
    root, repo, path, _, results = seat
    outside(seat, brief.seat_action('builder', path, repo, root))
    state.stop_seat('builder', root, reason='report unreadable')
    state._write_state(lambda data: data.setdefault('builds', {}).update(A={
        'brief': str(path.relative_to(root)), 'worktree': str(repo), 'runtime': 'claude',
        'repo': 'app', 'commands': ['test'], 'iteration': 0, 'repeats': 0, 'signature': None,
        'status': 'ready', 'action': brief.seat_action('builder', path, repo, root)}), root)
    with pytest.raises(ValueError, match='write a fresh brief'):
        build.next_action('A', root=root)
    new = path.with_name('fresh.md')
    new.write_text('Build it again')
    state.append_event('brief written', {'name': 'fresh', 'item': 'A', 'role': 'builder',
        'gate': False, 'path': str(new.relative_to(root)), 'worktree': str(repo),
        'head': 'a' * 40, 'sha256': hashlib.sha256(new.read_bytes()).hexdigest()}, root)
    action = build.next_action('A', root=root)
    assert action['action'] == 'launch' and 'fresh.md' in action['prompt']
    launch(seat, action)


def test_build_next_never_adopts_another_items_seat(seat):
    # #889 D2: a seat that ran the brief for another item is not this build's seat.
    from wuwei import brief
    root, repo, path, _, _ = seat
    outside(seat, brief.seat_action('builder', path, repo, root))
    state._write_state(lambda data: data['seats']['builder'].update(item='B', status='stopped'), root)
    assert build.next_action('A', root=root)['action'] == 'launch'


def set_enforce(root, value):
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write(f'[guards]\nenforce = {str(value).lower()}\n')


def test_a_builder_launch_with_no_build_record_is_refused_and_build_next_launches_it(seat):
    # #901 owner decision: a builder runs on its build record. The refusal names build next
    # (and reconcile for work done outside), and the launch build next returns registers.
    from wuwei import brief
    root, repo, path, _, _ = seat
    prompt = brief.seat_action('builder', path, repo, root)['prompt']
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build A', 'prompt': prompt}})
    assert code == 1 and 'no build record for A' in reason, reason
    assert 'bin/wuwei build next A' in reason and 'bin/wuwei build reconcile A --worktree' in reason
    assert not state.read_state(root)['seats'] and 'A' not in state.read_state(root).get('builds', {})
    action = build.next_action('A', root=root)
    assert action['action'] == 'launch'
    launch(seat, action)
    assert state.read_state(root)['builds']['A']['status'] == 'running'


def test_with_enforce_off_a_builder_with_no_build_record_logs_and_registers(seat, monkeypatch, capsys):
    # #901: guards.enforce = false records guard.would_refuse; the seat registers as before, so
    # build next continues it when it stops (#892).
    import io
    import sys
    from wuwei import brief
    root, repo, path, day, _ = seat
    set_enforce(root, False)
    payload = {'cwd': str(root), 'session_id': 'planner', 'transcript_path': 'planner.jsonl',
               'hook_event_name': 'PreToolUse', 'tool_name': 'Agent', 'tool_input': {
                   'subagent_type': 'wuwei:builder', 'description': 'Build A',
                   'prompt': brief.seat_action('builder', path, repo, root)['prompt']}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert main(['hook', 'PreToolUse']) == 0, capsys.readouterr()
    [logged] = [e['payload'] for e in events(day) if e['kind'] == 'guard.would_refuse']
    assert logged['guard'] == 'agent_launch' and 'no build record for A' in logged['reason']
    assert state.read_state(root)['seats']['builder']['status'] == 'running'


def test_a_sentinel_launch_needs_no_build_record(seat):
    # #901: only builders: the gate and other seats keep their own rules.
    from wuwei import brief
    root, repo, path, _, _ = seat
    gate = path.with_name('arch.md')
    gate.write_text('Review A')
    state.append_event('brief written', {'name': 'arch', 'item': 'A', 'role': 'sentinel-arch',
        'gate': True, 'path': str(gate.relative_to(root)), 'worktree': str(repo),
        'head': 'a' * 40, 'sha256': hashlib.sha256(gate.read_bytes()).hexdigest()}, root)
    state.transition('A', 'gate', root)
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:sentinel-arch', 'description': 'Gate A',
        'prompt': brief.seat_action('sentinel-arch', gate, repo, root)['prompt']}})
    assert 'build record' not in reason
