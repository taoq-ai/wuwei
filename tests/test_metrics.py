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


def test_one_rejection_per_verdict_file_version(root):
    import re
    from wuwei import metrics, verdict
    state._write_state(lambda data: None, root, reserved=False)
    path = workspace.day_dir(root) / 'decisions/gate-quality.md'
    path.parent.mkdir()
    path.write_text('Verdict: maybe\n')
    for _ in range(3):
        assert verdict.lint_file(path, role='sentinel-quality')[0] == 1
    assert metrics.collect(root)['verdict_lint_rejections'] == 1
    path.write_text('Verdict: nope\n')
    verdict.lint_file(path, role='sentinel-quality')
    assert metrics.collect(root)['verdict_lint_rejections'] == 2
    verdict.lint_file(path.with_name('gate-missing.md'), role='sentinel-quality')
    rows = [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    digests = [row['payload']['sha256'] for row in rows if row['kind'] == 'verdict.rejected']
    assert all(re.fullmatch('[0-9a-f]{64}', digest) for digest in digests[:-1])
    assert digests[-1] is None


def test_escaped_defects_counted_per_computed_tier(root, monkeypatch):
    from wuwei import metrics

    def merged(computed):
        return {'phase': 'merged', 'gates': {'tier': computed, 'computed': computed,
                                             'reasons': [], 'roles': ['quality']}}
    assert metrics.collect(root)['escaped_defects_per_tier'] == metrics.UNMEASURED
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    state._write_state(lambda data: data.update(items={'A': merged('light'), 'C': merged('standard')}),
                       root, reserved=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    briefs = workspace.day_dir(root) / 'briefs'
    briefs.mkdir(parents=True)
    (briefs / 'b.md').write_text('Fix the regression from A.\n')
    (briefs / 'gate.md').write_text('Review C.\n')
    state._write_state(lambda data: data.update(items={'B': merged('standard')}), root, reserved=False)
    for name, role in (('b', 'builder'), ('gate', 'sentinel-quality')):
        state.append_event('brief written', {'item': 'B', 'role': role, 'name': name,
                                             'path': str((briefs / f'{name}.md').relative_to(root))}, root)
    assert metrics.collect(root)['escaped_defects_per_tier'] == {
        'light': {'merged': 1, 'escaped': 1}, 'standard': {'merged': 2, 'escaped': 0}}


def stamped(monkeypatch, root, at, kind, payload):
    monkeypatch.setenv('WUWEI_NOW', f'2026-09-29T{at}+00:00')
    state.append_event(kind, payload, root)


def banded_day(monkeypatch, root):
    """A planner day: young until midday, older in the evening, compacted late."""
    (root / '.wuwei/config.toml').write_text('[owner]\ntimezone = "UTC"\n')
    stamped(monkeypatch, root, '08:00:00', 'plan.session', {'session_id': 'P'})
    for minute in range(10):
        stamped(monkeypatch, root, f'08:{minute + 1:02}:00', 'session.seen', {'session_id': 'P', 'hook': 'Stop'})
    stamped(monkeypatch, root, '09:00:00', 'gate.received', {'item': 'A', 'verdict': 'PASS'})
    stamped(monkeypatch, root, '12:00:00', 'gate.received', {'item': 'A', 'verdict': 'FIX'})
    for minute in range(60):
        stamped(monkeypatch, root, f'15:{minute:02}:00', 'session.seen', {'session_id': 'P', 'hook': 'Stop'})
    stamped(monkeypatch, root, '19:00:00', 'gate.received', {'item': 'A', 'verdict': 'FIX'})
    stamped(monkeypatch, root, '19:05:00', 'state.transition', {'item': 'A', 'phase_changes': {'A': 'fix'}})
    for _ in range(2):
        stamped(monkeypatch, root, '19:10:00', 'verdict.rejected', {'file': 'gate.md', 'sha256': 'a' * 64})
    stamped(monkeypatch, root, '20:00:00', 'session.seen', {'session_id': 'P', 'hook': 'SessionStart:compact'})
    stamped(monkeypatch, root, '23:00:00', 'gate.received', {'item': 'A', 'verdict': 'PASS'})
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T23:30:00+00:00')


def test_quality_by_hour_and_session_age(root, monkeypatch):
    from zoneinfo import ZoneInfo
    from wuwei import metrics
    assert metrics.collect(root)['quality_by_band'] == 'unmeasured'
    banded_day(monkeypatch, root)
    table = metrics.collect(root)['quality_by_band']
    hour, age = table['hour'], table['session_age']
    assert list(hour) == ['morning', 'midday', 'afternoon', 'evening']
    assert list(age) == ['0-49 turns', '50-199 turns', '200+ turns', 'compacted', 'no planner']
    assert (hour['morning']['gates'], hour['morning']['fix_rate']) == (1, 0.0)
    assert hour['midday']['fix_rate'] == 1.0
    assert {key: hour['evening'][key] for key in ('gates', 'fix_rounds', 'lint_rejections')} == {
        'gates': 2, 'fix_rounds': 1, 'lint_rejections': 1}
    assert age['0-49 turns']['gates'] == 2
    assert (age['50-199 turns']['gates'], age['50-199 turns']['fix_rounds']) == (1, 1)
    assert age['compacted']['gates'] == 1
    assert hour['afternoon']['fix_rate'] == 'unmeasured'
    assert all(cell['interventions'] == 'unmeasured' for cells in table.values() for cell in cells.values())
    gate = {'kind': 'gate.received', 'ts': '2026-09-29T10:30:00+00:00', 'payload': {'verdict': 'PASS'}}
    assert metrics._bands([('2026-09-29', [gate])], [], ZoneInfo('Europe/Amsterdam'))['hour']['midday']['gates'] == 1
    assert metrics._bands([('2026-09-29', [gate])], [], ZoneInfo('UTC'))['hour']['morning']['gates'] == 1


def test_band_interventions_from_transcripts(root, monkeypatch):
    from wuwei import metrics
    (root / 'transcripts').mkdir()
    rows = [{'type': 'user', 'timestamp': at, 'cwd': str(root),
             'message': {'role': 'user', 'content': 'owner text'}}
            for at in ('2026-09-29T09:00:00Z', '2026-09-29T19:00:00Z')]
    (root / 'transcripts/a.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    state.append_event('state.write', {}, root)
    (root / '.wuwei/config.toml').write_text('[owner]\ntimezone = "UTC"\n[metrics]\ntranscripts = "transcripts"\n')
    calls = []
    real = metrics._human_times
    monkeypatch.setattr(metrics, '_human_times', lambda *args: calls.append(1) or real(*args))
    value = metrics.collect(root)
    assert calls == [1]
    hour = value['quality_by_band']['hour']
    assert [hour[band]['interventions'] for band in hour] == [1, 0, 0, 1]
    assert value['quality_by_band']['session_age']['no planner']['interventions'] == 2
    assert value['owner_intervention'] == metrics._owner_intervention(real(root, workspace.load_config(root)),
                                                                      workspace.now())


def cells(**rates):
    from wuwei import metrics
    table = {}
    for band, (gates, fixes) in rates.items():
        table[band] = {'gates': gates, 'fix_verdicts': fixes, 'fix_rounds': 0, 'lint_rejections': 0,
                       'interventions': metrics.UNMEASURED,
                       'fix_rate': fixes / gates if gates else metrics.UNMEASURED}
    return table


@pytest.mark.parametrize('rates,found', [
    ({'evening': (5, 3), 'morning': (5, 1)}, ('evening', 0.6, 0.2)),
    ({'evening': (10, 3), 'morning': (5, 1)}, None),
    ({'evening': (5, 3), 'morning': (0, 0)}, None),
    ({'evening': (5, 3), 'morning': (5, 1), 'midday': (0, 0)}, ('evening', 0.6, 0.2)),
])
def test_worst_band_margin(rates, found):
    from wuwei import metrics
    assert metrics.worst(cells(**rates), 0.2) == found


def test_band_lines():
    from wuwei import metrics
    lines = metrics.band_lines('Hour', cells(morning=(2, 1), evening=(0, 0)))
    assert lines[0] == '| Hour | Gates | FIX rate | Fix rounds | Lint rejections | Interventions |'
    assert lines[1].startswith('| --- |')
    assert lines[2:] == ['| morning | 2 | 0.50 | 0 | 0 | unmeasured |',
                         '| evening | 0 | unmeasured | 0 | 0 | unmeasured |']
    assert metrics.band_lines('Hour', 'unmeasured') == ['Hour: unmeasured']
