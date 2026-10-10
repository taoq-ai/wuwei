"""#283: cruise mode (design 5.8.1): levels, the cruise answer, undo, promotion and demotion."""

import json
import os

import pytest

from test_decision import SUPERVISED, save, events
from wuwei.workspace import owner_cli
from test_decision_classes import BELOW, LEAD, record, route, ws  # noqa: F401 (ws is a fixture)


def config(root, text):
    (root / '.wuwei/config.toml').write_text(text)


def ledger(root):
    path = root / '.wuwei/memory/ledger.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def later(monkeypatch, stamp):
    monkeypatch.setenv('WUWEI_NOW', f'2026-09-28T{stamp}:00+00:00')


def raise_to(root, name, level):
    from wuwei import promotion
    promotion.cruise_level(root, name, level, 'test setup', '.wuwei/config.toml')


# Phase 1: config and the running level


def test_cruise_config_defaults_and_ranges(ws):
    from wuwei import workspace
    cruise = workspace.load_config(ws)['decisions']['cruise']
    assert (cruise['margin'], cruise['max_per_day'], cruise['undo_minutes'],
            cruise['promote_agreements'], cruise['promote_days']) == (0.2, 20, 60, 10, 14)
    config(ws, '[decisions.cruise]\nmargin = 0.3\nmax_per_day = 5\nundo_minutes = 30\n'
               'promote_agreements = 8\npromote_days = 10\n')
    cruise = workspace.load_config(ws)['decisions']['cruise']
    assert (cruise['margin'], cruise['max_per_day'], cruise['undo_minutes'],
            cruise['promote_agreements'], cruise['promote_days']) == (0.3, 5, 30, 8, 10)
    for value in ('0', '1.5', '-0.1'):
        config(ws, f'[decisions.cruise]\nmargin = {value}\n')
        with pytest.raises(workspace.ConfigError, match='decisions.cruise.margin'):
            workspace.load_config(ws)
    assert (cruise['shadow_days'], cruise['shadow_min']) == (5, 5)  # #560
    for key in ('shadow_days', 'shadow_min'):
        config(ws, f'[decisions.cruise]\n{key} = 0\n')
        with pytest.raises(workspace.ConfigError, match=f'decisions.cruise.{key}'):
            workspace.load_config(ws)


def test_config_check_and_lint_refuse_a_level_above_its_ceiling(ws, capsys):
    from wuwei.__main__ import main
    config(ws, '[decisions.cruise.levels]\nmessage = 2\n')
    assert main(['config', 'check']) == 1
    out = capsys.readouterr()
    assert 'decisions.cruise.levels.message' in out.out + out.err and 'above its ceiling L1' in out.out + out.err
    config(ws, '')
    path = save(ws, record(cls='autopilot'))
    assert main(['decision', 'lint', str(path)]) == 1
    assert 'Class: expected one of' in capsys.readouterr().err


def test_running_levels_fail_closed(ws):
    from wuwei import decision
    assert decision.running(ws) == {'levels': {}, 'changed': {}}
    path = ws / '.wuwei/memory/cruise.json'
    path.parent.mkdir(parents=True)
    for text in ('not json', '[]', '{"levels": {"autopilot": 1}, "changed": {}}',
                 '{"levels": {"defer": "2"}, "changed": {}}', '{"levels": {"defer": 4}, "changed": {}}'):
        path.write_text(text)
        with pytest.raises(ValueError, match='bin/wuwei doctor'):
            decision.running(ws)
    path.unlink()
    (ws / 'elsewhere.json').write_text('{"levels": {}, "changed": {}}')
    os.symlink(ws / 'elsewhere.json', path)
    with pytest.raises(ValueError):
        decision.running(ws)


@pytest.mark.parametrize('text,running,expected', [
    ('', None, 0),
    ('', {'levels': {'defer': 2}}, 2),
    ('', {'levels': {'defer': 5}}, 3),
    ('[decisions.cruise.levels]\ndefer = 1\n', {'levels': {'defer': 3}}, 1),
    ('[decisions.cruise]\nenabled = false\n', {'levels': {'defer': 2}}, 0),
    (SUPERVISED, {'levels': {'defer': 2}}, 0),
])
def test_level_reads_the_running_level(ws, text, running, expected):
    from wuwei import decision, workspace
    config(ws, text)
    assert decision.level(workspace.load_config(ws), 'defer', running) == expected


def test_level_defaults_and_supervised(ws):
    from wuwei import decision, workspace
    assert decision.level(workspace.load_config(ws), 'retry') == 2
    config(ws, SUPERVISED)
    assert decision.level(workspace.load_config(ws), 'retry') == 0


