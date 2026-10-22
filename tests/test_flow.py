"""In-progress work flows as a Kanban board (flow-order): class of service, then closest to done, then age."""

import datetime

import pytest

from conftest import footer, make_pr, write_plan
from wuwei import board, hook, plan, ws


def ago(**delta):
    return (ws.now() - datetime.timedelta(**delta)).isoformat(timespec='seconds')


def items(root, *ids, **extra):
    write_plan(root, [{'id': i, 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open',
                       'approved': True, **extra.get(i.replace('-', '_'), {})} for i in ids])


def pr(number, item, created=None, updated=None, **given):
    found = make_pr(number=number, head=str(number % 10) * 40, body=footer(item), created=created, **given)
    return {**found, 'updatedAt': updated} if updated else found


def order(root):
    return [row['item'] for row in board.compute(root) if row['item'] != 'team']


def stop(root, session='s1'):
    return hook.handle(root, 'Stop', {'session_id': session, 'cwd': str(root)})


def test_the_item_closest_to_done_lists_first_and_age_orders_ties(root, fake):
    items(root, 'I-1', 'I-2', 'I-3')
    fake.prs['41'] = {**pr(41, 'I-1', created=ago(days=5), updated=ago(hours=3), files=('src/app.py',)), 'isDraft': True}
    fake.prs['42'] = pr(42, 'I-2')  # just got its CI result; its gates are next
    fake.prs['43'] = pr(43, 'I-3', created=ago(hours=1))  # the same column, older
    assert order(root) == ['I-3', 'I-2', 'I-1']
    reason = stop(root)['reason']
    assert reason.index('I-3') < reason.index('I-2') < reason.index('I-1')
    shown = board.text(board.compute(root), root)
    assert 'I-1 change (acme/app#41) [standard, last event 3h ago]' in shown
    assert 'I-3 change (acme/app#43) [standard, last event 1h ago]' in shown


def test_an_expedite_item_lists_above_every_class_and_a_second_is_sent_back(root, fake):
    (root / ws.DIR / 'goals.md').write_text('# Goals\n\n## G-1\nOutcome: x\n\n## G-2\nOutcome: y\nDate: 2026-12-01\n')
    items(root, 'I-1', 'I-2', 'I-3', 'I-4', I_2={'class': 'expedite'}, I_3={'goal': 'G-2'}, I_4={'class': 'intangible'})
    fake.prs['41'] = pr(41, 'I-1', created=ago(days=3))
    fake.prs['44'] = pr(44, 'I-4', created=ago(days=4))
    assert order(root) == ['I-2', 'I-3', 'I-1', 'I-4']
    assert [row.get('class') for row in board.compute(root) if row['item'] != 'team'] == ['expedite', 'fixed-date', 'standard', 'intangible']
    with pytest.raises(ValueError, match='I-2 is already expedite'):
        plan.add(root, 'I-5', 'urgent too', 'G-1', 'acme/app', 'light', {'value': 1, 'time': 1, 'risk': 1, 'size': 1},
                 cls='expedite')
    with pytest.raises(ValueError, match='class of service'):
        plan.add(root, 'I-5', 'x', 'G-1', 'acme/app', 'light', {'value': 1, 'time': 1, 'risk': 1, 'size': 1}, cls='urgent')
    assert plan.add(root, 'I-2', 'still urgent', 'G-1', 'acme/app', 'light', {'value': 1, 'time': 1, 'risk': 1, 'size': 1},
                    cls='expedite')['class'] == 'expedite'  # the expedite item itself may be re-added


def test_an_item_that_waits_shows_waiting_and_adds_its_cost_of_delay_to_what_it_waits_on(root, fake):
    plan.add(root, 'I-1', 'base', 'G-1', 'acme/app', 'light', {'value': 8, 'time': 5, 'risk': 3, 'size': 2})
    plan.add(root, 'I-2', 'on top', 'G-1', 'acme/app', 'light', {'value': 5, 'time': 3, 'risk': 2, 'size': 1}, after=['i-1'])
    plan.approve(root, 'yes')
    assert plan.find(root, 'I-1')['score'] == 13.0  # (16 + 10) / 2
    rows = {row['item']: row for row in board.compute(root)}
    assert rows['I-2']['gaps'][0] == {**rows['I-2']['gaps'][0], 'text': 'waiting on I-1', 'actionable': False}
    assert rows['I-1']['score'] == 13.0 and rows['I-2']['score'] == 10.0
    reason = stop(root)['reason']
    assert 'I-1: no pull request yet' in reason and 'I-2' not in reason.split('Left out')[0]
    plan.mark(root, 'I-1', 'done', 'merged')
    ws.cache_put(root, 'board', None)
    assert not any(g['text'].startswith('waiting on') for row in board.compute(root) for g in row['gaps'])
    with pytest.raises(ValueError, match='I-9 is not in the plan'):
        plan.add(root, 'I-3', 'x', 'G-1', 'acme/app', 'light', {'value': 1, 'time': 1, 'risk': 1, 'size': 1}, after=['I-9'])


