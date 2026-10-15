"""Work in progress keeps moving without the owner's nudge: owed replies, the watch pass."""

import datetime

from conftest import make_pr, write_plan
from wuwei import board, hook, plan, report, ws

THREAD = 'https://acme.slack.com/archives/C0123ABC/p1760510000000200'


def test_an_owed_reply_is_on_the_board_and_overdue_once_past_due(root, fake):
    item = plan.owe(root, THREAD, 'Dade asks whether the workspace filter ships today', 'Dade', within='2h')
    assert item['id'] == 'R-1' and item['kind'] == 'reply'
    row = next(r for r in board.compute(root) if r['item'] == 'R-1')
    assert row['gaps'][0]['text'].startswith(f'reply owed to Dade in {THREAD}, due ')
    assert row['gaps'][0]['actionable'] and row['gaps'][0]['kind'] == 'safety'
    rows = plan.items(root)
    rows[0]['due'] = (ws.now() - datetime.timedelta(minutes=5)).isoformat(timespec='seconds')
    plan.save(root, rows)
    assert 'overdue since' in next(r for r in board.compute(root) if r['item'] == 'R-1')['gaps'][0]['text']


def test_a_send_into_the_thread_closes_the_reply_by_itself(root, fake):
    plan.owe(root, THREAD, 'filter question', 'Dade')
    out = hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'mcp__slack__slack_send_message', 'cwd': str(root),
        'tool_input': {'channel_id': 'C0123ABC', 'thread_ts': '1760510000.000200', 'text': 'Yes, it ships at 15:00.'},
        'tool_response': {'ok': True}})
    assert plan.find(root, 'R-1')['status'] == 'done'
    assert ws.rows(root, 'reply.sent')[0]['data']['id'] == 'R-1'
    assert 'R-1' in out['hookSpecificOutput']['additionalContext']


def test_a_send_elsewhere_leaves_the_reply_open(root, fake):
    plan.owe(root, THREAD, 'filter question', 'Dade')
    hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'mcp__slack__slack_send_message', 'cwd': str(root),
        'tool_input': {'channel_id': 'C0999', 'text': 'unrelated'}, 'tool_response': {'ok': True}})
    assert plan.find(root, 'R-1')['status'] == 'open'


def test_an_owed_reply_keeps_the_turn_going(root, fake):
    plan.owe(root, THREAD, 'filter question', 'Dade')
    out = hook.handle(root, 'Stop', {'session_id': 's1', 'stop_hook_active': False, 'cwd': str(root)})
    assert 'R-1' in out['reason']


def test_status_all_shows_process_gaps_for_the_watch(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open'}])
    fake.prs['42'] = make_pr(lines=300)
    quiet = board.compute(root)[0]['gaps']
    every = board.compute(root, everything=True)[0]['gaps']
    assert not any('changed lines' in g['text'] for g in quiet)
    assert any('changed lines' in g['text'] for g in every)


def test_the_report_counts_replies_and_response_time(root, fake):
    plan.owe(root, THREAD, 'filter question', 'Dade')
    plan.mark(root, 'R-1', 'done', 'replied')
    plan.owe(root, 'https://acme.slack.com/archives/C1/p1', 'second', 'Ana')
    text = report.day(root)
    assert 'Replies: 2 owed today, 1 closed, 1 open, 0 overdue' in text


def test_a_watch_pass_is_recorded_and_says_when_the_last_was(root, fake, capsys):
    from wuwei import __main__ as cli
    import os
    os.chdir(root)
    assert cli.main(['watch', '--record', 'acted on 2 PRs, 1 reply owed']) == 0
    assert ws.rows(root, 'watch.pass')[0]['data']['summary'] == 'acted on 2 PRs, 1 reply owed'
    assert cli.main(['watch']) == 0
    assert 'last pass' in capsys.readouterr().out