def test_the_level_writer_records_a_ledger_line(ws):
    from wuwei import decision, promotion
    promotion.cruise_level(ws, 'defer', 2, 'raise approved D-9', '.wuwei/days/2026-09-28/decisions/D-9.md')
    running = decision.running(ws)
    assert running['levels'] == {'defer': 2} and running['changed']['defer'].startswith('2026-09-28T12:00')
    line = ledger(ws)[-1]
    assert (line['target'], line['action'], line['status'], line['reason'], line['evidence']) == (
        '.wuwei/memory/cruise.json', 'raise', 'landed', 'raise approved D-9',
        '.wuwei/days/2026-09-28/decisions/D-9.md')
    promotion.cruise_level(ws, 'defer', 1, 'undo D-3', 'x')
    assert ledger(ws)[-1]['action'] == 'lower' and decision.running(ws)['levels']['defer'] == 1
    for name, level in (('autopilot', 1), ('message', 2), ('defer', -1)):
        with pytest.raises(ValueError):
            promotion.cruise_level(ws, name, level, 'r', 'x')


def test_the_level_writer_keeps_a_budget_hold(ws):
    # #558: a budget lowering holds the level it took away; any other write clears the hold.
    from wuwei import decision, promotion
    promotion.cruise_level(ws, 'defer', 1, 'budget spent: defer', 'x', hold=2)
    assert decision.running(ws)['budget'] == {'defer': 2}
    promotion.cruise_level(ws, 'defer', 2, 'budget refilled: defer back to L2', 'x')
    assert set(json.loads((ws / '.wuwei/memory/cruise.json').read_text())) == {'levels', 'changed'}
    path = ws / '.wuwei/memory/cruise.json'
    for budget in ('{"autopilot": 1}', '{"defer": 4}', '{"defer": "2"}', '[]'):
        path.write_text('{"levels": {}, "changed": {}, "budget": %s}' % budget)
        with pytest.raises(ValueError, match='bin/wuwei doctor'):
            decision.running(ws)


def test_promote_rejects_a_proposal_for_the_cruise_levels(ws):
    from wuwei import promotion
    proposal = {'target': '.wuwei/memory/cruise.json', 'action': 'patch', 'reason': 'raise',
                'evidence': '.wuwei/config.toml', 'old_text': '{}', 'text': '{"levels": {"defer": 3}}'}
    record = promotion.land(ws, proposal, day='2026-09-28', run='r',
                            ledger=ws / '.wuwei/memory/ledger.jsonl', name='p.json')
    assert record['status'] == 'rejected'
    assert not (ws / '.wuwei/memory/cruise.json').exists()


# Phase 2: the cruise answer


def outcome(root, ident='D-3'):
    from wuwei import state
    return state.read_state(root).get('decision_outcomes', {}).get(ident)


def test_a_wide_margin_record_at_l2_is_a_cruise_answer(ws, capsys):
    from wuwei import state
    raise_to(ws, 'defer', 2)
    path = save(ws, record(cls='defer', radius='workspace'))
    assert route(ws, capsys) == (0, 'mandate')
    text = path.read_text()
    assert 'Decided-by: cruise defer@L2' in text and 'Outcome: A' in text
    row = outcome(ws)
    assert (row['decided_by'], row['rule'], row['class'], row['level'], row['items']) == (
        'mandate', 'cruise defer@L2', 'defer', 2, [])
    assert row['at'].startswith('2026-09-28T12:00') and row['undo_until'].startswith('2026-09-28T13:00')
    decided = [e['payload'] for e in events(ws) if e['kind'] == 'decision.decided']
    assert len(decided) == 1 and decided[0]['decided_by'] == 'cruise defer@L2'
    assert decided[0]['undo_until'] == row['undo_until'] and decided[0]['class'] == 'defer'
    assert not state.read_state(ws).get('decision_routes')
    before = len(events(ws))
    assert route(ws, capsys) == (0, 'mandate') and len(events(ws)) == before


def test_l3_has_no_undo_window_and_default_routine_classes_cruise(ws, capsys):
    raise_to(ws, 'defer', 3)
    save(ws, record(cls='defer', radius='workspace'))
    assert route(ws, capsys) == (0, 'mandate')
    assert outcome(ws)['rule'] == 'cruise defer@L3' and 'undo_until' not in outcome(ws)
    save(ws, record(cls='retry'), name='D-4.md')
    assert route(ws, capsys, 'D-4') == (0, 'mandate')
    assert outcome(ws, 'D-4')['rule'] == 'cruise retry@L2'


@pytest.mark.parametrize('setup,kwargs', [
    ('', dict(cls='defer', radius='workspace')),  # defer runs at its default L0
    ('', dict(cls='retry', radius='item DIV-1')),
    ('', dict(cls='retry', wants=BELOW)),
    ('[decisions.cruise]\nmax_per_day = 0\n', dict(cls='retry')),
    ('[decisions.cruise]\nenabled = false\n', dict(cls='retry')),
    ('[decisions.cruise.levels]\nretry = 1\n', dict(cls='retry')),
])
def test_a_failing_condition_keeps_the_mandate_answer(ws, capsys, setup, kwargs):
    config(ws, setup)
    path = save(ws, record(**kwargs))
    assert route(ws, capsys) == (0, 'mandate')
    assert 'rule' not in outcome(ws) and 'Decided-by: mandate' in path.read_text()


