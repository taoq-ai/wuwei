"""#558: the error budget per decision class (design 5.8.1): the window reader, the spend rule,
the steward evaluation, the command, the promotion gate and the status line part."""

import json
import math

import pytest

from test_cruise import agree, cards, config, ledger, propose, raise_to, status_line
from test_decision import events
from test_decision_classes import ws  # noqa: F401 (fixture)


def at(monkeypatch, stamp):
    monkeypatch.setenv('WUWEI_NOW', stamp)


def answers(root, cls, count, start=10, items=()):
    """count cruise answers of cls under the current WUWEI_NOW."""
    from wuwei import state
    for number in range(start, start + count):
        state.append_event('decision.decided', {
            'id': f'D-{number}', 'option': 'A', 'class': cls, 'rule': f'cruise {cls}@L2',
            'items': list(items), 'decided_by': f'cruise {cls}@L2'}, root)


def reverse(root, ident, cls='defer', undo=False):
    from wuwei import state
    payload = {'id': ident, 'option': 'B', 'decided_by': 'owner', 'class': cls}
    if undo:
        payload.update(option='A', undo=True, rule=f'cruise {cls}@L2')
    state.append_event('decision.reversed', payload, root)


# Phase 1: config


def test_budget_config_defaults_and_ranges(ws, capsys):
    from wuwei import workspace
    from wuwei.__main__ import main
    cruise = workspace.load_config(ws)['decisions']['cruise']
    assert (cruise['budget_share'], cruise['budget_window_days'], cruise['burn_warn']) == (0.1, 14, 2.0)
    config(ws, '[decisions.cruise]\nbudget_share = 0.3\n')
    assert workspace.load_config(ws)['decisions']['cruise']['budget_share'] == 0.3
    for value in ('0.6', '0.0', '-0.1'):
        config(ws, f'[decisions.cruise]\nbudget_share = {value}\n')
        with pytest.raises(workspace.ConfigError, match='decisions.cruise.budget_share'):
            workspace.load_config(ws)
    config(ws, '[decisions.cruise]\nbudget_window_days = 0\n')
    with pytest.raises(workspace.ConfigError, match='budget_window_days'):
        workspace.load_config(ws)
    config(ws, '[decisions.cruise]\nbudget_share = 0.6\n')
    assert main(['config', 'check']) == 1


# Phase 2: the rule and the reader


CRUISE = {'budget_share': 0.1, 'budget_window_days': 14, 'burn_warn': 2.0}


@pytest.mark.parametrize('answered,spent,recent,allowance,burn,state', [
    (20, 3, 0, 2.0, 0.0, 'spent'),
    (20, 2, 2, 2.0, 7.0, 'warn'),
    (20, 0, 0, 2.0, 0.0, 'ok'),
    (5, 1, 0, 0.5, 0.0, 'ok'),
    (5, 2, 0, 0.5, 0.0, 'spent'),
    (0, 1, 1, 0.0, math.inf, 'warn'),
    (0, 0, 0, 0.0, 0.0, 'ok'),
])
def test_measure(answered, spent, recent, allowance, burn, state):
    from wuwei import budget_classes
    assert budget_classes.measure(answered, spent, recent, CRUISE) == (allowance, burn, state)


