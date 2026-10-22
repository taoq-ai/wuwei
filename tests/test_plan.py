import json

import pytest

from conftest import answered
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


def test_restore_reopens_a_parked_or_dropped_item(root, monkeypatch, capsys):
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.mark(root, 'I-1', 'parked', 'later')
    assert cli.main(['plan', 'restore', 'i-1']) == 0
    assert capsys.readouterr().out == 'I-1 open again\n'
    assert (plan.find(root, 'I-1')['status'], plan.find(root, 'I-1')['reason']) == ('open', 'restored')
    assert ws.rows(root, 'item.open')[-1]['data'] == {'id': 'I-1', 'reason': 'restored'}
    assert cli.main(['plan', 'restore', 'I-9']) == 2
    assert capsys.readouterr().err == 'wuwei: I-9 is not in the plan\n'


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
    assert item['host'] == 'agent'
    lead.write_text(json.dumps([{'id': 'TIN-2', 'title': 'long', 'scores': scores(), 'host': 'session'}]))
    assert plan.add_from(root, lead)[0]['host'] == 'session'


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
    return hook.handle(root, 'PostToolUse', answered(root, [question], {question: reply}))


def test_a_plan_pass_offers_each_goal_whose_date_passed_once(root, monkeypatch, capsys):
    import datetime
    monkeypatch.chdir(root)
    day = lambda n: (ws.now() + datetime.timedelta(days=n)).date().isoformat()  # noqa: E731
    goals_md(root, {'G-1': day(-1), 'G-2': day(1), 'G-3': day(0), 'G-4': '', 'G-5': 'end of Q4', 'G-6': day(-9),
                    'G-7': day(-1), 'Release': day(-1), 'G-8': '1 October 2026', 'G-9': day(-3), 'g-10': day(-1),
                    'g-11': day(-1), 'G-12': day(-40)[:7]})
    answer_goal(root, 'goal: G-6 met? 100 percent at 2026-10-01.', 'Yes')
    answer_goal(root, 'goal: g-10 met? done.', 'Yes')  # a lowercase heading, ruled met in lowercase
    real = ws.now()
    monkeypatch.setattr(ws, 'now', lambda: real - datetime.timedelta(days=5))  # met early, before its date
    answer_goal(root, 'goal: G-7 met? shipped early.', 'Yes')
    monkeypatch.setattr(ws, 'now', lambda: real - datetime.timedelta(days=3))  # a no on the goal's own date
    answer_goal(root, 'goal: G-9 met? not yet.', 'No')
    monkeypatch.setattr(ws, 'now', lambda: real)
    out = plan_pass(capsys)
    assert out.count(f"goal G-1 dated {day(-1)}: ask the owner 'goal: G-1 met? <evidence>'") == 1
    assert [line for line in out.splitlines() if line.startswith('goal ')] == [
        f"goal G-1 dated {day(-1)}: ask the owner 'goal: G-1 met? <evidence>'",
        f"goal G-11 dated {day(-1)}: ask the owner 'goal: G-11 met? <evidence>'"]
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
    goals_md(root, {'G-2': day(-1), 'G-3': day(-6)})
    monkeypatch.setattr(ws, 'now', lambda: real - datetime.timedelta(days=5))  # a no given five days ago
    answer_goal(root, 'goal: G-3 met? not yet.', 'No')
    monkeypatch.setattr(ws, 'now', lambda: real)
    assert 'goal G-3' not in plan_pass(capsys)
    goals_md(root, {'G-2': day(-1), 'G-3': day(-5)})  # moved to the day of the no: still held
    assert 'goal G-3' not in plan_pass(capsys)
    goals_md(root, {'G-2': day(-1), 'G-3': day(-2)})  # the owner moved the date past the day of the no
    assert f"goal G-3 dated {day(-2)}: ask the owner 'goal: G-3 met? <evidence>'" in plan_pass(capsys)


