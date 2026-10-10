"""Steward findings are producer-owned and gate the next planner action."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

from wuwei import state, workspace


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'],
        items={'A': {'phase': 'planned', 'status': 'queued'}}), tmp_path, reserved=False)
    return tmp_path


def test_third_fix_round_requires_dedicated_ack(root):
    from wuwei import dispatch, steward

    for _ in range(3):
        state.append_event('state.transition', {'item': 'A', 'phase': 'fix',
                                                 'phase_changes': {'A': 'fix'}}, root)
    with pytest.raises(dispatch.Refused, match='steward'):
        dispatch.next_step('A', root)
    notes = state.read_state(root)['steward_notes']
    assert len(notes) == 1
    assert notes[0]['item'] == 'A'
    assert 'third fix round' in notes[0]['text']
    with pytest.raises(dispatch.Refused, match='steward'):
        dispatch.next_step('A', root)
    assert len(state.read_state(root)['steward_notes']) == 1
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('steward_acks', [notes[0]['id']], root)
    steward.acknowledge(notes[0]['id'], root)
    with pytest.raises(dispatch.Refused, match='phase'):
        dispatch.next_step('A', root)


def test_review_reads_local_events_only(root, monkeypatch):
    """#617: dispatch next and next reach review; a failing metric read never blocks them."""
    from wuwei import dispatch, metrics, registry

    def unreachable(*args, **kwargs):
        raise AssertionError('review reached the network')
    monkeypatch.setattr(metrics, 'collect', unreachable)
    monkeypatch.setattr(registry, 'load', unreachable)
    for _ in range(3):
        state.append_event('state.transition', {'phase_changes': {'A': 'fix'}}, root)
    with pytest.raises(dispatch.Refused, match='A-fix-3'):
        dispatch.next_step('A', root)


