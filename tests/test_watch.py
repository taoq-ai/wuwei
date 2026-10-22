"""Work in progress keeps moving without the owner's nudge: owed replies, the watch pass."""

import datetime
import json

import pytest

from conftest import launched, make_pr, write_plan
from wuwei import board, evidence, gh, hook, plan, report, ws

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


IN_THREAD = 'https://x.slack.com/archives/C1/p1729590000123456?thread_ts=1729580000.000100&cid=C1'


def _send(root, **fields):
    return hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'mcp__slack__slack_send_message', 'cwd': str(root),
        'tool_input': {**fields, 'text': 'Answered in the thread.'}, 'tool_response': {'ok': True}})


@pytest.mark.parametrize('link', [IN_THREAD, 'https://x.slack.com/archives/C1/p1729590000123456?cid=C1&thread_ts=1729580000.000100'],
                         ids=['thread_ts-first', 'cid-first'])
def test_a_send_into_the_thread_closes_a_reply_owed_on_a_message_inside_it(root, fake, link):
    plan.owe(root, link, 'Omer asks about the rollout', 'Omer')
    out = _send(root, channel_id='C1', thread_ts='1729580000.000100')
    assert plan.find(root, 'R-1')['status'] == 'done'
    assert 'R-1' in out['hookSpecificOutput']['additionalContext']


def test_a_send_naming_the_linked_message_inside_a_thread_closes_it_too(root, fake):
    plan.owe(root, IN_THREAD, 'Omer asks about the rollout', 'Omer')
    _send(root, channel='C1', thread_ts='1729590000.123456')
    assert plan.find(root, 'R-1')['status'] == 'done'


def test_a_thread_reply_stays_owed_on_another_channel_or_thread(root, fake):
    plan.owe(root, IN_THREAD, 'Omer asks about the rollout', 'Omer')
    plan.owe(root, 'https://x.slack.com/archives/C1/p1729590000123456?cid=C1 (thread_ts=1729580000.000900)', 'a note', 'Omer')
    plan.owe(root, 'https://x.slack.com/archives/C1/p1729590000123456?cid=C1&xthread_ts=1729580000.000800', 'a typo', 'Omer')
    _send(root, channel_id='C2', thread_ts='1729580000.000100')
    _send(root, channel_id='C12', thread_ts='1729580000.000100')
    _send(root, channel_id='C1', thread_ts='1729580000.000200')
    _send(root, channel_id='C1', thread_ts='1729580000.000900')
    _send(root, channel_id='C1', thread_ts='1729580000.000800')
    _send(root, channel_id='C1')
    assert [plan.find(root, i)['status'] for i in ('R-1', 'R-2', 'R-3')] == ['open', 'open', 'open']


QUOTES = [('mcp__slack__slack_send_message', lambda line: {'channel_id': 'D04OWNER', 'text': f'Still open: {line}'}),
          ('mcp__slack__slack_send_message', lambda line: {'channel_id': 'C1', 'text': f'Omer, {line}'}),
          ('mcp__slack__slack_send_message', lambda line: {'channel_id': 'C2', 'text': f'FYI <{line.split()[5].rstrip(",")}|thread>'}),
          ('mcp__github__add_issue_comment', lambda line: {'owner': 'acme', 'repo': 'app', 'issue_number': 7, 'body': line}),
          ('mcp__filesystem__write_file', lambda line: {'path': 'notes.md', 'content': line})]


@pytest.mark.parametrize('tool, fields', QUOTES, ids=['dm', 'channel', 'mrkdwn', 'github', 'write'])
@pytest.mark.parametrize('link', [IN_THREAD, 'https://x.slack.com/archives/C1/p1729580000000100?thread_ts=1729580000.000100&cid=C1'],
                         ids=['reply', 'root'])
def test_a_message_quoting_the_link_elsewhere_leaves_the_reply_open(root, fake, link, tool, fields):
    plan.owe(root, link, 'Omer asks about the rollout', 'Omer')
    line = next(r for r in board.compute(root) if r['item'] == 'R-1')['gaps'][0]['text']
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': tool, 'cwd': str(root),
                                      'tool_input': fields(line), 'tool_response': {'ok': True}})
    assert link in json.dumps(fields(line)) and plan.find(root, 'R-1')['status'] == 'open'