def test_merge_no_class_and_unplanned_items_never_cruise(ws, capsys):
    from wuwei import state
    # #557: a merge naming no repository and a record without a class have no measured undo.
    save(ws, record(cls='merge'))
    assert route(ws, capsys)[1].startswith('owner\n') and outcome(ws) is None
    save(ws, record(cls='retry').replace('Class: retry\n', ''), name='D-4.md')
    assert route(ws, capsys, 'D-4')[1].startswith('owner\n') and outcome(ws, 'D-4') is None
    state._write_state(lambda data: data.update(items={'DIV-1': {'goal': 'unplanned'}}), ws, reserved=False)
    save(ws, record(cls='retry').replace('Question: Which fix?', 'Question: Which fix for DIV-1?'), name='D-5.md')
    assert route(ws, capsys, 'D-5') == (0, 'mandate') and 'rule' not in outcome(ws, 'D-5')


def test_the_daily_budget_counts_cruise_answers(ws, capsys):
    config(ws, '[decisions.cruise]\nmax_per_day = 1\n')
    save(ws, record(cls='retry'))
    save(ws, record(cls='retry'), name='D-4.md')
    route(ws, capsys)
    route(ws, capsys, 'D-4')
    assert outcome(ws)['rule'] == 'cruise retry@L2' and 'rule' not in outcome(ws, 'D-4')


@pytest.mark.parametrize('value,code', [('cruise defer@L2', 0), ('cruise merge@L3', 0),
                                        ('cruise defer@L1', 1), ('cruise unknown@L2', 1), ('cruise', 1)])
def test_lint_accepts_a_cruise_rule(value, code):
    from wuwei import decision
    assert decision.lint(record().replace('Decided-by: seat', 'Decided-by: ' + value))[0] == code


def test_a_thin_margin_goes_to_the_owner(ws, capsys):
    from wuwei import state
    raise_to(ws, 'defer', 2)
    save(ws, record(cls='defer', radius='workspace', wants=LEAD))
    assert route(ws, capsys) == (0, 'owner')
    row = state.read_state(ws)['decision_routes']['D-3']
    assert row['class'] == 'defer' and row['thin'] is True and row['at'].startswith('2026-09-28T12:00')
    routed = next(e['payload'] for e in events(ws) if e['kind'] == 'decision.routed')
    assert routed['class'] == 'defer' and routed['thin'] is True
    assert outcome(ws) is None
    path = save(ws, record(cls='approach', wants=LEAD), name='D-4.md')
    assert route(ws, capsys, 'D-4') == (0, 'mandate')
    assert 'Decided-by: mandate' in path.read_text() and 'rule' not in outcome(ws, 'D-4')


def test_thin_escalations_keep_the_level(ws, capsys, monkeypatch):
    # #558: thin routes are flagged; only the error budget lowers a class.
    from wuwei import decision, state, workspace
    later(monkeypatch, '11:00')
    raise_to(ws, 'defer', 2)
    later(monkeypatch, '12:00')
    for number in (3, 4):
        save(ws, record(cls='defer', radius='workspace', wants=LEAD), name=f'D-{number}.md')
        route(ws, capsys, f'D-{number}')
    save(ws, record(cls='defer', radius='workspace'), name='D-5.md')  # a cruise answer resets
    route(ws, capsys, 'D-5')
    assert outcome(ws, 'D-5')['rule'] == 'cruise defer@L2'
    for number in (6, 7):
        save(ws, record(cls='defer', radius='workspace', wants=LEAD), name=f'D-{number}.md')
        route(ws, capsys, f'D-{number}')
    save(ws, record(cls='defer', radius='workspace', wants=LEAD), name='D-8.md')
    route(ws, capsys, 'D-8')
    assert state.read_state(ws)['decision_routes']['D-8']['thin'] is True
    assert decision.level(workspace.load_config(ws), 'defer', decision.running(ws)) == 2
    assert ledger(ws)[-1]['reason'] == 'test setup'


def test_closing_collects_a_cruise_park_disposition(ws, capsys):
    from wuwei import closing, state
    save(ws, record(cls='park').replace('Outcome: pending', 'Outcome: parked DIV-1'))
    assert route(ws, capsys) == (0, 'mandate')
    assert outcome(ws)['rule'] == 'cruise park@L2'
    state._write_state(lambda data: data.update(
        items={'DIV-1': {'goal': 'g', 'status': 'queued', 'phase': 'planned'}}, approved_items=['DIV-1']),
        ws, reserved=False)
    _, findings = closing.unresolved(ws, [])
    assert 'DIV-1 is still open' not in findings, findings


# Phase 3: notify and undo


@pytest.fixture
def answered(ws, capsys):
    """US1: defer at L2 and D-3 taken as a cruise answer at 12:00, undo until 13:00."""
    raise_to(ws, 'defer', 2)
    path = save(ws, record(cls='defer', radius='workspace'))
    assert route(ws, capsys) == (0, 'mandate')
    return path