def test_fresh_seat_run_and_pending_decision_queue(root, monkeypatch):
    from wuwei import registry, steward

    day = workspace.day_dir(root)
    (day / 'decisions').mkdir()
    (day / 'decisions/D-1.md').write_text('Question: Proceed?\nRecommendation: Defer\nReversibility: one-way\n')
    calls = []
    fake = SimpleNamespace(dispatch=lambda *args, **kwargs: calls.append((args, kwargs))
                           or registry.Result(0, {'agent_type': 'wuwei:steward'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    assert steward.run(root, trigger='sweep') == 0
    assert calls[0][0][0] == 'steward'
    assert calls[0][0][3] is True
    queue = json.loads((day / 'steward-decisions.json').read_text())
    assert queue[0]['id'] == 'D-1'
    assert queue[0]['recommendation'] == 'Defer'
    assert state.read_state(root)['items']['A']['phase'] == 'planned'
    assert set(state.read_state(root)['items']) == {'A'}
    kinds = [row['kind'] for row in
             (json.loads(line) for line in (day / 'events.jsonl').read_text().splitlines())]
    assert 'brief written' in kinds and 'steward.run' in kinds


def test_failed_steward_launch_leaves_no_brief(root):
    from wuwei import steward

    (root / '.wuwei/config.toml').write_text('[adapters]\nruntime = "none"\n')
    with pytest.raises(ValueError, match='no adapter configured'):
        steward.run(root)
    assert not list((workspace.day_dir(root) / 'briefs').glob('steward-*.md'))


def test_steward_launch_uses_approved_role_runtime(root, monkeypatch):
    from wuwei import registry, steward
    state._write_state(lambda data: data.update(seat_policy={
        'steward': {'runtime': 'codex', 'model': 'test'}}), root, reserved=False)
    selected = []
    adapter = SimpleNamespace(dispatch=lambda *args, **kwargs:
                              registry.Result(0, {'id': 'one'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config:
                        selected.append(config['adapters']['runtime']) or adapter)
    assert steward.run(root) == 0
    assert selected == ['codex']


def test_prior_day_without_steward_is_next_plan_finding(root):
    from wuwei import steward

    old = root / '.wuwei/days/2026-09-28'
    old.mkdir(parents=True)
    (old / 'events.jsonl').write_text(json.dumps({'kind': 'plan.approved', 'payload': {},
                                                  'ts': '2026-09-28T09:00:00Z'}) + '\n')
    assert steward.previous_day_finding(root) == 'prior day had no steward run: 2026-09-28'


def test_plan_displays_prior_day_finding(root, monkeypatch):
    from wuwei import plan
    from test_plan import proposal

    old = root / '.wuwei/days/2026-09-28'
    old.mkdir(parents=True)
    (old / 'events.jsonl').write_text(json.dumps({'kind': 'plan.approved', 'payload': {},
                                                  'ts': '2026-09-28T09:00:00Z'}) + '\n')
    (root / '.wuwei/memory').mkdir()
    (root / '.wuwei/memory/goals.md').write_text('# Goals\n## G-1\noutcome: Ship a useful result\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    state._write_state(lambda data: data.update(gate_approved=False), root, reserved=False)
    assert 'prior day had no steward run' in plan.propose(proposal(), root).read_text()


def test_sweep_and_close_trigger_steward(root, monkeypatch):
    from wuwei import steward, watch
    from wuwei.commands import close

    calls = []
    monkeypatch.setattr(steward, 'run', lambda _root, *, trigger: calls.append(trigger) or 0)
    watch.sweep(root)
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.closing, 'check', lambda _root: (0, ''))
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda _root: (0, []))
    monkeypatch.setattr(close.closing, 'unresolved', lambda _root, _rows, **_: (0, ''))
    assert close.run(SimpleNamespace(check=None)) == 0
    assert calls == ['sweep', 'close']


def test_trace_threshold_marks_steward_due_without_launch(root, monkeypatch, capsys):
    from wuwei.guards.traces import check

    (root / '.wuwei/config.toml').write_text('[steward]\nevery_tool_calls=2\n')
    day = workspace.day_dir(root)
    payload = {'session_id': 'seat', 'cwd': str(root), 'tool_name': 'Read',
               'tool_input': {'file_path': 'README.md'}}
    assert check(payload) == (0, '')
    assert check(payload) == (0, '')
    assert check(payload) == (0, '')
    assert capsys.readouterr().out == ''
    events = [json.loads(line) for line in (day / 'events.jsonl').read_text().splitlines()]
    assert [(row['kind'], row['payload'].get('tool_calls')) for row in events
            if row['kind'].startswith('steward.')] == [('steward.due', 2)]
    assert not list((day / 'briefs').glob('steward-*.md'))
    state.append_event('steward.run', {'trigger': 'tool-calls', 'tool_calls': 3}, root)
    assert check(payload) == (0, '')
    assert check(payload) == (0, '')
    events = [json.loads(line) for line in (day / 'events.jsonl').read_text().splitlines()]
    assert [row['payload']['tool_calls'] for row in events
            if row['kind'] == 'steward.due'] == [2, 5]


def test_trace_threshold_survives_unrelated_metrics_error(root):
    from wuwei.guards.traces import check

    (root / '.wuwei/config.toml').write_text('[steward]\nevery_tool_calls=1\n')
    state.append_event('seat.usage', {'usage': {'cost': -1}}, root)
    payload = {'session_id': 'seat', 'cwd': str(root), 'tool_name': 'Read',
               'tool_input': {'file_path': 'README.md'}}
    assert check(payload) == (0, '')
    events = [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    assert any(row['kind'] == 'steward.due' for row in events)
    assert not any(row['kind'] == 'traces.gap' for row in events)


def test_concurrent_reviews_record_one_note(root, monkeypatch):
    from wuwei import steward

    for _ in range(3):
        state.append_event('state.transition', {'phase_changes': {'A': 'fix'}}, root)
    original = state._write_state
    barrier = Barrier(2)

    def delayed(*args, **kwargs):
        barrier.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(state, '_write_state', delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: steward.review(root), range(2)))
    assert len(state.read_state(root)['steward_notes']) == 1


def test_close_retry_uses_existing_steward_run(root, monkeypatch):
    from wuwei.commands import close
    from wuwei import registry

    state.append_event('steward.run', {'trigger': 'close', 'tool_calls': 0}, root)
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(registry, 'load', lambda *args: pytest.fail('duplicate steward dispatch'))
    monkeypatch.setattr(close.closing, 'check', lambda _root: (1, 'pending'))
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda _root: (0, []))
    monkeypatch.setattr(close.closing, 'unresolved', lambda _root, _rows, **_: (0, ''))
    assert close.run(SimpleNamespace(check=None)) == 1
    assert not list((workspace.day_dir(root) / 'briefs').glob('steward-*.md'))


def test_decision_queue_skips_owner_answered(root):
    from wuwei import steward

    day = workspace.day_dir(root)
    (day / 'decisions').mkdir()
    for name in ('D-1', 'D-2'):
        (day / 'decisions' / (name + '.md')).write_text('Question: Proceed?\nOutcome: pending\n')
    state._write_state(lambda data: data.update(
        decision_outcomes={'D-1': {'option': 'A', 'decided_by': 'owner'}}), root, reserved=False)
    assert [row['id'] for row in steward.decision_queue(root)] == ['D-2']


def test_sweep_brief_carries_calibration_and_close_skips_it(root, monkeypatch):
    from wuwei import calibrate, registry, steward

    briefs = []
    adapter = SimpleNamespace(dispatch=lambda role, path, *args, **kwargs:
                              briefs.append(open(path).read()) or registry.Result(0, {'id': 'one'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: adapter)
    monkeypatch.setattr(calibrate, 'drift', lambda _root: [{'repo': 'acme/widget', 'changed': ['ci_checks']}])
    (root / '.wuwei/calibration.json').write_text(json.dumps({'acme/widget': {'baseline': {'prs': 3}}}))
    assert steward.run(root, trigger='sweep') == 0
    assert ('Calibration: {"baseline": {"acme/widget": {"prs": 3}}, "drift": '
            '[{"changed": ["ci_checks"], "repo": "acme/widget"}]}') in briefs[0]
    monkeypatch.setattr(calibrate, 'drift', lambda _root: pytest.fail('close ran drift'))
    assert steward.run(root, trigger='close') == 0
    assert 'Calibration:' not in briefs[1]


def test_seat_question_without_record_names_the_missing_record(root):
    from wuwei import dispatch
    from wuwei.guards.decision import check_stop

    day = workspace.day_dir(root)
    relative = '.wuwei/days/2026-09-29/briefs/b1.md'
    (day / 'briefs').mkdir()
    (root / relative).write_text('brief')
    transcript = root / 'agent.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {
        'content': 'WUWEI brief: ' + relative + '\nRead instructions.'}}) + '\n')
    data = state.read_state(root)
    data['items']['alpha'] = {'phase': 'gate', 'status': 'running', 'gates': {}}
    data['approved_items'].append('alpha')
    data['seats'] = {'b1': {'role': 'builder', 'item': 'alpha', 'status': 'stopped',
                            'brief': relative}}
    (day / 'state.json').chmod(0o600)
    (day / 'state.json').write_text(json.dumps(data))
    payload = {'cwd': str(root), 'agent_id': 'agent7', 'agent_type': 'wuwei:builder',
               'stop_hook_active': False, 'agent_transcript_path': str(transcript),
               'last_assistant_message': 'Should I use a cache here?'}
    assert check_stop(payload)[0] == 1
    notes = state.read_state(root)['steward_notes']
    assert [note['id'] for note in notes] == ['alpha-question-agent7']
    assert 'decision record' in notes[0]['text']
    with pytest.raises(dispatch.Refused, match='alpha-question-agent7.*decision record'):
        dispatch.next_step('alpha', root)
    assert check_stop(payload)[0] == 1
    assert len(state.read_state(root)['steward_notes']) == 1


def at(monkeypatch, hour, minute=0):
    monkeypatch.setenv('WUWEI_NOW', f'2026-09-29T{hour:02d}:{minute:02d}:00+00:00')


def exchange(root, monkeypatch, hour, kind, **payload):
    at(monkeypatch, hour)
    state.append_event(kind, {'item': 'alpha', **payload}, root)
    at(monkeypatch, 12)


def record(root, name, text, hour=10):
    import os
    from datetime import datetime
    path = workspace.day_dir(root) / 'decisions' / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(text)
    stamp = datetime.fromisoformat(f'2026-09-29T{hour:02d}:30:00+00:00').timestamp()
    os.utime(path, (stamp, stamp))


@pytest.fixture
def loop(root, monkeypatch):
    state._write_state(lambda data: data['items'].update(alpha={'goal': 'G-1'}), root,
                       reserved=False)
    return root, monkeypatch


def loops(root):
    return [row['payload'] for row in
            (json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines())
            if row['kind'] == 'negotiation.loop']


def seven_exchanges(root, monkeypatch):
    record(root, 'D-1.md', 'Question: Cache alpha results?\nContext: none\n')
    record(root, 'C-1.md', 'Question: Which store?\nContext: alpha needs one\nOptions:\nA\nB\n')
    record(root, 'D-2.md', 'Question: Unrelated?\nOptions:\n| alpha | x |\n')
    record(root, 'D-3.md', 'Question: Old alpha one?\n', hour=6)
    exchange(root, monkeypatch, 6, 'gate.received', role='sentinel-arch', verdict='FIX')
    exchange(root, monkeypatch, 6, 'brief written', role='builder')
    for hour in (9, 10, 11):
        exchange(root, monkeypatch, hour, 'gate.received', role='sentinel-arch', verdict='FIX')
    exchange(root, monkeypatch, 10, 'brief written', role='builder')
    exchange(root, monkeypatch, 10, 'brief written', role='sentinel-arch')
    exchange(root, monkeypatch, 10, 'build.checked')
    exchange(root, monkeypatch, 11, 'build.fix_opened')


def test_seven_exchanges_raise_one_loop(loop):
    from wuwei import outward, steward
    root, monkeypatch = loop
    (root / '.wuwei/config.toml').write_text('[steward]\nloop_threshold = 6\n')
    seven_exchanges(root, monkeypatch)
    steward.review(root)
    raised, = loops(root)
    assert raised['item'] == 'alpha'
    assert raised['counts'] == {'records': 2, 'verdicts': 3, 'redispatches': 1, 'continuations': 1}
    assert raised['past_goal'] is False and len(raised['last']) == 2
    assert raised['last'] == ['11:00 arch review FIX', '11:00 fix requested']
    assert raised['reason'].startswith('alpha is going back and forth:')
    assert outward.lint(raised['reason'], 'D1', workspace.load_config(root), to_owner=True)[0] == 0
    assert state.read_state(root)['negotiation_loops']['alpha'] == {
        key: value for key, value in raised.items() if key != 'prs_seen'}
    steward.review(root)
    exchange(root, monkeypatch, 11, 'build.fix_opened')
    steward.review(root)
    assert len(loops(root)) == 1


def test_second_fix_round_raises_alone(loop):
    from wuwei import steward
    root, monkeypatch = loop
    exchange(root, monkeypatch, 1, 'build.fix_opened')
    steward.review(root)
    assert not loops(root)
    exchange(root, monkeypatch, 2, 'build.fix_opened')
    steward.review(root)
    raised, = loops(root)
    assert raised['fix_rounds'] == 2 and raised['counts']['continuations'] == 0


@pytest.mark.parametrize('count,raised', [(9, 0), (10, 1)])
def test_default_threshold(loop, count, raised):
    from wuwei import steward
    root, monkeypatch = loop
    for _ in range(count):
        exchange(root, monkeypatch, 11, 'gate.received', role='sentinel-goal', verdict='FIX')
    steward.review(root)
    assert len(loops(root)) == raised


@pytest.mark.parametrize('goals,past', [
    ('## G-1\noutcome: o\nmeasure: m\ntarget: t\ndate: 2026-09-01\npriority: 1\n', True),
    ('## G-1\noutcome: o\nmeasure: m\ntarget: t\ndate: 2026-12-01\npriority: 1\n', False),
    (None, False)])
def test_loop_past_goal(loop, goals, past):
    from wuwei import steward
    root, monkeypatch = loop
    if goals:
        (root / '.wuwei/memory').mkdir(parents=True)
        (root / '.wuwei/memory/goals.md').write_text('# Goals\n\n' + goals)
    exchange(root, monkeypatch, 1, 'build.fix_opened')
    exchange(root, monkeypatch, 2, 'build.fix_opened')
    steward.review(root)
    assert loops(root)[0]['past_goal'] is past


def test_concurrent_reviews_record_one_loop(loop):
    from wuwei import steward
    root, monkeypatch = loop
    exchange(root, monkeypatch, 1, 'build.fix_opened')
    exchange(root, monkeypatch, 2, 'build.fix_opened')
    original = state._write_state
    barrier = Barrier(2)

    def delayed(*args, **kwargs):
        if kwargs.get('kind') == 'negotiation.loop':
            barrier.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(state, '_write_state', delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: steward.review(root), range(2)))
    assert len(loops(root)) == 1