def test_a_send_naming_only_the_channel_of_a_top_level_link_neither_fails_nor_closes_it(root, fake):
    plan.owe(root, 'https://x.slack.com/archives/C1/p1729570000000100', 'an older question', 'Omer')
    plan.owe(root, IN_THREAD, 'Omer asks about the rollout', 'Omer')
    _send(root, channel_id='C1', thread_ts='1729580000.000100')
    assert [plan.find(root, i)['status'] for i in ('R-1', 'R-2')] == ['open', 'done']
    assert ws.rows(root, 'hook.error') == []


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
    quiet = next(r for r in board.compute(root) if r['item'] == 'I-1')['gaps']
    every = next(r for r in board.compute(root, everything=True) if r['item'] == 'I-1')['gaps']
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
    assert {r['item']: r['pr'] for r in board.compute(root) if r['item'] != 'team'} == {'A': 'acme/app#9', 'B': 'acme/app#9'}
    fake.prs['9'].update(state='MERGED', mergedAt=ws.now().isoformat(timespec='seconds'))
    ws.cache_put(root, 'prs-acme__app', None)
    board.compute(root)
    assert plan.find(root, 'A')['status'] == 'done' and plan.find(root, 'B')['status'] == 'done'


def test_a_run_item_stays_open_with_run_owed_when_its_pr_merges_until_plan_done(root, fake):
    from wuwei import __main__ as cli
    import os
    write_plan(root, [_item('R'), _item('B')])
    os.chdir(root)
    assert cli.main(['plan', 'run', 'R', '--reason', 'run: head none on production']) == 0
    fake.prs['9'] = make_pr(9, body='WUWEI-Item: R\nWUWEI-Item: B', state='MERGED')
    fake.prs['9']['mergedAt'] = ws.now().isoformat(timespec='seconds')
    rows = {r['item']: r for r in board.compute(root)}
    assert plan.find(root, 'R')['status'] == 'open' and plan.find(root, 'B')['status'] == 'done'
    assert rows['R']['gaps'][0]['text'] == 'run: run: head none on production; code merged as acme/app#9, run owed'
    board.compute(root)
    assert len([r for r in ws.rows(root, 'item.open') if 'run owed' in r['data']['reason']]) == 1
    assert cli.main(['plan', 'done', 'R', '--reason', 'run: head live in production']) == 0
    assert plan.find(root, 'R')['status'] == 'done'


def test_a_run_item_with_a_merged_and_an_open_pr_keeps_its_run_evidence(root, fake):
    from wuwei import __main__ as cli
    import os
    write_plan(root, [_item('R')])
    os.chdir(root)
    assert cli.main(['plan', 'run', 'R', '--reason', 'run: head none on production']) == 0
    fake.prs['9'] = make_pr(9, body='WUWEI-Item: R', state='MERGED')
    fake.prs['9']['mergedAt'] = ws.now().isoformat(timespec='seconds')
    fake.prs['10'] = make_pr(10, body='WUWEI-Item: R')
    assert [r['pr'] for r in board.compute(root) if r['item'] == 'R'] == ['acme/app#10']
    assert plan.find(root, 'R')['reason'] == 'run: head none on production'


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
    assert {r['item']: r['pr'] for r in board.compute(root) if r['item'] != 'team'} == {'A': 'acme/app#5', 'B': None}
    fake.prs['5'].update(state='MERGED', mergedAt=ws.now().isoformat(timespec='seconds'))
    ws.cache_put(root, 'prs-acme__app', None)
    board.compute(root)
    assert plan.find(root, 'A')['status'] == 'done' and plan.find(root, 'B')['status'] == 'open'


def test_a_footerless_pr_links_through_the_plan_prs_list(root, fake):
    write_plan(root, [_item('A', prs=['acme/app#6']), _item('B')])
    fake.prs['6'] = {**make_pr(6, body=''), 'headRefName': 'unrelated'}
    assert {r['item']: r['pr'] for r in board.compute(root) if r['item'] != 'team'} == {'A': 'acme/app#6', 'B': None}


SHEPHERD = 'orchestration: open PRs with no shepherd seat running'
GATES = 'orchestration: gates owed on green heads with no gate seat running'