def test_nudges_list_an_open_undo_window_first(ws, answered, capsys, monkeypatch):
    from wuwei.__main__ import main
    save(ws, record(door='one-way', confidence='low'), name='D-4.md')
    route(ws, capsys, 'D-4')
    assert main(['nudges', '--all']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == ('nudge: D-3 taken as A by cruise defer@L2, undo until 13:00. '
                        'Run: wuwei decision show D-3 --widget')
    assert any(line.startswith('nudge: D-4 pending') for line in lines[1:])
    later(monkeypatch, '13:00')
    main(['nudges', '--all'])
    assert 'D-3 taken' not in capsys.readouterr().out


def test_the_undo_widget_while_the_window_is_open(ws, answered, capsys, monkeypatch):
    from wuwei.__main__ import main
    assert main(['decision', 'show', 'D-3', '--widget']) == 0
    widget, = json.loads(capsys.readouterr().out)
    assert widget['header'] == 'D-3' and 'D-3' in widget['question'] and '13:00' in widget['question']
    assert [option['label'] for option in widget['options']] == ['Keep (Recommended)', 'Undo']
    assert widget['record'] == 'wuwei decision undo D-3 --answer "<label>"'
    later(monkeypatch, '13:01')
    assert main(['decision', 'show', 'D-3', '--widget']) == 0
    assert json.loads(capsys.readouterr().out) == []


def undo(root, ident='D-3', answer=None, where=None):
    from types import SimpleNamespace
    from wuwei.commands.decision import undo
    return undo(SimpleNamespace(id=ident, answer=answer), root=root, where=where)


def test_undo_reverts_the_answer_and_keeps_the_level(ws, answered, capsys, monkeypatch):
    from wuwei import decision, state, workspace
    from wuwei.commands.decision import owner_outcome
    from types import SimpleNamespace
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert undo(ws) == (0, 'owner: ask with wuwei decision show D-3 --widget')
    data = state.read_state(ws)
    assert 'D-3' not in data['decision_outcomes'] and data['decision_routes']['D-3']['undone'] is True
    text = answered.read_text()
    assert 'Decided-by: owner' in text and 'Outcome: pending' in text and 'Notes: Undone at ' in text
    reversed_, = [e['payload'] for e in events(ws) if e['kind'] == 'decision.reversed']
    assert reversed_['undo'] is True and reversed_['rule'] == 'cruise defer@L2' and reversed_['class'] == 'defer'
    # #558: the undo spends the error budget instead of lowering the class at once.
    assert decision.level(workspace.load_config(ws), 'defer', decision.running(ws)) == 2
    assert ledger(ws)[-1]['reason'] == 'test setup'
    assert owner_outcome(SimpleNamespace(id='D-3', option='B'), root=ws) == (0, 'B')


def test_keep_closed_window_no_window_and_declined(ws, answered, capsys, monkeypatch):
    from wuwei import state
    before = state.read_state(ws)
    assert undo(ws, answer='Keep (Recommended)') == (0, 'kept')
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: False)
    code, message = undo(ws)
    assert code == 1 and 'declined' in message
    later(monkeypatch, '13:00')
    assert undo(ws) == (1, f'undo window closed at 13:00; run {owner_cli(ws)} decide D-3 <option> to reverse it')
    save(ws, record(cls='retry', radius='item DIV-1'), name='D-4.md')
    route(ws, capsys, 'D-4')
    assert undo(ws, 'D-4') == (1, f'D-4 has no undo window; run {owner_cli(ws)} decide D-4 <option> to reverse it')
    assert state.read_state(ws)['decision_outcomes']['D-3'] == before['decision_outcomes']['D-3']


def test_the_undo_card_answer_confirms(ws, answered, monkeypatch):
    from wuwei import sessions
    monkeypatch.setattr(sessions, 'gate_topics',
                        lambda root, session: (frozenset({sessions.card_topic('D-3', 'Keep')}), True))
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: False)
    assert undo(ws, answer='Undo')[0] == 1
    monkeypatch.setattr(sessions, 'gate_topics',
                        lambda root, session: (frozenset({sessions.card_topic('D-3', 'Undo')}), True))
    assert undo(ws, answer='Undo')[0] == 0


def test_the_digest_lists_cruise_answers_first(ws, capsys, monkeypatch):
    from wuwei import registry, watch, workspace
    from wuwei.registry import Result
    sent = []

    class Chat:
        def dm(self, text, *, root=None):
            sent.append(text)
            return Result(0, {})

    monkeypatch.setattr(registry, 'load', lambda kind, config: Chat())
    raise_to(ws, 'defer', 2)
    save(ws, record(cls='design'), name='D-1.md')
    save(ws, record(cls='defer', radius='workspace'), name='D-2.md')
    route(ws, capsys, 'D-1')
    route(ws, capsys, 'D-2')
    assert watch.digest(ws, workspace.load_config(ws)) == 0
    assert sent == ['Two-way decisions taken:\n- D-2: A (cruise defer@L2)\n- D-1: A\n']


def test_the_owner_reversing_a_cruise_answer_keeps_the_level(ws, answered, monkeypatch):
    from types import SimpleNamespace
    from wuwei import decision, state, workspace
    from wuwei.commands.decision import owner_outcome
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert owner_outcome(SimpleNamespace(id='D-3', option='B'), root=ws) == (0, 'B')
    row = state.read_state(ws)['decision_outcomes']['D-3']
    assert (row['class'], row['recommendation']) == ('defer', 'A')
    assert [e['payload']['class'] for e in events(ws) if e['kind'] == 'decision.reversed'] == ['defer']
    assert decision.running(ws)['levels']['defer'] == 2 and ledger(ws)[-1]['reason'] == 'test setup'


