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
    assert not any(row['kind'] == 'hook.post_tool_use_error' for row in events)


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
    from wuwei import steward

    state.append_event('steward.run', {'trigger': 'close', 'tool_calls': 0}, root)
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(steward, 'run', lambda *args, **kwargs: pytest.fail('duplicate steward run'))
    monkeypatch.setattr(close.closing, 'check', lambda _root: (1, 'pending'))
    assert close.run(SimpleNamespace(check=None)) == 1