def open_prs(root, fake, count=3, rollup=None):
    """count open PRs, each owing its quality gate at its own head, CI green unless rollup says otherwise."""
    write_plan(root, [{'id': f'I-{n}', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open'}
                      for n in range(1, count + 1)])
    for n in range(1, count + 1):
        fake.prs[str(40 + n)] = make_pr(number=40 + n, head=f'{n}' * 40, body=f'WUWEI-Item: I-{n}')
        fake.prs[str(40 + n)]['statusCheckRollup'] = rollup or fake.prs[str(40 + n)]['statusCheckRollup']


def team(root):
    return [g['text'] for r in board.compute(root) if r['item'] == 'team' for g in r['gaps']]


def seat(root, role, session='s1', agent='a1', kind='seat.started'):
    ws.record(root, kind, {'role': role, 'agent': agent, 'session': session})


def test_open_prs_and_owed_gates_with_no_seat_running_show_one_team_row(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 's1')
    open_prs(root, fake)
    assert team(root) == [SHEPHERD, GATES]
    assert '- team seats: ' + SHEPHERD in board.text(board.compute(root), root)


def test_a_running_seat_in_this_session_clears_its_line(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 's1')
    open_prs(root, fake)
    seat(root, 'shepherd')
    assert team(root) == [GATES]
    seat(root, 'sentinel-quality', agent='a2')
    assert team(root) == []


def test_a_dead_stopped_or_unconfirmed_seat_never_counts_as_running(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 's2')
    open_prs(root, fake)
    now = ws.now()
    monkeypatch.setattr(ws, 'now', lambda: now - datetime.timedelta(hours=6, seconds=1))
    seat(root, 'shepherd', session='s1')  # a session that died without a stop, past the live bound
    monkeypatch.setattr(ws, 'now', lambda: now)
    seat(root, 'shepherd', session='s2', agent='a2')
    seat(root, 'shepherd', session='s2', agent='a2', kind='seat.stopped')
    seat(root, 'sentinel-quality', session='s1', agent='a3')
    seat(root, 'sentinel-quality', session='s1', agent='a3', kind='seat.unconfirmed')
    monkeypatch.setattr(ws, 'now', lambda: now - datetime.timedelta(days=1))
    seat(root, 'shepherd', session='s2', agent='a4')  # this session's seat from yesterday
    monkeypatch.setattr(ws, 'now', lambda: now)
    assert team(root) == [SHEPHERD, GATES]
    ws.record(root, 'seat.started', {'role': 'shepherd', 'agent': 'a5'})  # a launch whose payload named no session
    monkeypatch.delenv('CLAUDE_CODE_SESSION_ID')
    assert team(root) == [SHEPHERD, GATES]  # a seat with no session counts in no session


def test_two_open_prs_need_no_shepherd_line(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 's1')
    open_prs(root, fake, count=2)
    assert team(root) == [GATES]


def test_owed_gates_on_a_head_whose_ci_runs_or_fails_owe_no_gate_seat(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 's1')
    seat(root, 'shepherd')
    open_prs(root, fake, rollup=[{'name': 'test', 'conclusion': '', 'status': 'IN_PROGRESS'}])
    assert team(root) == []
    open_prs(root, fake, rollup=[{'name': 'test', 'conclusion': 'FAILURE', 'status': 'COMPLETED'}])
    assert team(root) == []


def test_owed_gates_on_a_green_head_missing_a_required_check_owe_no_gate_seat(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 's1')
    seat(root, 'shepherd')
    fake.protection['main'] = ['build']  # the base requires a check that never ran at the heads
    open_prs(root, fake)
    assert team(root) == []
    fake.protection['main'] = []
    ws.cache_prune(root, -1, 'required-*')  # the base's required checks are kept for PR_TTL
    assert team(root) == [GATES]


def test_a_team_line_is_a_duty_that_never_holds_a_merge(root):
    found = [evidence.gap(SHEPHERD), evidence.gap(GATES)]
    assert {g['kind'] for g in found} == {'duty'} and evidence.blocking(found) == [] and evidence.visible(found) == found


def _owe_pr(root, opened=None):
    plan.owe(root, 'acme/app#7', 'review ping for #7', 'Ana')
    if opened:
        rows = plan.items(root)
        rows[0]['opened'] = opened
        plan.save(root, rows)


def _listed(root):
    return any(r['item'] == 'R-1' for r in board.compute(root)) or any(r['item'] == 'R-1' for r in board.replies(root))


def test_an_owe_keyed_to_a_pr_closes_on_a_slack_send_that_names_the_pr(root, fake):
    _owe_pr(root)
    hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'mcp__slack__slack_send_message', 'cwd': str(root),
        'tool_input': {'channel_id': 'C0AD2QW0C4U', 'text': 'Review please: https://github.com/acme/app/pull/7'},
        'tool_response': {'ok': True}})
    assert not _listed(root)
    assert plan.find(root, 'R-1')['status'] == 'done'