def test_the_owner_confirming_a_cruise_answer_keeps_the_level(ws, answered, monkeypatch):
    from types import SimpleNamespace
    from wuwei import decision
    from wuwei.commands.decision import owner_outcome
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert owner_outcome(SimpleNamespace(id='D-3', option='A'), root=ws) == (0, 'A')
    assert decision.running(ws)['levels']['defer'] == 2


# Phase 4: promotion, the weekly sample and escaped defects


def agree(root, count, cls='defer', start=100, **extra):
    """count owner answers equal to the recommendation in today's state."""
    from wuwei import state, workspace
    rows = {f'D-{start + index}': {'option': 'A', 'outcome': 'A', 'decided_by': 'owner',
                                   'reversibility': 'two-way', 'cisr': 'Consequential', 'class': cls,
                                   'recommendation': 'A', 'at': workspace.now().isoformat(), **extra}
            for index in range(count)}
    state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update(rows), root, reserved=False)


def calibrated(root, cls='defer', start=300):
    """#559: ten taken high-confidence records of cls that stood, so promotion may raise it."""
    from wuwei import state
    for number in range(start, start + 10):
        state.append_event('decision.decided', {'id': f'D-{number}', 'option': 'A', 'class': cls,
                                                'decided_by': 'mandate', 'confidence': 'high'}, root)


def cards(root):
    from wuwei import state
    return state.read_state(root).get('cruise_cards', {})


def propose(root):
    from wuwei import cruise, workspace
    return cruise.propose(root, workspace.load_config(root))


def test_ten_agreements_propose_a_raise(ws, monkeypatch):
    from wuwei import cruise, decision, state, workspace
    monkeypatch.setenv('WUWEI_NOW', '2026-09-27T12:00:00+00:00')
    agree(ws, 4)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    agree(ws, 6)
    assert propose(ws) == []  # #559: too few scored records
    calibrated(ws)
    raise_to(ws, 'defer', 1)  # #560: a raise to L2 changes routes, so it starts a shadow first
    later(monkeypatch, '12:01')
    agree(ws, 10, start=120)
    lines = len(ledger(ws))
    assert propose(ws) == [] and cards(ws) == {}
    assert decision.running(ws)['shadow']['defer'] == {
        'level': 2, 'started': '2026-09-28T12:01:00+00:00', 'scored': 0, 'agreed': 0, 'state': 'running'}
    assert len(ledger(ws)) == lines + 1 and ledger(ws)[-1]['reason'] == 'shadow started: defer at L2'
    assert propose(ws) == [] and len(ledger(ws)) == lines + 1
    raise_to(ws, 'defer', 0)
    later(monkeypatch, '12:02')
    agree(ws, 10, start=140)
    assert propose(ws) == ['D-1']  # L1 changes no route: its shadow passes at once
    card = cards(ws)['D-1']
    assert (card['kind'], card['class'], card['level']) == ('raise', 'defer', 1)
    assert 'D-1' in state.read_state(ws)['decision_routes']
    text = (workspace.day_dir(ws) / 'decisions/D-1.md').read_text()
    assert 'Decided-by: owner' in text and '| raise | Raise defer to L1 |' in text and '| keep | Keep defer at L0 |' in text
    assert any(e['kind'] == 'cruise.carded' for e in events(ws))
    widget, = cruise.gate_widgets(ws, workspace.load_config(ws))
    assert widget['header'] == 'D-1' and widget['options'][0]['label'] == 'Raise defer to L1 (Recommended)'
    assert propose(ws) == []  # one raise card per class per window
    assert decision.running(ws)['levels'] == {'defer': 0}


@pytest.mark.parametrize('setup', ['nine', 'changed', 'supervised', 'off', 'capped'])
def test_no_raise_card(ws, setup, monkeypatch):
    agree(ws, 9 if setup == 'nine' else 10)
    if setup == 'changed':
        later(monkeypatch, '12:01')
        raise_to(ws, 'defer', 0)
    config(ws, {'supervised': SUPERVISED, 'off': '[decisions.cruise]\nenabled = false\n',
                'capped': '[decisions.cruise.levels]\ndefer = 0\n'}.get(setup, ''))
    assert propose(ws) == [] and cards(ws) == {}


def answer(root, ident, option, monkeypatch):
    from types import SimpleNamespace
    from wuwei.commands.decision import owner_outcome
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    return owner_outcome(SimpleNamespace(id=ident, option=option), root=root)