def test_select_reads_the_window(ws, monkeypatch):
    from wuwei import budget_classes, state
    at(monkeypatch, '2026-09-10T12:00:00+00:00')
    answers(ws, 'retry', 1, start=1)  # older than the window
    at(monkeypatch, '2026-09-27T12:00:00+00:00')
    answers(ws, 'defer', 2, start=3)
    answers(ws, 'retry', 1, start=5, items=['DIV-1'])
    state.append_event('decision.decided', {'id': 'D-6', 'option': 'A', 'class': 'defer',
                                            'decided_by': 'mandate'}, ws)
    reverse(ws, 'D-3', undo=True)
    reverse(ws, 'D-4')
    reverse(ws, 'D-6')  # a plain mandate answer: not counted
    at(monkeypatch, '2026-09-28T12:00:00+00:00')
    source = '.wuwei/days/2026-09-27/decisions/D-5.md'
    for ident, option in (('D-1', 'B'), ('D-2', 'A')):
        state.append_event('cruise.carded', {'id': ident, 'kind': 'sample', 'class': 'retry',
                                             'option': 'A', 'source': source}, ws)
        state.append_event('decision.decided', {'id': ident, 'option': option, 'decided_by': 'owner',
                                                'class': 'retry'}, ws)
    monkeypatch.setattr('wuwei.metrics._escaped', lambda root: ({'DIV-1': 'standard'}, {'DIV-1'}))
    found, counted = budget_classes.select(ws, 14)
    assert [(row['day'], row['id'], row['class']) for row in found] == [
        ('2026-09-27', 'D-3', 'defer'), ('2026-09-27', 'D-4', 'defer'), ('2026-09-27', 'D-5', 'retry')]
    assert sorted((row['kind'], row['class'], row['day'], row['id'], row['label']) for row in counted) == [
        ('escaped', 'retry', '2026-09-27', 'D-5', 'escaped DIV-1 2026-09-27 D-5'),
        ('reversal', 'defer', '2026-09-27', 'D-4', 'reversal 2026-09-27 D-4'),
        ('sample', 'retry', '2026-09-27', 'D-5', 'sample 2026-09-28 D-1 of 2026-09-27 D-5'),
        ('undo', 'defer', '2026-09-27', 'D-3', 'undo 2026-09-27 D-3')]
    damage(ws)
    with pytest.raises(ValueError):
        budget_classes.select(ws, 14)


def damage(root):
    from wuwei import workspace
    path = workspace.day_dir(root) / 'events.jsonl'
    path.chmod(0o600)
    with path.open('a') as handle:
        handle.write('{"kind"')


def spend(root, cls='defer', count=20, reversals=3):
    answers(root, cls, count)
    for number in range(10, 10 + reversals):
        reverse(root, f'D-{number}', cls)


def test_table_has_a_row_per_class_but_merge(ws):
    from wuwei import budget_classes, cruise, workspace
    raise_to(ws, 'defer', 2)
    spend(ws)
    rows = {row['class']: row for row in budget_classes.table(ws, workspace.load_config(ws))}
    assert set(rows) == set(cruise.CLASSES) - {'merge'}
    row = rows['defer']
    assert (row['level'], row['answered'], row['spent'], row['allowance'], row['state'], row['held']) == (
        2, 20, 3, 2.0, 'spent', False)
    assert row['events'] == [f'reversal 2026-09-28 D-{n}' for n in (10, 11, 12)]
    assert (rows['retry']['answered'], rows['retry']['spent'], rows['retry']['state']) == (0, 0, 'ok')


# Phase 4: the steward evaluation


def level(root, name='defer'):
    from wuwei import cruise, workspace
    return cruise.level(workspace.load_config(root), name, cruise.running(root))


def test_a_spent_budget_lowers_the_class_once(ws):
    from wuwei import budget_classes, cruise
    raise_to(ws, 'defer', 2)
    spend(ws)
    budget_classes.evaluate(ws)
    assert level(ws) == 1 and cruise.running(ws)['budget'] == {'defer': 2}
    line = ledger(ws)[-1]
    assert line['action'] == 'lower' and line['reason'].startswith('budget spent: defer')
    assert all(f'reversal 2026-09-28 D-{n}' in line['reason'] for n in (10, 11, 12))
    assert line['evidence'] == '.wuwei/days/2026-09-28/decisions/D-12.md'
    count = len(ledger(ws))
    budget_classes.evaluate(ws)
    assert len(ledger(ws)) == count and level(ws) == 1


@pytest.mark.parametrize('count,reversals', [(20, 2), (5, 1)])
def test_an_unspent_budget_keeps_the_level(ws, count, reversals):
    from wuwei import budget_classes
    raise_to(ws, 'defer', 2)
    spend(ws, count=count, reversals=reversals)
    budget_classes.evaluate(ws)
    assert level(ws) == 2 and ledger(ws)[-1]['reason'] == 'test setup'


