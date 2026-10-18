import pytest

from wuwei import plan, ws


def scores(value=8, time=5, risk=3, size=2):
    return {'value': value, 'time': time, 'risk': risk, 'size': size}


def test_wsjf_ranks_the_queue(root):
    plan.add(root, 'I-1', 'small win', 'G-1', 'acme/app', 'light', scores(size=1))
    plan.add(root, 'I-2', 'big job', 'G-1', 'acme/app', 'standard', scores(size=13))
    assert [item['id'] for item in plan.items(root)] == ['I-1', 'I-2']
    assert plan.items(root)[0]['score'] == 16.0


def test_rice_when_configured(root):
    ws.set_config(root, 'prioritisation', 'rice')
    item = plan.add(root, 'I-1', 't', 'G-1', 'acme/app', 'light',
                    {'reach': 100, 'impact': 2, 'confidence': 0.8, 'effort': 4})
    assert item['score'] == 40.0


@pytest.mark.parametrize('bad', [scores(value=4), scores(size=0), {'value': 1}])
def test_scores_outside_the_scale_are_refused(root, bad):
    with pytest.raises(ValueError):
        plan.add(root, 'I-1', 't', 'G-1', 'acme/app', 'light', bad)


def test_parked_items_sink_and_are_recorded(root):
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores(size=1))
    plan.add(root, 'I-2', 'b', 'G-1', 'acme/app', 'light', scores(size=2))
    plan.mark(root, 'I-1', 'parked', 'two fix rounds without a pass')
    assert [item['id'] for item in plan.items(root)] == ['I-2', 'I-1']
    assert ws.rows(root, 'item.parked')[0]['data']['reason'] == 'two fix rounds without a pass'


def test_adding_an_id_again_rescores_it_and_reopens_a_dropped_item(root):
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.mark(root, 'I-1', 'dropped', 'wrong scores')
    item = plan.add(root, 'i-1', 'a better title', 'G-1', 'acme/app', 'standard', scores(value=13))
    assert (item['id'], item['title'], item['tier'], item['status'], item['score']) == ('I-1', 'a better title', 'standard', 'open', 10.5)
    assert len(plan.items(root)) == 1 and ws.rows(root, 'item.updated')


def test_restore_reopens_a_parked_or_dropped_item(root):
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.mark(root, 'I-1', 'parked', 'later')
    assert plan.restore(root, 'I-1')['status'] == 'open'
    with pytest.raises(ValueError):
        plan.restore(root, 'I-9')


def test_candidates_are_added_from_the_lead_file_with_its_own_field_names(root, tmp_path):
    import json
    lead = tmp_path / 'lead.json'
    lead.write_text(json.dumps({'candidates': [
        {'id': 'TIN-1', 'title': 'routing', 'goal': 'G-1', 'repository': 'acme/app', 'tier': 'standard',
         'scores': {'business_value': 8, 'time_criticality': 5, 'risk_reduction': 3, 'job_size': 2},
         'why': 'every call routes wrong', 'promise': 'calls route to their client',
         'acceptance': ['given a Gong call, when it arrives, then it lands with its client']}]}))
    [item] = plan.add_from(root, lead)
    assert (item['repo'], item['score'], item['promise']) == ('acme/app', 8.0, 'calls route to their client')
    assert item['acceptance'] == ['given a Gong call, when it arrives, then it lands with its client']


def test_a_seat_reads_its_item_promise_from_the_plan(root, monkeypatch, capsys):
    import json
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    assert cli.main(['plan', 'add', 'I-7', 'mid-day item', '--goal', 'G-1', '--repo', 'acme/app', '--value', '5',
                     '--time', '3', '--risk', '2', '--size', '2', '--promise', 'one route per client',
                     '--accept', 'given A, when B, then C']) == 0
    capsys.readouterr()
    assert cli.main(['plan', 'show', 'I-7']) == 0
    item = json.loads(capsys.readouterr().out)
    assert (item['promise'], item['acceptance']) == ('one route per client', ['given A, when B, then C'])