def test_the_owner_raise_lands_and_keep_does_not(ws, monkeypatch):
    from wuwei import decision, workspace
    agree(ws, 10)
    calibrated(ws)
    propose(ws)
    assert answer(ws, 'D-1', 'raise', monkeypatch) == (0, 'raise')
    assert decision.level(workspace.load_config(ws), 'defer', decision.running(ws)) == 1
    line = ledger(ws)[-1]
    assert (line['action'], line['reason'], line['evidence']) == (
        'raise', 'raise approved D-1; shadow agreed 0 of 0', '.wuwei/days/2026-09-28/decisions/D-1.md')
    assert 'shadow' not in decision.running(ws)
    agree(ws, 10, cls='scope-cut', start=200)
    calibrated(ws, 'scope-cut', start=400)
    propose(ws)
    assert answer(ws, 'D-2', 'keep', monkeypatch) == (0, 'keep')
    assert 'scope-cut' not in decision.running(ws)['levels']


def test_a_raise_never_passes_the_configured_level(ws, monkeypatch):
    from wuwei import decision
    agree(ws, 10)
    calibrated(ws)
    propose(ws)
    config(ws, '[decisions.cruise.levels]\ndefer = 0\n')
    answer(ws, 'D-1', 'raise', monkeypatch)
    assert decision.running(ws)['levels'] == {}


def test_weekly_sample_card(ws, capsys, monkeypatch):
    from wuwei import budget_classes, cruise, decision, workspace
    answered_ = save(ws, record(cls='retry'))
    assert route(ws, capsys) == (0, 'mandate')
    assert propose(ws) == ['D-4']
    card = cards(ws)['D-4']
    assert (card['kind'], card['class'], card['option'], card['source']) == (
        'sample', 'retry', 'A', '.wuwei/days/2026-09-28/decisions/D-3.md')
    text = (workspace.day_dir(ws) / 'decisions/D-4.md').read_text()
    assert 'Decided-by: owner' in text and 'Outcome: pending' in text and 'Question: Which fix?' in text
    assert 'Decided-by: cruise' in answered_.read_text()
    widget, = cruise.gate_widgets(ws, workspace.load_config(ws))
    assert [option['label'] for option in widget['options']] == ['Implement fix', 'Defer until tomorrow']
    assert 'Correctness decided it' not in widget['question']
    assert propose(ws) == []
    assert answer(ws, 'D-4', 'B', monkeypatch) == (0, 'B')
    # #558: a different sample answer spends the error budget; the level stays.
    assert decision.level(workspace.load_config(ws), 'retry', decision.running(ws)) == 2
    assert [row['label'] for row in budget_classes.select(ws, 14)[1]] == [
        'sample 2026-09-28 D-4 of 2026-09-28 D-3']


def test_a_sample_answered_the_same_keeps_the_level(ws, capsys, monkeypatch):
    from wuwei import decision
    save(ws, record(cls='retry'))
    route(ws, capsys)
    propose(ws)
    assert answer(ws, 'D-4', 'A', monkeypatch) == (0, 'A')
    assert decision.running(ws)['levels'] == {}


def test_an_escaped_defect_spends_the_budget(ws, capsys, monkeypatch):
    from wuwei import budget_classes, cruise, decision, state, workspace
    state._write_state(lambda data: data.update(items={'DIV-1': {
        'goal': 'G-1', 'status': 'queued', 'phase': 'planned'}}), ws, reserved=False)
    save(ws, record(cls='retry').replace('Question: Which fix?', 'Question: Which fix for DIV-1?'))
    assert route(ws, capsys) == (0, 'mandate')
    assert outcome(ws)['items'] == ['DIV-1']
    monkeypatch.setattr('wuwei.metrics._escaped', lambda root: ({'DIV-1': 'standard'}, {'DIV-1'}))
    assert [row['label'] for row in budget_classes.select(ws, 14)[1]] == ['escaped DIV-1 2026-09-28 D-3']
    budget_classes.evaluate(ws)  # one event against one answer: under two events, not spent
    assert decision.level(workspace.load_config(ws), 'retry', decision.running(ws)) == 2
    assert not any(hasattr(cruise, name) for name in ('lower', 'streak', 'escaped'))


# Phase 5: the status line, supervised and the steward


def status_line(root):
    from wuwei import workspace
    from wuwei.commands import status
    return status.full(status.snapshot(workspace.day_dir(root)))


def test_status_names_the_cruise_level(ws, capsys):
    from wuwei import state
    state._write_state(lambda data: None, ws, reserved=False)
    assert '\ncruise L2\nplugin ' in status_line(ws)
    config(ws, '[decisions.cruise]\nenabled = false\n')
    assert '\ncruise off, L2\nplugin ' in status_line(ws)
    config(ws, '')
    raise_to(ws, 'defer', 3)
    assert '\ncruise L3\nplugin ' in status_line(ws)
    config(ws, SUPERVISED)
    assert '\ncruise L0\nplugin ' in status_line(ws)
    (ws / '.wuwei/memory/cruise.json').write_text('not json')
    from wuwei.__main__ import main
    assert main(['status']) == 2  # --line skips cruise.json since #562
    assert capsys.readouterr().out.strip() == 'WUWEI ? unmeasured'


def test_supervised_routes_as_before_and_the_mandate_sends_every_class_to_the_owner(ws, capsys):
    from wuwei import brief, state
    config(ws, SUPERVISED)
    raise_to(ws, 'defer', 2)
    save(ws, record(cls='defer', radius='workspace'))
    assert route(ws, capsys) == (0, 'owner')
    assert not state.read_state(ws).get('decision_outcomes')
    text = brief.mandate(ws)
    assert 'Decide and record: none.' in text and 'decision records of class approach, retry' in text


