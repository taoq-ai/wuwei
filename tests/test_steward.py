"""The steward runs at sweep and close as one fresh seat; it never gates the planner (part 14)."""

import json
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
        items={'A': {'phase': 'planned', 'status': 'queued'}}), tmp_path)
    return tmp_path


def test_fresh_seat_run(root, monkeypatch):
    from wuwei import registry, steward

    day = workspace.day_dir(root)
    calls = []
    fake = SimpleNamespace(dispatch=lambda *args, **kwargs: calls.append((args, kwargs))
                           or registry.Result(0, {'agent_type': 'wuwei:steward'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    assert steward.run(root, trigger='sweep') == 0
    assert calls[0][0][0] == 'steward'
    assert calls[0][0][3] is True
    text = (root / json.loads((day / 'events.jsonl').read_text().splitlines()[-1])['payload']['brief']).read_text()
    assert 'Notes:' not in text and 'Decision queue:' not in text
    assert not (day / 'steward-decisions.json').exists()
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
        'steward': {'runtime': 'codex', 'model': 'test'}}), root)
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
    state._write_state(lambda data: data.update(gate_approved=False), root)
    assert 'prior day had no steward run' in plan.propose(proposal(), root).read_text()


def test_close_triggers_steward(root, monkeypatch):
    # #847: the watch's sweep trigger is gone; close runs the steward.
    from wuwei import steward
    from wuwei.commands import close

    calls = []
    monkeypatch.setattr(steward, 'run', lambda _root, *, trigger: calls.append(trigger) or 0)
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.closing, 'check', lambda _root: (0, ''))
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda _root: (0, []))
    monkeypatch.setattr(close.closing, 'unresolved', lambda _root, _rows, **_: (0, ''))
    assert close.run(SimpleNamespace(check=None)) == 0
    assert calls == ['close']


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


def at_phase(root, phase):
    from test_next import day

    day(root, items={'A': {'phase': phase, 'status': 'running'}})


@pytest.mark.parametrize('phase', ['fix', 'delta'])
@pytest.mark.parametrize('trigger', ['sweep'])
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
    assert '## Steward runs\nnone\n' in report.build(root)
    for trigger in ('sweep', 'sweep', 'close'):  # sweep: days before #847
        state.append_event('steward.run', {'trigger': trigger, 'tool_calls': 0}, root)
    assert '## Steward runs\n- close: 1\n- sweep: 2\n' in report.build(root)
    assert 'watch.sweep_seconds' not in report.build(root)




def test_no_ack_and_no_tool_call_trigger(root, capsys):
    from wuwei.__main__ import main
    for argv in (['steward', 'ack', 'A-fix-3'], ['steward', 'run', '--trigger', 'tool-calls']):
        with pytest.raises(SystemExit):
            main(argv)
