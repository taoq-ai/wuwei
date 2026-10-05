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


def test_ai_tells_per_text(root, monkeypatch):
    from test_decision import VALID
    from wuwei import metrics, report, retro
    text = 'This is not just a fix but a rewrite. We delve into it.'

    def row(ident, **extra):
        return {'id': ident, 'channel': 'chat', 'operation': 'post', 'adapter': 'slack',
                'destination': 'C1', 'inputs': {'channel': 'C1', 'text': text}, 'text': text,
                'created': '2026-09-29T12:00:00Z', 'tier_reason': 'external', 'audience': 'work',
                'status': 'pending', **extra}
    state._write_state(lambda data: data.update(drafts={
        'draft-1': row('draft-1', style=['not-x-but-y', 'stock-word']), 'draft-2': row('draft-2')}),
        root, reserved=False)
    decisions = workspace.day_dir(root) / 'decisions'
    decisions.mkdir()
    (decisions / 'D-1.md').write_text(VALID.replace('records the failure.', text))
    (decisions / 'D-2.md').symlink_to(decisions / 'D-1.md')
    assert metrics.collect(root)['ai_tells'] == {'draft-1': 2, 'D-1': 2}
    (decisions / 'D-2.md').unlink()
    evidence = workspace.day_dir(root) / 'retro/role.json'
    evidence.parent.mkdir()
    note = {'agent_id': 'builder-1', 'agent_type': 'builder', 'missing': [], 'invalid': [],
            'fields': {'Blocked': 'none', 'Gap': 'none', 'Change': 'none'}}
    evidence.write_text(json.dumps(note))
    state.append_event('retro.captured', {**note, 'evidence': evidence.relative_to(root).as_posix()}, root)
    retro_text = retro.compile(root).read_text()
    assert json.loads(retro_text.split('## Metrics\n')[1].splitlines()[0])['ai_tells'] == {'draft-1': 2, 'D-1': 2}
    (root / '.wuwei/config.toml').write_text('[owner.verbosity]\nreport = "standard"\n')
    lines = report.build(root).splitlines()
    assert json.loads(lines[lines.index('## Process metrics') + 1])['ai_tells'] == {'draft-1': 2, 'D-1': 2}


def test_ai_tells_counts_sent_outward_text(root):
    from wuwei import metrics
    state.append_event('outward.ai_tells', {'kind': 'tracker', 'tells': ['dash', 'sales'], 'draft': False}, root)
    state.append_event('outward.ai_tells', {'kind': 'review', 'tells': ['dash'], 'draft': True}, root)
    found = metrics.collect(root)['ai_tells']
    assert list(found.values()) == [2] and next(iter(found)).startswith('outward-')


def test_ask_metrics(root):
    from wuwei import metrics

    assert metrics.collect(root)['asks_per_item'] == metrics.UNMEASURED
    assert metrics.collect(root)['unnecessary_asks'] == metrics.UNMEASURED
    directory = workspace.day_dir(root) / 'decisions'
    directory.mkdir(parents=True)
    (directory / 'D-1.md').write_text('Question: Cache alpha results?\n')
    (directory / 'D-2.md').write_text('Question: Which store?\nContext: alpha and beta share it\n')
    (directory / 'D-3.md').write_text('Question: Shift the day?\n')
    routes = {f'D-{n}': {'reversibility': 'one-way', 'recommendation': 'A'} for n in (1, 2, 3)}
    state._write_state(lambda data: data.update(
        items={'alpha': {}, 'beta': {}}, decision_routes=routes, decision_outcomes={
            'D-1': {'option': 'A', 'decided_by': 'owner'},
            'D-2': {'option': 'B', 'decided_by': 'owner'}}), root, reserved=False)
    value = metrics.collect(root)
    assert value['asks_per_item'] == {'alpha': 2, 'beta': 1, 'day': 1}
    assert value['unnecessary_asks'] == 1


def test_metrics_week_prints_computes_and_refuses(root, capsys, monkeypatch):
    # #422: the weekly aggregate on demand; bare metrics is unchanged.
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00+00:00')
    state.append_event('build.parked', {'item': 'A'}, root)
    assert main(['metrics', '--week', '2026-W40']) == 0
    found = json.loads(capsys.readouterr().out)
    assert (found['week'], found['final'], found['metrics']['stuck_parks']) == ('2026-W40', False, 1)
    assert json.loads((root / '.wuwei/metrics/2026-W40.json').read_text()) == found
    (root / '.wuwei/metrics/2026-W40.json').write_text(json.dumps({'week': '2026-W40', 'kept': True}))
    assert main(['metrics', '--week']) == 0
    assert json.loads(capsys.readouterr().out) == {'week': '2026-W40', 'kept': True}
    assert main(['metrics', '--week', 'bad']) == 2
    assert 'invalid week' in capsys.readouterr().err
    assert main(['metrics']) == 0
    assert 'stuck_parks_per_item' in json.loads(capsys.readouterr().out)


def test_seat_cost_from_seat_launched_rows(root):
    from wuwei import metrics
    row = lambda payload: {'kind': 'seat launched', 'payload': payload}
    rows = [row({'name': 'old'}), row({'free_mib': 10240, 'running': 0}),
            row({'free_mib': 7168, 'running': 1}), row({'free_mib': 4096, 'running': 2})]
    assert metrics.seat_cost(rows) == 3072
    assert metrics.seat_cost(rows[:2]) == metrics.UNMEASURED
    assert metrics.seat_cost([rows[0], rows[2]]) == metrics.UNMEASURED
    assert metrics.collect(root)['seat_cost_mib'] == metrics.UNMEASURED
    for payload in rows[1:]:
        state.append_event('seat launched', payload['payload'], root)
    assert metrics.collect(root)['seat_cost_mib'] == 3072


def test_seat_tokens_per_usage_row():
    # #528: the per-seat token cost the budget bounds CAP with.
    from wuwei import metrics
    usage = lambda tokens: {'kind': 'seat.usage', 'payload': {'usage': tokens}}
    rows = [usage({'input_tokens': 2, 'output_tokens': 3}),
            usage({'input_tokens': 'unmeasured', 'output_tokens': 3}),
            {'kind': 'seat launched', 'payload': {'usage': {'input_tokens': 1, 'output_tokens': 1}}},
            usage({'input_tokens': 10, 'output_tokens': 0})]
    assert metrics.seat_tokens(rows) == [5, 10]