# #560: shadow before live promotion


def shadow_at(root, name='approach', level=3, started='2026-09-28T12:00:00+00:00', state='running', **extra):
    from wuwei import promotion
    row = {'level': level, 'started': started, 'scored': 0, 'agreed': 0, 'state': state, **extra}
    promotion.cruise_shadow(root, name, row, f'shadow started: {name} at L{level}')
    return row


def test_the_shadow_row_has_one_writer_and_fails_closed(ws):
    from wuwei import decision
    row = shadow_at(ws)
    assert decision.running(ws)['shadow'] == {'approach': row}
    line = ledger(ws)[-1]
    assert (line['action'], line['reason'], line['target']) == (
        'shadow', 'shadow started: approach at L3', '.wuwei/memory/cruise.json')
    raise_to(ws, 'approach', 3)
    assert 'shadow' not in decision.running(ws)
    path = ws / '.wuwei/memory/cruise.json'
    good = dict(row)
    for bad in ({'autopilot': good}, {'approach': {**good, 'level': 0}}, {'approach': {**good, 'level': 4}},
                {'approach': {**good, 'scored': -1}}, {'approach': {**good, 'state': 'odd'}},
                {'approach': {**good, 'started': 5}}, []):
        path.write_text(json.dumps({'levels': {}, 'changed': {}, 'shadow': bad}))
        with pytest.raises(ValueError, match='bin/wuwei doctor'):
            decision.running(ws)


def shadows(root):
    from wuwei import state
    return state.read_state(root).get('decision_shadows', {})


def test_a_shadow_never_changes_the_live_route(ws, capsys):
    from wuwei import state
    from wuwei.__main__ import main
    shadow_at(ws)
    first = save(ws, record(cls='approach'))
    assert route(ws, capsys) == (0, 'mandate')
    assert shadows(ws) == {'D-3': {'class': 'approach', 'level': 3, 'option': 'A',
                                   'at': '2026-09-28T12:00:00+00:00'}}
    shadowed, = [e['payload'] for e in events(ws) if e['kind'] == 'decision.shadow']
    assert shadowed.items() >= {'id': 'D-3', 'class': 'approach', 'level': 3, 'option': 'A',
                                'at': '2026-09-28T12:00:00+00:00'}.items()
    path = ws / '.wuwei/memory/cruise.json'
    path.write_text(json.dumps({key: value for key, value in json.loads(path.read_text()).items() if key != 'shadow'}))
    second = save(ws, record(cls='approach'), name='D-4.md')
    assert route(ws, capsys, 'D-4') == (0, 'mandate')
    assert outcome(ws, 'D-3') == outcome(ws, 'D-4') and outcome(ws, 'D-3')['rule'] == 'cruise approach@L2'
    decided = [{k: v for k, v in e['payload'].items() if k != 'id'} for e in events(ws) if e['kind'] == 'decision.decided']
    assert decided[0] == decided[1] and first.read_text() == second.read_text()
    assert set(shadows(ws)) == {'D-3'}
    shadow_at(ws)
    save(ws, record(cls='approach', door='one-way'), name='D-5.md')
    route(ws, capsys, 'D-5')
    assert set(shadows(ws)) == {'D-3'}
    before = state.read_state(ws)
    assert main(['event', '--', 'decision.shadow', '{}']) == 1
    assert main(['state', 'set', 'decision_shadows', '{}']) == 1
    assert 'wuwei decision route' in capsys.readouterr().err and state.read_state(ws) == before


def shadowed(root, capsys, count, start=3):
    """count approach records taken at 12:00 on 2026-09-28 while approach runs in shadow at L3."""
    for number in range(start, start + count):
        save(root, record(cls='approach'), name=f'D-{number}.md')
        assert route(root, capsys, f'D-{number}') == (0, 'mandate')


def day(monkeypatch, date):
    monkeypatch.setenv('WUWEI_NOW', f'{date}T12:00:00+00:00')


def test_a_passed_shadow_asks_once_and_the_raise_lands(ws, capsys, monkeypatch):
    from wuwei import cruise, decision
    shadow_at(ws)
    calibrated(ws, 'approach')
    shadowed(ws, capsys, 5)
    day(monkeypatch, '2026-10-03')
    cruise.review_shadows(ws)
    row = decision.running(ws)['shadow']['approach']
    assert (row['state'], row['scored'], row['agreed']) == ('passed', 5, 5)
    assert ledger(ws)[-1]['reason'] == 'shadow passed: approach at L3; agreed 5 of 5'
    raised = [ident for ident in propose(ws) if cards(ws)[ident]['kind'] == 'raise']
    assert len(raised) == 1 and cards(ws)[raised[0]]['shadow'] == row
    assert decision.running(ws)['shadow']['approach']['state'] == 'ended'
    assert ledger(ws)[-1]['reason'] == f'shadow asked {raised[0]}'
    assert not [ident for ident in propose(ws) if cards(ws)[ident]['kind'] == 'raise']
    assert answer(ws, raised[0], 'raise', monkeypatch) == (0, 'raise')
    assert decision.running(ws)['levels']['approach'] == 3 and 'shadow' not in decision.running(ws)
    assert ledger(ws)[-1]['reason'] == f'raise approved {raised[0]}; shadow agreed 5 of 5'


