"""Recorded process metrics have explicit missing and corrupt source behavior."""

import json
from pathlib import Path

import pytest

from wuwei import state, workspace
from wuwei.__main__ import main


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    return tmp_path


def test_metrics_from_recorded_events(root, capsys):
    from wuwei import metrics

    state._write_state(lambda data: data.update(items={'A': {'phase': 'planned', 'goal': 'unplanned'},
                                                        'B': {'phase': 'planned', 'goal': 'G-1'}}),
                       root, reserved=False)
    for _ in range(3):
        state.append_event('state.transition', {'item': 'A', 'phase': 'fix',
                                                 'phase_changes': {'A': 'fix'}}, root)
    state.append_event('reply: acknowledged', {'pr': 'org/repo#1'}, root)
    state.append_event('verdict.rejected', {'file': 'gate.md'}, root)
    state.append_event('decision.decided', {'id': 'D-1', 'reversibility': 'two-way',
                                            'decided_by': 'seat'}, root)
    state.append_event('seat.usage', {'item': 'A', 'role': 'builder', 'iteration': 1,
                                      'usage': {'cost': 0.5}}, root)
    state.append_event('build.parked', {'item': 'A'}, root)
    value = metrics.collect(root)
    assert value['fix_rounds_per_item']['A'] == 3
    assert value['handbacks_per_pr']['org/repo#1'] == 1
    assert value['verdict_lint_rejections'] == 1
    assert value['decisions_per_day'] == 1
    assert value['decisions_by_reversibility']['two-way'] == 1
    assert value['share_unplanned_work'] == 0.5
    assert value['build_loop_iterations_per_item']['A'] == 1
    assert value['stuck_parks_per_item']['A'] == 1
    assert value['cost_per_item']['A'] == 0.5
    assert value['seat_decisions_owner_reversed'] == 0
    assert main(['metrics']) == 0
    assert json.loads(capsys.readouterr().out)['fix_rounds_per_item']['A'] == 3


def test_unmeasured_seat_cost_remains_unmeasured(root):
    from wuwei import metrics
    state.append_event('seat.usage', {'item': 'A', 'role': 'builder', 'iteration': 1,
                                      'usage': {'cost': 'unmeasured'}}, root)
    value = metrics.collect(root)
    assert value['cost_per_item'] == 'unmeasured'
    assert value['cost_per_role'] == 'unmeasured'


def test_missing_source_is_unmeasured_and_corrupt_source_exits_two(root, capsys):
    from wuwei import metrics

    assert metrics.collect(root)['fix_rounds_per_item'] == 'unmeasured'
    assert main(['metrics']) == 0
    directory = workspace.day_dir(root)
    directory.mkdir(parents=True)
    (directory / 'events.jsonl').write_text('{broken}\n')
    assert main(['metrics']) == 2
    assert 'events' in capsys.readouterr().err


def test_owner_routing_counts_once_and_separately_from_seat_decisions(root, monkeypatch):
    from test_decision import VALID
    from wuwei import metrics

    monkeypatch.chdir(root)
    path = workspace.day_dir(root) / 'decisions/D-3.md'
    path.parent.mkdir(parents=True)
    path.write_text(VALID.replace('Reversibility: two-way', 'Reversibility: one-way'))
    assert main(['decision', 'route', 'D-3']) == 0
    assert main(['decision', 'route', 'D-3']) == 0
    value = metrics.collect(root)
    assert value['decisions_per_day'] == 1
    assert value['owner_decisions_per_day'] == 1
    assert value['decisions_by_reversibility'] == {'one-way': 1}


def test_phase_time_includes_initial_planned_interval(root, monkeypatch):
    from wuwei import metrics

    state.append_event('plan.approved', {'items': ['A']}, root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T13:00:00Z')
    state.append_event('state.transition', {'item': 'A', 'phase': 'fix',
                                             'phase_changes': {'A': 'fix'}}, root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T14:00:00Z')
    assert metrics.collect(root)['time_in_phase_seconds']['A'] == {
        'planned': 3600.0, 'fix': 3600.0}