def test_a_goal_the_owner_rewrites_in_place_is_a_new_goal(root, monkeypatch, capsys):
    import datetime
    from wuwei import report
    monkeypatch.chdir(root)
    day = lambda n: (ws.now() + datetime.timedelta(days=n)).date().isoformat()  # noqa: E731
    goals = root / ws.DIR / 'goals.md'
    goals.write_text(f'# Goals\n\n## G-1\nOutcome: ship 3.0\nDate: {day(-3)}\n')
    answer_goal(root, 'goal: G-1 met? 3.0 shipped.', 'Yes')
    assert [r['data']['outcome'] for r in ws.rows(root, 'ruling')] == ['ship 3.0']
    assert 'goal G-1' not in plan_pass(capsys)
    assert 'Met goals: G-1.' in report.day(root)
    goals.write_text(f'# Goals\n\n## G-1\nOutcome: halve review latency\nDate: {day(-1)}\n')
    assert f"goal G-1 dated {day(-1)}: ask the owner 'goal: G-1 met? <evidence>'" in plan_pass(capsys)
    assert 'Met goals: none.' in report.day(root)


def codex_job(folder, status, said=''):
    """A fixture copy of the Codex companion's job file shape (state/<workspace>/jobs/<id>.json), read 2026-10-20."""
    import json
    path = folder / 'task-mukx4f0u-z6hz7v.json'
    path.write_text(json.dumps({'id': 'task-mukx4f0u-z6hz7v', 'kind': 'task', 'status': status, 'phase': 'done',
                                'pid': None, 'logFile': str(folder / 'task-mukx4f0u-z6hz7v.log'),
                                'result': {'status': 0, 'threadId': 't', 'rawOutput': said, 'touchedFiles': []}}))
    return path


@pytest.mark.parametrize('status, said, shown', [
    ('running', '', 'job running'),
    ('queued', '', 'job queued'),
    ('completed', 'Done. Handoff in [HANDOFF.md](/wt/i-1/HANDOFF.md).', 'job completed, handoff /wt/i-1/HANDOFF.md'),
    ('completed', 'Pushed; see `/wt/i-1/HANDOFF.md`', 'job completed, handoff /wt/i-1/HANDOFF.md'),
    ('completed', 'Pushed and opened the draft.', 'job completed'),
    ('failed', 'turn failed', 'job failed'),
    ('cancelled', '', 'job cancelled'),
    ('completed', 'Should FR-026 hold the old rule or the new one?\n', 'job asked a question'),
    ('failed', 'turn failed: why did the build break?', 'job failed'),
    ('cancelled', 'Should I keep going?', 'job cancelled'),
])
def test_a_registered_codex_job_shows_its_state_on_the_board(root, fake, monkeypatch, tmp_path, status, said, shown):
    from wuwei import __main__ as cli, board
    monkeypatch.chdir(root)
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.approve(root, 'Approve')
    assert cli.main(['plan', 'run', 'A', '--job', str(codex_job(tmp_path, status, said))]) == 0
    assert [g['text'] for r in board.compute(root) if r['item'] == 'A' for g in r['gaps']] == [f'run: {shown}']


@pytest.mark.parametrize('content', [None, 'not json', '[1]', '{}', '{"status": null}', '{"status": "running", "result": "x"}',
                                     pytest.param('[' * 100000 + ']' * 100000, id='nested-200KB'), '{"status": ["running"]}',
                                     pytest.param('{"status": ' + '[' * 100000 + ']' * 100000 + '}', id='nested-status'),
                                     pytest.param('{"status": "running", "result": {"rawOutput": ' + '[' * 100000 + ']' * 100000 + '}}',
                                                  id='nested-rawOutput')])