def test_time_criticality_rises_one_fibonacci_step_per_day_in_progress(root, fake):
    plan.add(root, 'I-1', 'slow', 'G-1', 'acme/app', 'light', {'value': 8, 'time': 5, 'risk': 3, 'size': 2})
    plan.approve(root, 'yes')
    item = plan.find(root, 'I-1')
    assert [plan.cost(item, [item], {'I-1': d}) for d in (0, 1, 2, 9)] == [8.0, 9.5, 12.0, 15.5]  # 5, 8, 13, then 20 at most
    fake.prs['42'] = pr(42, 'I-1', created=ago(days=2, hours=1))
    assert next(row for row in board.compute(root) if row['item'] == 'I-1')['score'] == 12.0


def test_in_progress_work_idle_four_hours_with_no_live_seat_shows_stale_at_the_top_of_its_class(root, fake):
    items(root, 'I-1', 'I-2')
    fake.prs['41'] = pr(41, 'I-1', created=ago(hours=5), files=('src/app.py',))  # a fix round, idle 5 hours
    fake.prs['42'] = pr(42, 'I-2', created=ago(minutes=5))  # its gates are next
    rows = {row['item']: row for row in board.compute(root)}
    assert rows['I-1']['gaps'][0]['text'] == f'stale: no event since {ago(hours=5)[:16]}, no live seat'
    assert order(root) == ['I-1', 'I-2']
    assert 'last event 5h ago' in board.text(board.compute(root), root)
    ws.cache_put(root, 'board', None)
    with pytest.MonkeyPatch.context() as patch:  # a seat started on I-1 more than 4 hours ago, still running
        patch.setattr(board, 'running', lambda root, hours=6: [{'role': 'builder', 'agent': 'b1', 'session': 's2', 'item': 'i-1'}])
        assert not any(g['text'].startswith('stale') for row in board.compute(root) for g in row['gaps'])
        assert order(root) == ['I-2', 'I-1']
    ws.record(root, 'seat.started', {'role': 'builder', 'agent': 'b1', 'session': 's9', 'item': 'i-1'})  # an event
    ws.cache_put(root, 'board', None)
    assert order(root) == ['I-2', 'I-1'] and 'last event 0h ago' in board.text(board.compute(root), root)


def test_an_item_never_waits_on_itself(root):
    plan.add(root, 'I-1', 'base', 'G-1', 'acme/app', 'light', {'value': 1, 'time': 1, 'risk': 1, 'size': 1})
    with pytest.raises(ValueError, match='i-1 is not in the plan, or is this item or waits on it'):
        plan.add(root, 'I-1', 'base', 'G-1', 'acme/app', 'light', {'value': 1, 'time': 1, 'risk': 1, 'size': 1}, after=['i-1'])
    assert plan.find(root, 'I-1').get('after') == []


def test_the_cli_and_the_lead_file_name_a_class_and_what_an_item_waits_on(root, monkeypatch, capsys, tmp_path):
    import json
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    wsjf = ['--goal', 'G-1', '--repo', 'acme/app', '--value', '5', '--time', '3', '--risk', '2', '--size', '1']
    assert cli.main(['plan', 'add', 'I-1', 'base', *wsjf, '--class', 'expedite']) == 0
    assert cli.main(['plan', 'add', 'I-2', 'on top', *wsjf, '--after', 'I-1', '--class', 'intangible']) == 0
    assert (plan.find(root, 'I-1')['class'], plan.find(root, 'I-2')['after']) == ('expedite', ['I-1'])
    assert cli.main(['plan', 'add', 'I-3', 'urgent', *wsjf, '--class', 'expedite']) == 2
    assert 'I-1 is already expedite' in capsys.readouterr().err
    lead = tmp_path / 'lead.json'
    lead.write_text(json.dumps([{'id': 'I-4', 'title': 't', 'goal': 'G-1', 'repo': 'acme/app', 'class': 'fixed-date',
                                 'after': 'I-2', 'scores': {'value': 1, 'time': 1, 'risk': 1, 'size': 1}}]))
    [item] = plan.add_from(root, lead)
    assert (item['class'], item['after'], plan.find(root, 'I-2')['score']) == ('fixed-date', ['I-2'], 13.0)


def test_a_hand_edited_class_date_or_score_never_breaks_the_board(root, fake):
    items(root, 'I-1', 'I-2', I_1={'class': 'urgent', 'added': 'yesterday', 'scores': {'value': 4}, 'score': 3},
          I_2={'after': ['I-1'], 'added': ''})
    rows = {row['item']: row for row in board.compute(root)}
    assert (rows['I-1']['class'], rows['I-1']['last'], rows['I-1']['score']) == ('standard', None, 3)
    assert rows['I-2']['gaps'][0]['text'] == 'waiting on I-1' and 'I-1 change [standard]' in board.text(list(rows.values()))


ONE = {'value': 1, 'time': 1, 'risk': 1, 'size': 1}


