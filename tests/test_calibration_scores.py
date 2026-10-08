"""#559: confidence calibration per class and per role (design 5.8.1): the Brier rule, the
scored records, the stored states, the level cap, the promotion gate, routing, the status line,
the command and the report and retro section."""

import json

import pytest

from test_budget_classes import damage, reverse
from test_cruise import agree, cards, config, ledger, propose, raise_to, status_line
from test_decision import events, save
from test_decision_classes import record, route, ws  # noqa: F401 (ws is a fixture)


def taken(root, count, cls='defer', confidence='high', role=None, start=10, undo_until=None):
    """count records taken under the mandate, written as the CLI writes decision.decided."""
    from wuwei import state
    for number in range(start, start + count):
        payload = {'id': f'D-{number}', 'option': 'A', 'class': cls, 'decided_by': 'mandate',
                   'confidence': confidence, 'role': role}
        if undo_until:
            payload['undo_until'] = undo_until
        state.append_event('decision.decided', payload, root)


def broken(root, cls='defer', role=None):
    """12 high records, 3 reversed and 2 undone."""
    taken(root, 12, cls, role=role)
    for number in (10, 11, 12):
        reverse(root, f'D-{number}', cls)
    for number in (13, 14):
        reverse(root, f'D-{number}', cls, undo=True)


def store(root, classes=(), roles=()):
    from wuwei import promotion
    promotion.calibration(root, list(classes), list(roles), 'test setup')


def rows(root):
    from wuwei import calibration_scores, workspace
    return {(row['kind'], row['name']): row for row in calibration_scores.table(root, workspace.load_config(root))}


# Phase 1: config and record fields


def test_calibration_config_defaults_and_ranges(ws):
    from wuwei import workspace
    cruise = workspace.load_config(ws)['decisions']['cruise']
    assert (cruise['calibration_threshold'], cruise['calibration_min']) == (0.15, 10)
    for value in ('0.0', '1.0', '-0.1'):
        config(ws, f'[decisions.cruise]\ncalibration_threshold = {value}\n')
        with pytest.raises(workspace.ConfigError, match='decisions.cruise.calibration_threshold'):
            workspace.load_config(ws)
    config(ws, '[decisions.cruise]\ncalibration_min = 0\n')
    with pytest.raises(workspace.ConfigError, match='calibration_min'):
        workspace.load_config(ws)


def with_role(role='builder', **kwargs):
    return record(**kwargs).replace('Class: design', f'Class: design\nRole: {role}')


def test_role_field_and_the_payload(ws, capsys):
    from wuwei import decision
    assert decision.lint(with_role())[0] == 0
    code, message = decision.lint(with_role('wizard'))
    assert code == 1 and message.startswith('Role:')
    assert decision.lint(with_role('builder\nreviewer'))[0] == 1
    fields, scores = decision.evaluate(with_role())
    outcome = decision.seat_outcome(fields, scores)
    assert (outcome['confidence'], outcome['role']) == ('high', 'builder')
    save(ws, with_role(radius='outside'))
    assert route(ws, capsys) == (0, 'mandate')
    payload = next(row['payload'] for row in events(ws) if row['kind'] == 'decision.decided')
    assert (payload['confidence'], payload['role']) == ('high', 'builder')


# Phase 2: scoring


CRUISE = {'calibration_threshold': 0.15, 'calibration_min': 10}


@pytest.mark.parametrize('pairs,brier,state', [
    ([(0.9, 1)] * 7 + [(0.9, 0)] * 5, 0.343, 'uncalibrated'),
    ([(0.9, 1)] * 10, 0.01, 'calibrated'),
    ([(0.9, 1)] * 9, 0.01, 'too few'),
    ([(0.6, 1)] * 10, 0.16, 'uncalibrated'),
])
def test_measure(pairs, brier, state):
    from wuwei import calibration_scores
    found, named = calibration_scores.measure(pairs, CRUISE)
    assert round(found, 3) == brier and named == state


def test_measure_nothing_scored():
    from wuwei import calibration_scores
    assert calibration_scores.measure([], CRUISE) == (None, 'too few')