def test_an_owe_keyed_to_a_pr_closes_on_a_send_recorded_by_another_session_or_wuwei_sent(root, fake, monkeypatch):
    from wuwei import __main__ as cli
    _owe_pr(root)
    monkeypatch.chdir(root)
    assert cli.main(['sent', 'acme/app#7', 'https://acme.slack.com/archives/C1/p1792392138932809']) == 0
    assert not _listed(root)
    assert 'acme/app#7' in plan.find(root, 'R-1')['reason']


def test_an_owe_keyed_to_a_pr_stays_open_on_an_earlier_send_or_another_pr(root, fake):
    ws.record(root, 'sent', {'tool': 'outside the session', 'refs': ['acme/app#7'], 'link': 'https://x/1'})
    _owe_pr(root, opened=(ws.now() + datetime.timedelta(minutes=1)).isoformat(timespec='seconds'))
    ws.record(root, 'sent', {'tool': 'outside the session', 'refs': ['acme/app#8'], 'link': 'https://x/2'})
    assert _listed(root)
    assert plan.find(root, 'R-1')['status'] == 'open'


def test_an_owe_keyed_to_a_pr_stays_open_on_a_later_send_naming_another_pr(root, fake):
    _owe_pr(root, opened=(ws.now() - datetime.timedelta(minutes=5)).isoformat(timespec='seconds'))
    ws.record(root, 'sent', {'tool': 'outside the session', 'refs': ['acme/app#8'], 'link': 'https://x/2'})
    assert _listed(root)
    assert plan.find(root, 'R-1')['status'] == 'open'


OPENED, BEFORE, AFTER = '2026-10-20T06:11:00+00:00', '2026-10-20T06:10:59Z', '2026-10-20T06:11:00Z'


def node(*comments):
    """An unresolved GraphQL review thread from (login, createdAt) pairs."""
    return {'isResolved': False, 'comments': {'nodes': [{'author': {'login': who}, 'createdAt': at} for who, at in comments]}}


def test_an_owe_keyed_to_a_pr_closes_when_every_unresolved_thread_ends_with_the_owners_reply(root, fake):
    _owe_pr(root, opened=OPENED)
    fake.threads['7'] = [node(('alice', BEFORE), ('owner', AFTER)), node(('owner', BEFORE), ('alice', AFTER))]
    assert _listed(root)
    fake.threads['7'][1] = node(('owner', BEFORE), ('alice', AFTER), ('owner', AFTER))
    assert not _listed(root)
    assert 'owner' in plan.find(root, 'R-1')['reason']


def test_an_owe_stays_open_while_a_thread_ends_with_an_owner_reply_older_than_the_owe(root, fake):
    _owe_pr(root, opened=OPENED)  # the ask is newer than every reply the owner gave on the PR
    fake.threads['7'] = [node(('alice', BEFORE), ('owner', AFTER)), node(('alice', BEFORE), ('owner', BEFORE))]
    assert _listed(root)
    fake.threads['7'][1] = node(('alice', BEFORE), ('owner', AFTER))
    assert not _listed(root)


def test_an_owe_on_the_ccr_route_reads_the_reply_time_there(root, fake):
    fake.graphql = False
    _owe_pr(root, opened=OPENED)
    fake.ccr['7'] = [{'is_resolved': False, 'comments': [{'user': {'login': 'owner'}, 'created_at': BEFORE}]}]
    assert _listed(root)
    fake.ccr['7'][0]['comments'].append({'user': {'login': 'owner'}, 'created_at': AFTER})
    assert not _listed(root)


def test_an_owe_naming_two_prs_stays_open_while_either_waits_on_the_owner(root, fake):
    plan.owe(root, 'acme/app#7 and acme/app#8', 'replies on both', 'Ana')
    rows = plan.items(root)
    rows[0]['opened'] = OPENED
    plan.save(root, rows)
    fake.threads['7'] = [node(('alice', BEFORE), ('owner', AFTER))]
    fake.threads['8'] = [node(('owner', BEFORE), ('alice', AFTER))]
    assert _listed(root)
    fake.threads['8'] = [node(('owner', BEFORE), ('alice', AFTER), ('owner', AFTER))]
    assert not _listed(root)