def test_a_wait_that_would_close_a_cycle_is_refused(root):
    for item, after in (('A', ()), ('B', ['A']), ('C', ['b'])):
        plan.add(root, item, item, 'G-1', 'acme/app', 'light', ONE, after=after)
    for item, after in (('A', 'B'), ('A', 'c'), ('B', 'C')):
        with pytest.raises(ValueError, match=f'{after} is not in the plan, or is this item or waits on it'):
            plan.add(root, item, item, 'G-1', 'acme/app', 'light', ONE, after=[after])
    assert [plan.find(root, i).get('after') for i in 'ABC'] == [[], ['A'], ['B']]
    assert plan.add(root, 'C', 'C', 'G-1', 'acme/app', 'light', ONE, after=['A'])['after'] == ['A']  # no cycle: A waits on nothing


@pytest.mark.parametrize('closed', ['done', 'dropped', 'parked'])
def test_a_closed_waiter_stops_adding_its_cost_of_delay(root, closed):
    plan.add(root, 'I-1', 'base', 'G-1', 'acme/app', 'light', {'value': 8, 'time': 5, 'risk': 3, 'size': 2})
    plan.add(root, 'I-2', 'on top', 'G-1', 'acme/app', 'light', {'value': 5, 'time': 3, 'risk': 2, 'size': 1}, after=['I-1'])
    assert plan.find(root, 'I-1')['score'] == 13.0
    plan.mark(root, 'I-2', closed, 'closed')
    assert plan.find(root, 'I-1')['score'] == 8.0


def test_a_done_expedite_item_frees_the_class_and_a_restore_is_held_to_one(root):
    plan.add(root, 'E-1', 'urgent', 'G-1', 'acme/app', 'light', ONE, cls='expedite')
    plan.mark(root, 'E-1', 'done', 'merged')
    assert plan.add(root, 'E-2', 'next urgent', 'G-1', 'acme/app', 'light', ONE, cls='expedite')['class'] == 'expedite'
    with pytest.raises(ValueError, match='E-2 is already expedite'):
        plan.mark(root, 'E-1', 'open', 'restored')
    with pytest.raises(ValueError, match='E-2 is already expedite'):
        plan.add(root, 'E-1', 'urgent again', 'G-1', 'acme/app', 'light', ONE)  # a re-add reopens it as expedite
    assert plan.find(root, 'E-1')['status'] == 'done'
    plan.mark(root, 'E-2', 'parked', 'later')
    assert plan.mark(root, 'E-1', 'open', 'restored')['status'] == 'open'
    plan.mark(root, 'E-1', 'open', 'run evidence')  # an open item marked open again is no second start


def test_a_rescore_never_stamps_an_item_so_another_clones_edit_wins_the_merge(root, tmp_path):
    import shutil
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', ONE, promise='old promise')
    plan.add(root, 'B', 'b', 'G-1', 'acme/app', 'light', ONE, after=['A'])
    shutil.copytree(root, other := tmp_path / 'clone-y')
    plan.add(other, 'A', 'a', 'G-1', 'acme/app', 'light', ONE, promise='new promise from Y')  # the owner edits A on Y
    before = plan.find(root, 'A')['changed']
    plan.mark(root, 'B', 'done', 'merged')  # later on X: A's score drops, nothing a person edits
    assert (plan.find(root, 'A')['changed'], plan.find(root, 'A')['score']) == (before, 3.0)
    assert plan.merge(other, (root / ws.DIR / 'plan.json').read_bytes())
    assert (plan.find(other, 'A')['promise'], plan.find(other, 'A')['score'], plan.find(other, 'B')['status']) == (
        'new promise from Y', 3.0, 'done')


def test_the_stage_is_read_from_the_rows_own_gaps_before_waiting_or_stale_text(root, fake):
    items(root, 'I-1', 'I-2', 'I-3', I_2={'after': ['I-1']})
    fake.prs['42'] = pr(42, 'I-2', checks='FAILURE')  # waits on I-1, and its CI is red: a fix round, not ready to merge
    fake.prs['43'] = pr(43, 'I-3')  # its gates are next
    assert order(root) == ['I-3', 'I-2', 'I-1']
    items(root, 'I-4', 'I-5')
    fake.prs.clear()
    fake.prs['44'] = pr(44, 'I-4', created=ago(hours=5))  # stale at gates
    fake.prs['45'] = pr(45, 'I-5', created=ago(hours=6), files=('src/app.py',))  # stale in a fix round, older
    ws.cache_put(root, 'board', None)
    assert order(root) == ['I-4', 'I-5']


def test_time_in_progress_counts_from_the_items_first_pr(root, fake):
    items(root, 'I-1', I_1={'scores': {'value': 8, 'time': 5, 'risk': 3, 'size': 2}, 'framework': 'wsjf'})
    fake.prs['41'] = pr(41, 'I-1', created=ago(days=2, hours=1))
    fake.prs['42'] = pr(42, 'I-1')
    assert {row['score'] for row in board.compute(root) if row['item'] == 'I-1'} == {12.0}