def test_select_every_reads_taken_records(ws):
    from wuwei import budget_classes, state
    taken(ws, 1, role='builder', start=1)
    state.append_event('decision.decided', {'id': 'D-2', 'option': 'A', 'class': 'design',
                                            'decided_by': 'seat', 'confidence': 'low', 'role': None}, ws)
    state.append_event('decision.decided', {'id': 'D-3', 'option': 'A', 'class': 'retry', 'rule': 'cruise retry@L2',
                                            'decided_by': 'cruise retry@L2', 'items': [],
                                            'undo_until': '2026-09-28T13:00:00+00:00'}, ws)
    state.append_event('decision.decided', {'id': 'D-4', 'option': 'A', 'decided_by': 'owner'}, ws)
    reverse(ws, 'D-1')
    assert [row['id'] for row in budget_classes.select(ws, 14)[0]] == ['D-3']
    assert budget_classes.select(ws, 14)[1] == []
    found, counted = budget_classes.select(ws, 14, every=True)
    assert [(row['id'], row['confidence'], row['role'], row['undo_until']) for row in found] == [
        ('D-1', 'high', 'builder', None), ('D-2', 'low', None, None),
        ('D-3', None, None, '2026-09-28T13:00:00+00:00')]
    assert [row['label'] for row in counted] == ['reversal 2026-09-28 D-1']


def test_scored_and_table(ws):
    from wuwei import calibration_scores, workspace
    broken(ws)
    taken(ws, 1, start=30, undo_until='2026-09-28T13:00:00+00:00')  # window open
    taken(ws, 1, confidence=None, start=31)  # no stored confidence
    taken(ws, 10, cls='retry', role='builder', start=40)
    scored = calibration_scores.scored(ws, workspace.load_config(ws))
    assert len(scored) == 22
    row = rows(ws)['class', 'defer']
    assert (row['scored'], row['state'], len(row['broke'])) == (12, 'uncalibrated', 5)
    assert 'undo 2026-09-28 D-13' in row['broke']
    builder = rows(ws)['role', 'builder']
    assert (builder['scored'], builder['state'], round(builder['brier'], 2)) == (10, 'calibrated', 0.01)
    assert rows(ws)['class', 'park']['state'] == 'too few' and ('class', 'merge') not in rows(ws)
    damage(ws)
    with pytest.raises(ValueError):
        calibration_scores.table(ws, workspace.load_config(ws))


# Phase 3: stored states, cap and promotion


def test_the_writer_stores_the_sets(ws):
    from wuwei import calibration_scores, cruise
    store(ws, ['defer'], ['builder'])
    assert cruise.running(ws)['calibration'] == {'classes': ['defer'], 'roles': ['builder']}
    assert ledger(ws)[-1]['action'] == 'calibration'
    raise_to(ws, 'retry', 3)
    assert cruise.running(ws)['calibration'] == {'classes': ['defer'], 'roles': ['builder']}
    store(ws)
    assert 'calibration' not in cruise.running(ws)
    path = ws / '.wuwei/memory/cruise.json'
    for bad in ({'classes': ['wizard'], 'roles': []}, {'classes': 'defer', 'roles': []}, {'classes': [], 'roles': [1]}):
        path.write_text(json.dumps({'levels': {}, 'changed': {}, 'calibration': bad}))
        with pytest.raises(ValueError):
            cruise.running(ws)
    path.unlink()
    broken(ws, role='builder')
    calibration_scores.evaluate(ws)
    assert cruise.running(ws)['calibration'] == {'classes': ['defer'], 'roles': ['builder']}
    count = len(ledger(ws))
    assert 'reversal 2026-09-28 D-10' in ledger(ws)[-1]['reason']
    calibration_scores.evaluate(ws)
    assert len(ledger(ws)) == count


def test_the_steward_review_evaluates_calibration(ws, monkeypatch):
    from wuwei import calibration_scores, steward
    calls = []
    monkeypatch.setattr(calibration_scores, 'evaluate', calls.append)
    steward.review(ws)
    assert calls == [ws]


def level(root, name='defer'):
    from wuwei import cruise, workspace
    return cruise.level(workspace.load_config(root), name, cruise.running(root))