def test_an_operations_item_shows_its_run_evidence_not_a_missing_pr(root, fake, monkeypatch):
    from wuwei import __main__ as cli, board
    monkeypatch.chdir(root)
    plan.add(root, 'G1-RESPLIT', 'Slack windows re-split', 'G-1', 'acme/app', 'light', scores())
    plan.approve(root, 'Approve')
    assert cli.main(['plan', 'run', 'G1-RESPLIT', '--reason', '63 of 65 windows terminal; 2 re-driven in run r-42']) == 0
    rows = [r for r in board.compute(root) if r['item'] == 'G1-RESPLIT']
    assert [g['text'] for g in rows[0]['gaps']] == ['run: 63 of 65 windows terminal; 2 re-driven in run r-42']
    cli.main(['plan', 'done', 'G1-RESPLIT', '--reason', 'r-42 done: 65 of 65 terminal'])
    assert not [r for r in board.compute(root) if r['item'] == 'G1-RESPLIT']


@pytest.mark.parametrize('data', [{'items': [{'id': 'I-1', 'title': 't'}]}, 'I-1', {'candidates': 'I-1'},
                                  [{'id': 'I-1', 'title': 't', 'scores': scores()}, {'title': 'no id'}],
                                  [{'id': 'I-1'}], ['I-1']])
def test_a_wrong_shape_candidates_file_is_refused_and_adds_nothing(root, tmp_path, monkeypatch, capsys, data):
    import json
    from wuwei import __main__ as cli
    lead = tmp_path / 'lead.json'
    lead.write_text(json.dumps(data))
    monkeypatch.chdir(root)
    assert cli.main(['plan', 'add', '--from', str(lead)]) == 2
    assert '{"candidates": [{"id", "title", ...}]}' in capsys.readouterr().err
    assert plan.items(root) == []


def test_a_changed_promise_or_acceptance_needs_approval_again(root, fake):
    from wuwei import board
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores(), promise='one route', acceptance=['given A'])
    plan.approve(root, 'Approve')
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores(), promise='one route', acceptance=['given A'])
    assert plan.find(root, 'A')['approved']
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores(), promise='two routes', acceptance=['given A'])
    assert not plan.find(root, 'A')['approved']
    assert board.compute(root)[0]['gaps'][0]['text'] == 'awaiting plan approval'
    plan.approve(root, 'Approve')
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores(), acceptance=['given B'])
    assert not plan.find(root, 'A')['approved']


def test_plan_run_refuses_without_a_reason(root, monkeypatch, capsys):
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores())
    assert cli.main(['plan', 'run', 'A']) == 2
    assert '--reason' in capsys.readouterr().err
    assert plan.find(root, 'A').get('kind') is None and not ws.rows(root, 'item.open')
    assert cli.main(['plan', 'run', 'A', '--reason', 'ran X, it showed Y']) == 0
    assert plan.find(root, 'A')['reason'] == 'ran X, it showed Y'


def test_plan_help_gives_each_action_its_own_line(capsys):
    from wuwei import __main__ as cli
    with pytest.raises(SystemExit):
        cli.main(['plan', '--help'])
    lines = capsys.readouterr().out.splitlines()
    for action in ('show', 'add', 'park', 'drop', 'done', 'run', 'restore', 'pass', 'view'):
        assert len([line for line in lines if line.lstrip().startswith(action + ' ')]) == 1, action


def test_candidates_keep_acceptance_written_under_the_cli_flag_name(root, tmp_path):
    import json
    lead = tmp_path / 'lead.json'
    lead.write_text(json.dumps([{'id': 'A-1', 'title': 't', 'scores': {'value': 3, 'time': 3, 'risk': 3, 'size': 1},
                                 'accept': ['given x, when y, then z']}]))
    [item] = plan.add_from(root, lead)
    assert item['acceptance'] == ['given x, when y, then z']