@pytest.mark.parametrize('config, dues', [('', [250]), ('[steward]\nevery_tool_calls = 100\n', [100, 200])])
def test_default_interval_is_250_tool_calls(root, config, dues):
    from wuwei import steward, watch

    (root / '.wuwei/config.toml').write_text(config)
    path = workspace.day_dir(root) / 'events.jsonl'
    for count in range(1, 251):
        steward.maybe_run_for_tool_calls(count, root)
        rows = watch.records(path)
        if rows and rows[-1]['kind'] == 'steward.due':
            state.append_event('steward.run', {'trigger': 'tool-calls', 'tool_calls': count}, root)
    assert [row['payload']['tool_calls'] for row in watch.records(path)
            if row['kind'] == 'steward.due'] == dues


def at_phase(root, phase):
    from test_next import day

    day(root, items={'A': {'phase': phase, 'status': 'running'}})


@pytest.mark.parametrize('phase', ['fix', 'delta'])
@pytest.mark.parametrize('trigger', ['sweep', 'tool-calls'])
def test_steward_waits_for_the_fix_round(root, monkeypatch, capsys, phase, trigger):
    from wuwei import registry, steward, watch

    at_phase(root, phase)
    monkeypatch.setattr(registry, 'load', lambda *args: pytest.fail('steward launched mid-round'))
    assert steward.run(root, trigger=trigger) == 0
    assert capsys.readouterr().out == 'steward: waits for A to finish the fix round\n'
    day = workspace.day_dir(root)
    assert not list((day / 'briefs').glob('steward-*.md'))
    assert not any(row['kind'] == 'steward.run' for row in watch.records(day / 'events.jsonl'))


