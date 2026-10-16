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


def _item(id_, **extra):
    return {'id': id_, 'title': id_, 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open', **extra}


def test_a_pr_naming_two_items_links_both_and_closes_both_once_merged(root, fake):
    write_plan(root, [_item('A'), _item('B')])
    fake.prs['9'] = make_pr(9, body='Fixes both.\n\nWUWEI-Item: A\nWUWEI-Item: B')
    assert {r['item']: r['pr'] for r in board.compute(root)} == {'A': 'acme/app#9', 'B': 'acme/app#9'}
    fake.prs['9'].update(state='MERGED', mergedAt=ws.now().isoformat(timespec='seconds'))
    ws.cache_put(root, 'prs-acme__app', None)
    board.compute(root)
    assert plan.find(root, 'A')['status'] == 'done' and plan.find(root, 'B')['status'] == 'done'


def test_an_item_whose_pr_just_merged_closes_despite_a_stale_merged_cache(root, fake):
    import os
    write_plan(root, [_item('C')])
    ws.cache_put(root, 'merged-acme__app', [])
    path = root / ws.DIR / 'cache' / 'merged-acme__app.json'
    old = ws.now().timestamp() - 120
    os.utime(path, (old, old))
    fake.prs['7'] = make_pr(7, body='WUWEI-Item: C', state='MERGED')
    fake.prs['7']['mergedAt'] = ws.now().isoformat(timespec='seconds')
    board.compute(root)
    assert plan.find(root, 'C')['status'] == 'done'


def test_an_item_with_no_pr_names_its_uncounted_verdicts(root, fake):
    from conftest import verdict_text
    write_plan(root, [_item('D', approved=True)])
    path = root / ws.DIR / 'verdicts' / 'D' / 'quality-abc1234.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text(item='D', head='abc1234' + '0' * 33, pr='acme/app#1'))
    texts = [g['text'] for g in board.compute(root)[0]['gaps']]
    assert texts[0] == 'no pull request yet'
    assert texts[1].startswith('verdict .wuwei/verdicts/D/quality-abc1234.md not counted: ')


def test_a_footerless_pr_links_by_branch_name_and_closes_the_item_once_merged(root, fake):
    write_plan(root, [_item('A'), _item('B')])
    fake.prs['5'] = {**make_pr(5, body='No footer here.'), 'headRefName': 'A-fix'}
    assert {r['item']: r['pr'] for r in board.compute(root)} == {'A': 'acme/app#5', 'B': None}
    fake.prs['5'].update(state='MERGED', mergedAt=ws.now().isoformat(timespec='seconds'))
    ws.cache_put(root, 'prs-acme__app', None)
    board.compute(root)
    assert plan.find(root, 'A')['status'] == 'done' and plan.find(root, 'B')['status'] == 'open'


def test_a_footerless_pr_links_through_the_plan_prs_list(root, fake):
    write_plan(root, [_item('A', prs=['acme/app#6']), _item('B')])
    fake.prs['6'] = {**make_pr(6, body=''), 'headRefName': 'unrelated'}
    assert {r['item']: r['pr'] for r in board.compute(root)} == {'A': 'acme/app#6', 'B': None}