def test_an_uncalibrated_class_runs_at_most_l1(ws):
    raise_to(ws, 'defer', 3)
    store(ws, ['defer'])
    assert level(ws) == 1 and level(ws, 'retry') == 2
    store(ws)
    assert level(ws) == 3


@pytest.mark.parametrize('setup,carded', [(lambda root: None, False), (broken, False),
                                          (lambda root: taken(root, 10, start=40), True)])
def test_promotion_needs_a_calibrated_class(ws, setup, carded):
    setup(ws)
    agree(ws, 10)
    assert bool(propose(ws)) is carded and bool(cards(ws)) is carded


# Phase 4: routing and the status line


def test_an_uncalibrated_role_routes_to_a_card(ws, capsys):
    from wuwei import decision, state
    fields, scores = decision.evaluate(record(cls='retry'))
    assert decision.cisr(fields, scores) == 'Routine'
    assert decision.cisr(fields, scores, ambiguous=True) == 'Exploratory'
    fields, scores = decision.evaluate(record(radius='outside'))
    assert decision.cisr(fields, scores, ambiguous=True) == 'Strategic'
    store(ws, roles=['builder'])
    save(ws, with_role(radius='outside'))
    assert route(ws, capsys) == (0, 'owner')
    row = state.read_state(ws)['decision_routes']['D-3']
    assert (row['cisr'], row['uncalibrated']) == ('Strategic', 'builder')
    assert next(e for e in events(ws) if e['kind'] == 'decision.routed')['payload']['uncalibrated'] == 'builder'
    store(ws)
    save(ws, with_role(radius='outside'), name='D-4.md')
    assert route(ws, capsys, 'D-4') == (0, 'mandate')


def test_the_status_line_names_uncalibrated_roles(ws):
    from wuwei import state
    state._write_state(lambda data: None, ws, reserved=False)
    store(ws, roles=['builder', 'reviewer'])
    assert 'cruise L2 · uncalibrated builder, reviewer' in status_line(ws).splitlines()
    store(ws)
    assert 'uncalibrated' not in status_line(ws)


# Phase 5: command, report and retro


def test_cruise_calibration_prints_the_table(ws, capsys):
    from wuwei import commands
    from wuwei.__main__ import main
    assert commands.read_only(['cruise', 'calibration'])
    assert main(['cruise', 'calibration']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ['kind', 'name', 'scored', 'brier', 'state']
    assert len(lines) == 14
    broken(ws, role='builder')
    assert main(['cruise', 'calibration']) == 1
    out = capsys.readouterr().out.splitlines()
    assert next(line for line in out if line.startswith('role')).split() == [
        'role', 'builder', '12', '0.34', 'uncalibrated']
    damage(ws)
    assert main(['cruise', 'calibration']) == 2
    assert 'wuwei cruise calibration:' in capsys.readouterr().err


def test_report_and_retro_carry_the_section(ws, monkeypatch):
    from wuwei import calibration_scores, report, retro, state, workspace
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    state._write_state(lambda data: None, ws, reserved=False)
    assert calibration_scores.lines(ws, workspace.load_config(ws)) == ['none scored']
    broken(ws, role='builder')
    found = calibration_scores.lines(ws, workspace.load_config(ws))
    line = next(line for line in found if line.startswith('- role builder: uncalibrated'))
    assert 'reversal 2026-09-28 D-10' in line and line.endswith('run bin/wuwei cruise calibration')
    assert '## Calibration\n' + '\n'.join(found) in report.build(ws)
    retro_dir = workspace.day_dir(ws) / 'retro'
    retro_dir.mkdir()
    note = {'agent_id': 'builder-1', 'agent_type': 'builder', 'missing': [], 'invalid': [],
            'fields': {'Blocked': 'none', 'Gap': 'none', 'Change': 'none'}}
    (retro_dir / 'role.json').write_text(json.dumps(note))
    state.append_event('retro.captured', {**note, 'evidence': '.wuwei/days/2026-09-28/retro/role.json'}, ws)
    assert '## Calibration\n' + '\n'.join(found) in retro.compile(ws).read_text()