@pytest.mark.parametrize('count,date', [(5, '2026-09-30'), (4, '2026-10-03')])
def test_a_shadow_keeps_running_when_too_soon_or_too_few(ws, capsys, monkeypatch, count, date):
    from wuwei import cruise, decision
    shadow_at(ws)
    shadowed(ws, capsys, count)
    day(monkeypatch, date)
    cruise.review_shadows(ws)
    row = decision.running(ws)['shadow']['approach']
    assert (row['state'], row['scored'], row['agreed']) == ('running', count, count)
    assert ledger(ws)[-1]['reason'] == f'shadow scored: approach at L3; agreed {count} of {count}'
    lines = len(ledger(ws))
    cruise.review_shadows(ws)
    assert len(ledger(ws)) == lines


def test_one_disagreement_ends_the_shadow(ws, capsys, monkeypatch):
    from types import SimpleNamespace
    from wuwei import cruise, decision
    from wuwei.commands.decision import owner_outcome
    shadow_at(ws)
    calibrated(ws, 'approach')
    shadowed(ws, capsys, 5)
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    undo(ws)
    later(monkeypatch, '12:30')
    cruise.review_shadows(ws)  # D-3 undone and not answered, the rest inside their window
    assert decision.running(ws)['shadow']['approach']['scored'] == 0
    assert owner_outcome(SimpleNamespace(id='D-3', option='B'), root=ws) == (0, 'B')
    later(monkeypatch, '13:00')
    cruise.review_shadows(ws)
    row = decision.running(ws)['shadow']['approach']
    assert (row['state'], row['record']) == ('ended', '.wuwei/days/2026-09-28/decisions/D-3.md')
    assert ledger(ws)[-1]['reason'] == ('shadow ended: approach at L3: '
                                        '.wuwei/days/2026-09-28/decisions/D-3.md answered B, shadow A; agreed 4 of 5')
    assert 'approach' not in decision.running(ws)['levels']
    assert not [ident for ident in propose(ws) if cards(ws)[ident]['kind'] == 'raise']
    assert decision.running(ws)['shadow']['approach']['state'] == 'ended'


def test_agreements_count_from_the_last_shadow_end(ws, monkeypatch):
    from wuwei import cruise, decision, workspace
    later(monkeypatch, '11:00')
    agree(ws, 10, cls='scope-cut')
    later(monkeypatch, '12:00')
    shadow_at(ws, 'scope-cut', 1, state='ended', ended='2026-09-28T12:00:00+00:00')
    count = lambda: cruise.agreements(ws, 'scope-cut', workspace.load_config(ws), decision.running(ws))
    assert count() == 0
    later(monkeypatch, '12:01')
    agree(ws, 10, cls='scope-cut', start=200)
    assert count() == 10


def test_a_raise_card_without_a_passed_shadow_lands_nothing(ws, monkeypatch):
    from wuwei import decision, state
    agree(ws, 10)
    calibrated(ws)
    ident, = propose(ws)
    state._write_state(lambda data: data['cruise_cards'][ident].pop('shadow'), ws, reserved=False)
    assert answer(ws, ident, 'raise', monkeypatch) == (0, 'raise')
    assert decision.running(ws)['levels'] == {}


def test_the_owner_sees_the_shadow(ws, capsys):
    from wuwei import commands, cruise, decision, report, state, workspace
    from wuwei.__main__ import main
    assert 'cruise shadow' in commands.READ_ONLY
    state._write_state(lambda data: None, ws, reserved=False)
    assert main(['cruise', 'shadow']) == 0
    assert capsys.readouterr().out.splitlines()[1:] == ['none']
    assert cruise.shadow_lines(ws) == ['none'] and '## Cruise shadow\nnone\n' in report.build(ws)
    shadow_at(ws)
    assert main(['cruise', 'shadow']) == 0
    header, row = capsys.readouterr().out.splitlines()
    assert header.split() == ['class', 'level', 'started', 'scored', 'agreed', 'state']
    assert row.split() == ['approach', 'L3', '2026-09-28', '0', '0', 'running']
    assert cruise.label(workspace.load_config(ws), decision.running(ws)) == 'cruise L2 · shadow approach'
    assert 'cruise L2 · shadow approach' in status_line(ws)
    line, = cruise.shadow_lines(ws)
    assert '## Cruise shadow\n' + line in report.build(ws)
    (ws / '.wuwei/memory/cruise.json').write_text('not json')
    assert main(['cruise', 'shadow']) == 2


def test_the_steward_scores_shadows(ws, monkeypatch):
    from wuwei import cruise, steward
    seen = []
    monkeypatch.setattr(cruise, 'review_shadows', lambda root: seen.append(root))
    steward.review(ws)
    assert seen == [ws]