def test_an_owe_keyed_to_a_pr_stays_open_when_its_threads_are_unreadable(root, fake, monkeypatch):
    _owe_pr(root)
    fake.threads['7'] = [{'isResolved': False, 'comments': {'nodes': [{'author': {'login': 'owner'}}]}}]

    def down(args, timeout=30):
        raise gh.GhError('HTTP 502: Bad Gateway')
    monkeypatch.setattr(gh, 'run', down)
    assert [r['item'] for r in board.replies(root)] == ['R-1']


def test_an_item_naming_an_open_pr_without_its_link_says_so(root, fake):
    write_plan(root, [_item('T', title='take over acme/app#7', approved=True), _item('U', promise='finish #8', approved=True),
                      _item('V', title='take over acme/app#9', approved=True)])
    fake.prs['7'] = make_pr(7, body='by another author')
    fake.prs['8'] = make_pr(8, body='by another author')
    fake.prs['9'] = make_pr(9, body='', state='CLOSED')
    gaps = {r['item']: r['gaps'][0]['text'] for r in board.compute(root) if r['item'] in 'TUV'}
    assert gaps == {'T': 'PR acme/app#7 not linked: add the WUWEI footer naming T',
                    'U': 'PR acme/app#8 not linked: add the WUWEI footer naming U', 'V': 'no pull request yet'}


def test_plan_add_with_pr_links_a_taken_over_pr(root, fake, monkeypatch):
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    fake.prs['7'] = make_pr(7, body='by another author')
    assert cli.main(['plan', 'add', 'T', 'take over', '--goal', 'G-1', '--repo', 'acme/app', '--pr', 'acme/app#7',
                     '--value', '3', '--time', '3', '--risk', '3', '--size', '3']) == 0
    assert plan.find(root, 'T')['prs'] == ['acme/app#7']
    assert next(r for r in board.compute(root) if r['item'] == 'T')['pr'] == 'acme/app#7'


def test_an_item_naming_another_items_open_pr_gets_no_not_linked_line(root, fake):
    write_plan(root, [_item('A', promise='start after #9', approved=True), _item('B')])
    fake.prs['9'] = make_pr(9, body='WUWEI-Item: B')
    assert next(r for r in board.compute(root) if r['item'] == 'A')['gaps'][0]['text'] == 'no pull request yet'


def _add(*extra):
    from wuwei import __main__ as cli
    return cli.main(['plan', 'add', 'T', 'take over', '--goal', 'G-1', '--repo', 'acme/app',
                     '--value', '3', '--time', '3', '--risk', '3', '--size', '3', *extra])


def test_plan_add_refuses_a_pr_that_is_not_owner_repo_number(root, fake, monkeypatch):
    import pytest
    monkeypatch.chdir(root)
    for bad in ('7', 'foo', 'acme/app#x'):
        with pytest.raises(SystemExit, match='name the PR as owner/repo#number'):
            _add('--pr', bad)
        assert plan.find(root, 'T') is None


def test_plan_add_keeps_and_merges_recorded_prs_and_matches_the_repo_case(root, fake, monkeypatch):
    monkeypatch.chdir(root)
    _add('--pr', 'Acme/App#7')
    _add('--promise', 'new contract')
    _add('--pr', 'acme/app#8')
    assert plan.find(root, 'T')['prs'] == ['acme/app#7', 'acme/app#8']


def launch(root, session, prompt, agent=None, role='builder'):
    """A builder launch in session: its PreToolUse decision, then (when agent names one) the seat it starts."""
    data = {'subagent_type': f'wuwei:{role}', 'description': 'build', 'prompt': prompt}
    out = hook.handle(root, 'PreToolUse', {'session_id': session, 'tool_name': 'Agent', 'cwd': str(root), 'tool_input': data})
    if agent and not refused(out):  # an accepted launch only
        hook.handle(root, 'PostToolUse', {'session_id': session, 'tool_name': 'Agent', 'cwd': str(root), 'tool_input': data,
                                          'tool_response': {'agentId': agent}})
    return out


def refused(out):
    return out['hookSpecificOutput']['permissionDecisionReason'] if out and out['hookSpecificOutput'].get('permissionDecision') == 'deny' else None


def test_a_live_seat_in_another_session_shows_on_the_board_and_counts_for_the_team_row(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 'B')
    open_prs(root, fake)
    launch(root, 'A', 'Item: i-2\nBuild it.', agent='b1')
    seat(root, 'shepherd', session='A', agent='sh1')
    assert team(root) == [GATES]
    rows = [r for r in board.compute(root) if r['item'] == 'I-2']
    assert [g['text'] for r in rows for g in r['gaps'] if 'running' in g['text']] == ['builder running in session A']
    assert '- I-2 c (acme/app#42): ' in (text := board.text(board.compute(root), root)) and 'builder running in session A [waiting]' in text
    assert not [g for r in board.compute(root) if r['item'] != 'I-2' for g in r['gaps'] if 'running in session' in g['text']]