def goals_md(root, dates):
    (root / ws.DIR / 'goals.md').write_text('# Goals\n\n' + ''.join(
        f'## {name}\nOutcome: o\nMeasure: m\nDate: {date}\n\n' for name, date in dates.items()))


def plan_pass(capsys):
    from wuwei import __main__ as cli
    assert cli.main(['plan', 'pass', '--reason', 'morning']) == 0
    return capsys.readouterr().out


def answer_goal(root, question, reply):
    from wuwei import hook
    return hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'AskUserQuestion', 'cwd': str(root),
        'tool_input': {'questions': [{'question': question}]}, 'tool_response': {'answers': {question: reply}}})


def test_a_plan_pass_offers_each_goal_whose_date_passed_once(root, monkeypatch, capsys):
    import datetime
    monkeypatch.chdir(root)
    day = lambda n: (ws.now() + datetime.timedelta(days=n)).date().isoformat()  # noqa: E731
    goals_md(root, {'G-1': day(-1), 'G-2': day(1), 'G-3': day(0), 'G-4': '', 'G-5': 'end of Q4', 'G-6': day(-9),
                    'G-7': day(-1), 'Release': day(-1), 'G-8': '1 October 2026', 'G-9': day(-3)})
    answer_goal(root, 'goal: G-6 met? 100 percent at 2026-10-01.', 'Yes')
    real = ws.now()
    monkeypatch.setattr(ws, 'now', lambda: real - datetime.timedelta(days=5))  # met early, before its date
    answer_goal(root, 'goal: G-7 met? shipped early.', 'Yes')
    monkeypatch.setattr(ws, 'now', lambda: real - datetime.timedelta(days=3))  # a no on the goal's own date
    answer_goal(root, 'goal: G-9 met? not yet.', 'No')
    monkeypatch.setattr(ws, 'now', lambda: real)
    out = plan_pass(capsys)
    assert out.count(f"goal G-1 dated {day(-1)}: ask the owner 'goal: G-1 met? <evidence>'") == 1
    assert [line for line in out.splitlines() if line.startswith('goal ')] == [
        f"goal G-1 dated {day(-1)}: ask the owner 'goal: G-1 met? <evidence>'"]
    assert ws.rows(root, 'plan.pass')


def test_a_no_keeps_the_goal_quiet_until_its_date_moves(root, monkeypatch, capsys):
    import datetime
    monkeypatch.chdir(root)
    day = lambda n: (ws.now() + datetime.timedelta(days=n)).date().isoformat()  # noqa: E731
    goals_md(root, {'G-2': day(-1)})
    out = answer_goal(root, 'goal: G-2 met? 80 percent against 100.', 'No, keep it open')
    assert 'goal G-2 recorded as open' in out['hookSpecificOutput']['additionalContext']
    assert [r['data']['approved'] for r in ws.rows(root, 'ruling')] == [False]
    assert 'goal G-2' not in plan_pass(capsys)
    assert 'goal G-2' not in plan_pass(capsys)
    real = ws.now()
    monkeypatch.setattr(ws, 'now', lambda: real - datetime.timedelta(days=5))  # a no given five days ago
    answer_goal(root, 'goal: G-3 met? not yet.', 'No')
    monkeypatch.setattr(ws, 'now', lambda: real)
    goals_md(root, {'G-2': day(-1), 'G-3': day(-6)})
    assert 'goal G-3' not in plan_pass(capsys)
    goals_md(root, {'G-2': day(-1), 'G-3': day(-5)})  # moved to the day of the no: still held
    assert 'goal G-3' not in plan_pass(capsys)
    goals_md(root, {'G-2': day(-1), 'G-3': day(-2)})  # the owner moved the date past the day of the no
    assert f"goal G-3 dated {day(-2)}: ask the owner 'goal: G-3 met? <evidence>'" in plan_pass(capsys)