def test_close_review_runs_mid_round(root, monkeypatch):
    from wuwei import registry, steward, watch

    at_phase(root, 'fix')
    adapter = SimpleNamespace(dispatch=lambda *args, **kwargs: registry.Result(0, {'id': 'one'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: adapter)
    assert steward.run(root, trigger='close') == 0
    assert [row['payload']['trigger'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == 'steward.run'] == ['close']


@pytest.mark.parametrize('verbosity', ['', '[owner.verbosity]\nreport = "brief"\n'])
def test_report_counts_steward_runs(root, verbosity):
    from wuwei import report

    (root / '.wuwei/config.toml').write_text(verbosity)
    settings = 'Settings: steward.every_tool_calls = 250, watch.sweep_seconds = 7200'
    assert f'## Steward runs\nnone\n{settings}' in report.build(root)
    for trigger in ('tool-calls', 'sweep', 'sweep', 'close'):
        state.append_event('steward.run', {'trigger': trigger, 'tool_calls': 0}, root)
    assert (f'## Steward runs\n- close: 1\n- sweep: 2\n- tool-calls: 1\n{settings}'
            in report.build(root))


def test_tool_call_gate_reads_no_events_below_the_interval(root, monkeypatch):
    """#659: below a run boundary from the base the due check reads nothing."""
    from wuwei import steward, watch

    reads = []
    records = watch.records
    monkeypatch.setattr(watch, 'records', lambda path: reads.append(path) or records(path))
    assert steward.maybe_run_for_tool_calls(10, root, 0) == 0
    assert reads == []
    (root / '.wuwei/config.toml').write_text('[steward]\nevery_tool_calls = 2\n')
    assert steward.maybe_run_for_tool_calls(2, root, 0) == 2
    state.append_event('steward.run', {'trigger': 'tool-calls', 'tool_calls': 3}, root)
    assert steward.maybe_run_for_tool_calls(4, root, 2) == 3
    path = workspace.day_dir(root) / 'events.jsonl'
    assert [row['payload']['tool_calls'] for row in records(path) if row['kind'] == 'steward.due'] == [2]