def test_a_refilled_window_restores_the_level(ws, monkeypatch):
    from wuwei import budget_classes, cruise
    raise_to(ws, 'defer', 2)
    spend(ws)
    budget_classes.evaluate(ws)
    at(monkeypatch, '2026-10-13T12:00:00+00:00')
    budget_classes.evaluate(ws)
    assert level(ws) == 2 and 'budget' not in cruise.running(ws)
    line = ledger(ws)[-1]
    assert line['action'] == 'raise' and line['reason'].startswith('budget refilled: defer back to L2')


def test_a_fast_burn_writes_one_nudge_a_day(ws, capsys):
    from wuwei import budget_classes
    from wuwei.__main__ import main
    raise_to(ws, 'defer', 2)
    spend(ws, reversals=2)
    budget_classes.evaluate(ws)
    burn, = [e['payload'] for e in events(ws) if e['kind'] == 'cruise.burn']
    assert burn['class'] == 'defer' and burn['events'] == ['reversal 2026-09-28 D-10', 'reversal 2026-09-28 D-11']
    assert 'reversal 2026-09-28 D-11' in burn['reason'] and level(ws) == 2
    budget_classes.evaluate(ws)
    assert len([e for e in events(ws) if e['kind'] == 'cruise.burn']) == 1
    main(['nudges', '--all'])  # #742: the raw classification
    assert any(line.startswith('nudge: defer burns its error budget') and line.endswith('Run: wuwei cruise budget')
               for line in capsys.readouterr().out.splitlines())


def test_a_spent_class_at_l0_is_not_held(ws):
    from wuwei import budget_classes, cruise
    spend(ws)
    budget_classes.evaluate(ws)
    assert level(ws) == 0 and cruise.running(ws) == {'levels': {}, 'changed': {}} and ledger(ws) == []


def test_the_steward_review_evaluates_the_budget(ws, monkeypatch):
    from wuwei import budget_classes, steward
    calls = []
    monkeypatch.setattr(budget_classes, 'evaluate', calls.append)
    steward.review(ws)
    assert calls == [ws]


# Phase 6: promotion needs the budget unspent


def test_no_raise_card_with_a_spent_budget(ws, monkeypatch):
    # The lowering is the last change, so only the spent budget keeps the raise card away.
    from wuwei import budget_classes
    raise_to(ws, 'defer', 2)
    spend(ws)
    budget_classes.evaluate(ws)
    at(monkeypatch, '2026-09-28T12:01:00+00:00')
    agree(ws, 10)
    assert propose(ws) == [] and cards(ws) == {}


def test_no_raise_card_after_a_budget_event_since_the_last_change(ws):
    agree(ws, 10)
    spend(ws, reversals=1)
    assert propose(ws) == [] and cards(ws) == {}


# Phase 7: the command and the status line


def test_cruise_budget_prints_the_table(ws, capsys):
    from wuwei import commands
    from wuwei.__main__ import main
    assert commands.read_only(['cruise', 'budget'])
    assert main(['cruise', 'budget']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ['class', 'level', 'answered', 'spent', 'allowance', 'burn', 'state']
    assert len(lines) == 14 and not any(line.startswith('merge') for line in lines)
    raise_to(ws, 'defer', 2)
    spend(ws)
    assert main(['cruise', 'budget']) == 1
    row = next(line for line in capsys.readouterr().out.splitlines() if line.startswith('defer'))
    assert row.split() == ['defer', 'L2', '20', '3', '2', '10.5', 'spent']
    damage(ws)
    assert main(['cruise', 'budget']) == 2
    assert 'wuwei cruise budget:' in capsys.readouterr().err


def test_the_status_line_names_held_classes(ws):
    from wuwei import state
    state._write_state(lambda data: None, ws, reserved=False)
    path = ws / '.wuwei/memory/cruise.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'levels': {'defer': 1}, 'changed': {}, 'budget': {'defer': 2}}))
    assert '\ncruise L2 · budget defer spent\nplugin ' in status_line(ws)
    path.write_text(json.dumps({'levels': {'defer': 1, 'retry': 1}, 'changed': {},
                                'budget': {'retry': 2, 'defer': 2}}))
    assert '\ncruise L2 · budget defer, retry spent\nplugin ' in status_line(ws)