def test_an_unreadable_codex_job_file_never_reads_done(root, fake, monkeypatch, tmp_path, content):
    from wuwei import __main__ as cli, board
    monkeypatch.chdir(root)
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.approve(root, 'Approve')
    job = tmp_path / 'job.json'
    content is None or job.write_text(content)
    assert cli.main(['plan', 'run', 'A', '--reason', 'Codex builder in /wt/a', '--job', str(job)]) == 0
    try:  # Python 3.14 parses arrays nested 100,000 deep; 3.13 does not
        parsed = json.loads(content or '')
    except (ValueError, RecursionError):
        parsed = None
    shown = 'job running' if isinstance(parsed, dict) and parsed.get('status') == 'running' else 'job state unreadable'
    assert [g['text'] for r in board.compute(root) if r['item'] == 'A' for g in r['gaps']] == [f'run: Codex builder in /wt/a; {shown}']
    assert cli.main(['plan', 'run', 'A', '--reason', 'job done, HANDOFF read']) == 0
    assert plan.find(root, 'A')['job'] == str(job)


def test_the_plan_list_shows_an_item_with_no_goal(root, monkeypatch, capsys):
    """#1209: an owe-style item kept with "goal": null is listed with a blank goal, never a TypeError."""
    from conftest import write_plan
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    write_plan(root, [{'id': 'R-10', 'title': 'reply owed', 'goal': None, 'tier': None, 'status': None, 'repo': None, 'score': 0}])
    assert cli.main(['plan']) == 0
    [row] = [line for line in capsys.readouterr().out.splitlines() if 'R-10' in line]
    assert 'None' not in row and row.split() == ['0', 'R-10', 'open', 'reply', 'owed']  # a null status reads open, its default


def test_a_job_file_read_while_the_companion_writes_it_is_read_again(root, fake, monkeypatch, tmp_path):
    """#1212: a read that meets the companion's half-written job file shows the job's state, never state unreadable."""
    from wuwei import __main__ as cli, board
    monkeypatch.chdir(root)
    plan.add(root, 'A', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.approve(root, 'Approve')
    path = codex_job(tmp_path, 'running')
    whole = path.read_text()
    assert cli.main(['plan', 'run', 'A', '--job', str(path)]) == 0
    path.write_text(whole[:40])  # the companion truncated the file and has not finished writing it

    def written(seconds):
        path.write_text(whole)
    monkeypatch.setattr(board.time, 'sleep', written)
    assert [g['text'] for r in board.compute(root) if r['item'] == 'A' for g in r['gaps']] == ['run: job running']


def test_plan_add_stores_the_builder_host_and_refuses_any_other(root, monkeypatch, capsys):
    """builder-host: --host session|agent, agent by default; any other value is refused at the CLI and in add."""
    import json
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    add = ['plan', 'add', 'I-1', 'long item', '--goal', 'G-1', '--repo', 'acme/app', '--value', '5', '--time', '3', '--risk', '2', '--size', '2']
    assert cli.main(add) == 0 and plan.find(root, 'I-1')['host'] == 'agent'
    assert cli.main(add + ['--host', 'session']) == 0
    capsys.readouterr()
    assert cli.main(['plan', 'show', 'I-1']) == 0 and json.loads(capsys.readouterr().out)['host'] == 'session'
    with pytest.raises(SystemExit):
        cli.main(add + ['--host', 'codex'])
    with pytest.raises(ValueError, match='host must be one of agent, session'):
        plan.add(root, 'I-2', 't', 'G-1', 'acme/app', 'light', scores(), host='Session')
    assert plan.find(root, 'I-1')['host'] == 'session' and plan.find(root, 'I-2') is None


def test_plan_session_records_a_host_session_builder_and_refuses_an_agent_item(root, monkeypatch, capsys):
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'standard', scores(), host='session')
    plan.add(root, 'I-2', 'b', 'G-1', 'acme/app', 'standard', scores())
    assert cli.main(['plan', 'session', 'i-1', 'session_01ABC']) == 0
    assert capsys.readouterr().out == 'I-1 builder session session_01ABC recorded\n'
    assert (plan.find(root, 'I-1')['session'], plan.find(root, 'I-1')['status']) == ('session_01ABC', 'open')
    assert cli.main(['plan', 'session', 'I-2', 'session_02']) == 2
    assert '(I-2: host agent)' in capsys.readouterr().err and 'session' not in plan.find(root, 'I-2')
    assert cli.main(['plan', 'session', 'I-1']) == 2 and plan.find(root, 'I-1')['session'] == 'session_01ABC'