def test_a_seat_past_the_live_bound_no_longer_counts_in_any_session(root, fake, monkeypatch):
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 'B')
    open_prs(root, fake)
    now = ws.now()
    monkeypatch.setattr(ws, 'now', lambda: now - datetime.timedelta(hours=6, minutes=1))
    seat(root, 'shepherd', session='A', agent='old')
    launch(root, 'A', 'Item: I-2', agent='b-old')
    monkeypatch.setattr(ws, 'now', lambda: now - datetime.timedelta(hours=6, minutes=-1))
    seat(root, 'sentinel-quality', session='A', agent='young')
    monkeypatch.setattr(ws, 'now', lambda: now)
    assert team(root) == [SHEPHERD] and [s['agent'] for s in board.running(root)] == ['young']
    assert refused(launch(root, 'B', 'Item: I-2')) is None


def test_a_launch_for_an_item_another_live_session_holds_is_sent_back_naming_it(root, fake):
    open_prs(root, fake)
    launch(root, 'A', 'Model: claude-opus-5-5 high\nItem: `I-1`.\nBuild it.', agent='b1')
    reason = refused(launch(root, 'B', 'Item: I-1\nBuild it.'))
    assert 'I-1' in reason and 'session A' in reason and 'b1' in reason
    assert refused(launch(root, 'B', 'Item: i-1', role='sentinel-quality'))  # the plan reads ids without case
    assert ws.rows(root, 'refused')[-1]['data']['session'] == 'B'
    assert refused(launch(root, 'A', 'Item: I-1\nBuild the next part.')) is None  # the holding session itself
    hook.handle(root, 'SubagentStop', launched({'session_id': 'A', 'agent_id': 'b1', 'agent_type': 'wuwei:builder',
                                                'last_assistant_message': 'done', 'cwd': str(root)}))
    assert refused(launch(root, 'B', 'Item: I-1\nBuild it.')) is None  # stopped: free again


@pytest.mark.parametrize('prompt, sent_back', [
    ('Item: I-10\nBuild it.', False),  # I-1 is a prefix of I-10: a different item
    ('Item: I-1x', False), ('Item: I', False),
    ('Item: I-2\nThe brief in session A said `Item: I-1`; leave it alone.', False),  # a quote after the brief's own line
    ('The brief in session A said `Item: I-1`.\nItem: I-2\nBuild it.', False),  # a quote before the brief's own line
    ('> Item: I-1\nItem: I-2', False),  # a quoted line
    ('Item: I-2\nItem: I-1', False),  # two lines: the first names the item, as the seat records it
    ('Item: I-1\nItem: I-2', True), ('  Item: I-1', True), ('Build Item: `I-1`, then stop.', True),
    ('Item:I-1.', True), ('Item: I-1 in acme/app.', True), ('Model: x\nItem: I-1', True),
    ('The brief in session A said `Item: I-1`.\n- Item: I-2', False), ('Done: `Item: I-1`.\n**Item:** I-2', False),  # list and bold lines
    ('- Item: I-1', True), ('* Item: I-1', True), ('**Item:** I-1', True), ('**Item: I-1**', True)])
def test_a_brief_that_quotes_or_wraps_another_items_line_is_judged_by_its_own_item(root, fake, prompt, sent_back):
    open_prs(root, fake, count=3)
    write_plan(root, [{'id': i, 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open'}
                      for i in ('I-1', 'I-10', 'I-1x', 'I', 'I-2')])
    launch(root, 'A', 'Item: I-1', agent='b1')
    assert bool(refused(launch(root, 'B', prompt, agent='b2'))) is sent_back
    held = [s['item'] for s in board.running(root) if s['session'] == 'B']
    assert held == ([] if sent_back else [hook.asked({'prompt': prompt})[0]])


def test_a_seat_recorded_without_a_session_holds_nothing(root, fake):
    open_prs(root, fake)
    ws.record(root, 'seat.started', {'role': 'builder', 'agent': 'x1', 'item': 'I-1'})
    ws.record(root, 'seat.started', {'role': 'builder', 'agent': 'x2', 'item': 'I-1', 'session': ''})
    assert refused(launch(root, 'B', 'Item: I-1')) is None and board.running(root) == []
