import json
from pathlib import Path
import re

import pytest

from conftest import HEAD, make_pr, verdict_text, write_plan
from wuwei import board, evidence, guards, hook, plan, verdict, ws


def plan_one(root, tier='light'):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': tier,
                       'status': 'open', 'score': 3}])


def stop(root, active=False, session='s1'):
    return hook.handle(root, 'Stop', {'session_id': session, 'stop_hook_active': active, 'cwd': str(root)})


def test_stop_reminds_once_per_set_of_open_gaps(root, fake):
    plan_one(root)
    fake.prs['42'] = make_pr(files=('src/app.py',))
    first = stop(root)
    assert first['decision'] == 'block'
    assert 'I-1' in first['reason'] and 'no test in the diff' in first['reason']
    assert stop(root) is None
    assert ws.rows(root, 'stop.reminded')


def test_stop_never_loops_and_lets_waits_end_the_turn(root, fake):
    plan_one(root)
    pr = make_pr()
    pr['statusCheckRollup'] = [{'name': 'test', 'conclusion': '', 'status': 'IN_PROGRESS'}]
    fake.prs['42'] = pr
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    import hashlib
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'item': 'I-1',
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    ws.record(root, 'watch.pass', {'summary': 'nothing changed'})
    assert stop(root) is None
    fake.prs['42'] = make_pr(files=('src/app.py',))
    ws.cache_put(root, 'board', None)
    assert stop(root, active=True) is None


def test_an_item_without_a_pr_is_open_work(root, fake):
    plan_one(root)
    assert 'I-1: no pull request yet' in stop(root)['reason']


def test_a_closed_day_stops_quietly_until_the_next_plan_pass(root, fake):
    plan_one(root)
    ws.record(root, 'day.closed', {})
    assert stop(root) is None
    ws.record(root, 'plan.pass', {})
    assert stop(root, session='s2')['decision'] == 'block'


def reviewer_stop(root, message, active=False, agent='rev1', transcript='/t/agent.jsonl'):
    return hook.handle(root, 'SubagentStop', {
        'session_id': 's1', 'agent_id': agent, 'agent_type': 'wuwei:sentinel-quality', 'stop_hook_active': active,
        'last_assistant_message': message, 'agent_transcript_path': transcript, 'cwd': str(root)})


def test_a_reviewer_must_name_its_verdict_file(root):
    assert 'Verdict file:' in reviewer_stop(root, 'Looks fine to me.')['reason']


def test_a_malformed_verdict_is_sent_back_with_the_format(root):
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text('Verdict: PASS\n')
    result = reviewer_stop(root, f'Done.\nVerdict file: {path}')
    assert result['decision'] == 'block' and 'Head:' in result['reason'] and '## Findings' in result['reason']
    assert not ws.rows(root, 'attest')


def test_a_good_verdict_is_attested_however_it_was_written(root, fake):
    plan_one(root)
    fake.prs['42'] = make_pr()
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    assert reviewer_stop(root, 'Reviewed.\nVerdict file: .wuwei/verdicts/I-1/quality.md') is None
    row = ws.rows(root, 'attest')[0]['data']
    assert (row['gate'], row['item'], row['head'], row['agent']) == ('quality', 'I-1', HEAD, 'rev1')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_a_verdict_for_another_gate_is_refused(root):
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'arch.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text(gate='arch'))
    assert 'sentinel-quality' in reviewer_stop(root, f'Verdict file: {path}')['reason']


def test_a_verdict_outside_the_workspace_is_refused(root, tmp_path_factory):
    other = tmp_path_factory.mktemp('elsewhere') / 'v.md'
    other.write_text(verdict_text())
    assert '.wuwei/verdicts' in reviewer_stop(root, f'Verdict file: {other}')['reason']


def test_a_reviewer_that_still_fails_after_a_reminder_is_let_go_and_recorded(root):
    assert reviewer_stop(root, 'no file', active=True) is None
    assert ws.rows(root, 'verdict.missing')


def test_post_tool_traces_without_secrets(root):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'Bash', 'cwd': str(root),
                                      'tool_input': {'command': 'echo ghp_' + 'a1' * 18},
                                      'tool_response': {'stdout': 'x'}})
    row = ws.traces(root)[0]
    assert row['tool'] == 'Bash' and 'ghp_' not in json.dumps(row)


def test_post_tool_trace_carries_the_seats_role(root):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'Read', 'cwd': str(root),
                                      'agent_type': 'wuwei:sentinel-quality', 'tool_input': {'file_path': 'a.py'}})
    assert ws.traces(root)[0]['role'] == 'sentinel-quality'


def test_pre_tool_marks_the_hook_seen_on_every_call(root):
    hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': 'Read', 'cwd': str(root), 'tool_input': {}})
    assert abs(ws.cache_get(root, 'hook-seen', 120) - ws.now().timestamp()) < 5


@pytest.mark.parametrize('tool, data, decision', [('mcp__slack__send_message', {'text': 'hi'}, None),
                                                   ('Write', {'file_path': '.wuwei/ledger.jsonl'}, 'deny')])
def test_a_failed_hook_seen_stamp_lets_the_guards_decide(root, monkeypatch, tool, data, decision):
    real = ws.cache_put
    monkeypatch.setattr(ws, 'cache_put', lambda root, name, value: 1 / 0 if name == 'hook-seen' else real(root, name, value))
    out = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': tool, 'cwd': str(root), 'tool_input': data})
    assert (out and out['hookSpecificOutput']['permissionDecision']) == decision
    assert not ws.rows(root, 'hook.error')


def test_post_tool_tells_what_a_new_pr_still_needs(root, fake):
    plan_one(root)
    fake.prs['42'] = make_pr(files=('src/app.py',))
    out = hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'Bash', 'cwd': str(root), 'tool_input': {'command': 'gh pr create --fill'},
        'tool_response': {'stdout': 'https://github.com/acme/app/pull/42\n'}})
    context = out['hookSpecificOutput']['additionalContext']
    assert 'acme/app#42' in context and 'no test in the diff' in context


def test_an_owner_answer_becomes_a_ruling(root):
    hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'AskUserQuestion', 'cwd': str(root),
        'tool_input': {'questions': [{'question': 'owner review: acme/app#42 at aaaaaaa. Merge it?'}]},
        'tool_response': {'answers': {'owner review: acme/app#42 at aaaaaaa. Merge it?': 'Yes'}}})
    assert ws.rows(root, 'ruling')[0]['data'] == {'pr': 'acme/app#42', 'head': 'aaaaaaa', 'approved': True,
                                                   'question': 'owner review: acme/app#42 at aaaaaaa. Merge it?',
                                                   'answer': 'Yes'}
    assert ws.rows(root, 'prompt')


def test_pre_tool_deny_uses_the_harness_shape_and_is_recorded(root):
    out = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': 'Write', 'cwd': str(root),
                                           'tool_input': {'file_path': '.wuwei/ledger.jsonl'}})
    assert out['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert ws.rows(root, 'refused')


@pytest.mark.parametrize('tool, data', [
    ('Write', {'file_path': '.wuwei/ledger.jsonl'}),
    ('AskUserQuestion', {'questions': [{'question': 'Want me to continue with I-2?', 'header': 'h', 'options': []}]})])
def test_pre_tool_deny_holds_when_the_last_ledger_line_is_not_a_row(root, tool, data):
    path = root / ws.DIR / 'ledger' / f'{ws.clone(root)}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[1]\n')
    out = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': tool, 'cwd': str(root), 'tool_input': data})
    assert out['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert ws.rows(root, 'refused') and not ws.rows(root, 'hook.error')


def test_session_start_orients_with_the_board(root, fake):
    plan_one(root)
    context = hook.handle(root, 'SessionStart', {'session_id': 's1', 'cwd': str(root)})['hookSpecificOutput']['additionalContext']
    assert 'WUWEI' in context and 'I-1' in context


def test_a_hook_error_fails_open(root, monkeypatch):
    monkeypatch.setattr(board, 'rows', lambda root: 1 / 0)
    assert stop(root) is None
    assert ws.rows(root, 'hook.error')


def test_the_stop_reminder_says_the_plan_is_the_mandate(root, fake):
    plan_one(root)
    assert 'do not ask the owner whether to continue' in stop(root)['reason']


def test_an_unreadable_code_host_is_a_waiting_gap_not_a_crash(root, monkeypatch):
    from wuwei import gh, report

    def down(args, timeout=30):
        raise gh.GhError('HTTP 403')
    monkeypatch.setattr(gh, 'run', down)
    plan_one(root)
    rows = board.compute(root)
    assert rows[0]['gaps'][0]['text'] == 'acme/app unreadable: HTTP 403' and not rows[0]['gaps'][0]['actionable']
    assert 'unmeasured' in report.day(root)


def answer(root, question, reply):
    return hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'tool_name': 'AskUserQuestion', 'cwd': str(root),
        'tool_input': {'questions': [{'question': question}]}, 'tool_response': {'answers': {question: reply}}})


def test_a_one_way_answer_asks_for_an_adr(root):
    out = answer(root, 'one-way: drop the legacy sessions table in acme/app?', 'Yes, drop it')
    assert 'ADR' in out['hookSpecificOutput']['additionalContext']


def test_an_accepted_exception_becomes_a_follow_up_item(root):
    plan_one(root)
    answer(root, 'exception: acme/app#42 at aaaaaaa: no test in the diff. Merge without a test?', 'Yes')
    ruling = ws.rows(root, 'ruling')[0]['data']
    assert (ruling['kind'], ruling['gap'], ruling['approved']) == ('exception', 'no test in the diff', True)
    follow = [i for i in plan.items(root) if i['id'].startswith('X-')]
    assert follow and 'acme/app#42' in follow[0]['title'] and follow[0]['goal'] == 'G-1'


def test_andon_holds_new_builds_in_one_repo(root, fake):
    plan_one(root)
    board.andon(root, 'acme/app', 'base branch red: test_login')
    gaps = board.compute(root)[0]['gaps']
    assert gaps[0]['text'].startswith('andon: base branch red') and not gaps[0]['actionable']
    assert 'ANDON acme/app' in board.text(board.compute(root), root)
    board.andon(root, 'acme/app', clear=True)
    assert board.compute(root)[0]['gaps'][0]['text'] == 'no pull request yet'


def test_seat_tokens_are_counted_from_the_transcript(root, tmp_path):
    transcript = tmp_path / 'agent.jsonl'
    transcript.write_text('\n'.join(json.dumps({'type': 'assistant', 'message': {
        'content': [{'type': 'text', 'text': 'done'}], 'usage': {'input_tokens': n, 'output_tokens': 10}}})
        for n in (100, 200)))
    hook.handle(root, 'SubagentStop', {'session_id': 's1', 'agent_id': 'b1', 'agent_type': 'wuwei:builder',
                                       'agent_transcript_path': str(transcript), 'last_assistant_message': 'ok',
                                       'cwd': str(root)})
    assert ws.rows(root, 'seat.stopped')[0]['data']['tokens'] == 320


def test_session_start_names_the_cli_and_refreshes_the_pointer(root, fake):
    plan_one(root)
    context = hook.handle(root, 'SessionStart', {'session_id': 's1', 'cwd': str(root)})['hookSpecificOutput']['additionalContext']
    cli = str(hook.PLUGIN / 'bin' / 'wuwei')
    assert f'WUWEI CLI: {cli}' in context
    assert (root / ws.DIR / 'executable').read_text().strip() == cli


def test_process_gaps_never_hold_the_turn(root, fake):
    plan_one(root)
    fake.prs['42'] = make_pr(lines=300, requests=())
    import hashlib
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'item': 'I-1',
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    ws.record(root, 'watch.pass', {'summary': 'nothing changed'})
    assert stop(root) is None
    assert 'changed lines' not in board.text(board.compute(root), root)


def test_an_exception_over_two_prs_records_both(root):
    plan_one(root)
    answer(root, 'exception: acme/app#43 at e750645 and #44 at 237e183: gates missing at head e750645: security. '
                 'Accept for the hotfix?', 'Accept')
    rulings = [r['data'] for r in ws.rows(root, 'ruling')]
    assert [(r['pr'], r['head']) for r in rulings] == [('acme/app#43', 'e750645'), ('acme/app#44', '237e183')]
    assert all(r['gap'] == 'gates missing at head e750645: security' for r in rulings)


def test_stop_stays_quiet_while_a_seat_is_running(root, fake):
    plan_one(root)
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'Agent', 'cwd': str(root),
                                      'tool_input': {'subagent_type': 'wuwei:builder', 'prompt': 'Build I-1'},
                                      'tool_response': {'agentId': 'b1'}})
    assert stop(root) is None
    hook.handle(root, 'SubagentStop', {'session_id': 's1', 'agent_id': 'b1', 'agent_type': 'wuwei:builder',
                                       'last_assistant_message': 'done', 'cwd': str(root)})
    assert stop(root, session='s2')['decision'] == 'block'


def test_a_rejected_agent_launch_records_no_seat(root):
    assert pre(root, 'Agent', {'subagent_type': 'wuwei:nobody', 'prompt': 'Build I-1'}) is None
    assert ws.rows(root, 'seat.started') == []


def test_an_accepted_launch_records_its_seat_with_the_agent_id(root):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'Agent', 'cwd': str(root),
                                      'tool_input': {'subagent_type': 'wuwei:builder', 'description': 'build I-1',
                                                     'run_in_background': True},
                                      'tool_response': {'status': 'async_launched', 'agentId': 'a1'}})
    [row] = ws.rows(root, 'seat.started')
    assert (row['data']['agent'], row['data']['role'], row['data']['description']) == ('a1', 'builder', 'build I-1')


@pytest.mark.parametrize('tool, response', [('Agent', {'status': 'completed'}), ('Agent', {'agentId': ['a1']}),
                                            ('Task', {'agentId': ''}), ('Agent', 'launched a1'),
                                            ('Bash', {'agentId': 'a1'})])
def test_only_an_agent_launch_with_a_string_id_records_a_seat(root, tool, response):
    assert hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': tool, 'cwd': str(root),
                                             'tool_input': {'subagent_type': 'wuwei:builder'},
                                             'tool_response': response}) is None
    assert ws.rows(root, 'seat.started') == [] and ws.rows(root, 'hook.error') == []
    assert hook.running(root) == 0


def test_running_skips_rows_without_a_string_agent_id(root):
    ws.record(root, 'seat.started', {'role': 'builder'})
    ws.record(root, 'seat.started', {'role': 'builder', 'agent': ['a1']})
    ws.record(root, 'seat.stopped', {'role': 'builder', 'agent': ['a1']})
    assert hook.running(root) == 0


def test_running_counts_seats_by_agent_id_not_rows(root):
    for _ in range(3):
        ws.record(root, 'seat.started', {'role': 'builder', 'agent': 'a1'})
        ws.record(root, 'seat.stopped', {'role': 'builder', 'agent': 'a1'})
    ws.record(root, 'seat.stopped', {'role': 'builder', 'agent': 'a1'})
    ws.record(root, 'seat.started', {'role': 'planner', 'agent': 'a2'})
    assert hook.running(root) == 1


def test_stop_lists_at_most_ten_lines_and_says_what_it_left_out(root, fake):
    from conftest import write_plan as plan_rows
    plan_rows(root, [{'id': f'I-{n}', 'title': 't', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
                      'status': 'open', 'score': 1} for n in range(14)])
    reason = stop(root)['reason']
    assert reason.count('\n- ') == 10 and 'and 4 more' in reason


def test_a_seat_that_replaces_another_seats_verdict_is_sent_back(root):
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality-aaaaaaa.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text(verdict='FIX', findings='- [high] src/app.py:9 blocks: yes. Failure: two retries reorder the queue'))
    assert reviewer_stop(root, 'Verdict file: .wuwei/verdicts/I-1/quality-aaaaaaa.md', agent='rev0') is None
    path.write_text(verdict_text())
    result = reviewer_stop(root, 'Verdict file: .wuwei/verdicts/I-1/quality-aaaaaaa.md', agent='rev1')
    assert result['decision'] == 'block' and 'quality-aaaaaaa-2.md' in result['reason']
    assert [r['data']['verdict'] for r in ws.rows(root, 'attest')] == ['FIX']
    path.write_text(verdict_text())  # the same seat rewriting its own verdict is fine
    assert reviewer_stop(root, 'Verdict file: .wuwei/verdicts/I-1/quality-aaaaaaa.md', agent='rev1') is not None
    path.write_text(verdict_text(verdict='FIX', findings='- [high] src/app.py:9 blocks: yes. Failure: two retries reorder the queue'))
    assert reviewer_stop(root, 'Verdict file: .wuwei/verdicts/I-1/quality-aaaaaaa.md', agent='rev0') is None


VERDICT_1067 = '.wuwei/verdicts/1067/quality-3fb3f40.md'


def write_verdict(root, text, rel=VERDICT_1067):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def handback(root, message, agent_type='wuwei:sentinel-quality', agent='rev1'):
    return hook.handle(root, 'PreToolUse', {'session_id': 's1', 'agent_id': agent, 'agent_type': agent_type,
                                           'cwd': str(root), 'tool_name': 'SubagentHandback',
                                           'tool_input': {'message': message}})


def test_a_malformed_verdict_denies_the_handback_with_its_shape_errors(root):
    write_verdict(root, verdict_text(verdict='FIX', findings='- [high] the retry loop never ends'))
    out = handback(root, f'Reviewed.\nVerdict file: {VERDICT_1067}')['hookSpecificOutput']
    assert out['permissionDecision'] == 'deny'
    assert 'the retry loop never ends' in out['permissionDecisionReason'] and verdict.FORMAT in out['permissionDecisionReason']
    assert not ws.rows(root, 'attest')


def test_a_well_formed_verdict_is_attested_once_at_the_handback(root, tmp_path):
    write_verdict(root, verdict_text())
    message = f'Reviewed.\nVerdict file: {VERDICT_1067}'
    assert handback(root, message) is None and len(ws.rows(root, 'attest')) == 1
    transcript = tmp_path / 'agent.jsonl'
    transcript.write_text(json.dumps({'type': 'assistant', 'message': {'content': [
        {'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': message}}]}}) + '\n')
    assert reviewer_stop(root, '', transcript=str(transcript)) is None
    assert [(r['data']['path'], r['data']['gate']) for r in ws.rows(root, 'attest')] == [(VERDICT_1067, 'quality')]


@pytest.mark.parametrize('agent_type', ['wuwei:builder', 'wuwei:sentinel-arch', ''])
def test_only_the_gates_own_seat_attests_at_the_handback(root, agent_type):
    write_verdict(root, verdict_text())
    out = handback(root, f'Verdict file: {VERDICT_1067}', agent_type=agent_type)
    assert not ws.rows(root, 'attest')
    assert (out is not None) == ('sentinel' in agent_type)  # another seat's hand-back is not linted


def test_a_problem_found_after_the_handback_ended_the_run_is_recorded(root, tmp_path):
    write_verdict(root, verdict_text(verdict='FIX', findings='- [high] the retry loop never ends'))
    transcript = tmp_path / 'agent.jsonl'
    transcript.write_text(json.dumps({'type': 'assistant', 'message': {'content': [
        {'type': 'tool_use', 'name': 'SubagentHandback', 'input': {'message': f'Verdict file: {VERDICT_1067}'}}]}}) + '\n')
    assert reviewer_stop(root, '', transcript=str(transcript)) is None
    assert 'does not hold its shape' in ws.rows(root, 'verdict.missing')[0]['data']['problem']


def seat_stop(root, message='', active=False, transcript='/nowhere/agent.jsonl'):
    return hook.handle(root, 'SubagentStop', {'session_id': 's1', 'agent_id': 'b1', 'agent_type': 'wuwei:builder',
                                              'stop_hook_active': active, 'last_assistant_message': message,
                                              'agent_transcript_path': transcript, 'cwd': str(root)})


def test_a_seat_that_ends_silent_is_asked_for_its_report_in_plain_text(root):
    assert 'plain text' in seat_stop(root)['reason']
    assert seat_stop(root, active=True) is None and ws.rows(root, 'seat.silent')
    assert seat_stop(root, 'Built it; tests pass.\nBlocked: none') is None


def test_a_report_written_just_after_the_stop_is_still_read(root, tmp_path):
    import threading
    transcript = tmp_path / 'agent.jsonl'
    transcript.write_text('')
    row = {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Built it.\nBlocked: none'}]}}
    threading.Timer(0.3, lambda: transcript.write_text(json.dumps(row) + '\n')).start()
    assert seat_stop(root, transcript=str(transcript)) is None


def test_the_flat_verdict_path_is_accepted_too(root):
    path = root / ws.DIR / 'verdicts' / 'I-1-quality-aaaaaaa.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    assert reviewer_stop(root, 'Verdict file: .wuwei/verdicts/I-1-quality-aaaaaaa.md') is None
    assert ws.rows(root, 'attest')


def test_waiting_work_with_no_watch_armed_asks_once_to_arm_it(root, fake):
    plan_one(root)
    pr = make_pr()
    pr['statusCheckRollup'] = [{'name': 'test', 'conclusion': '', 'status': 'IN_PROGRESS'}]
    fake.prs['42'] = pr
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    import hashlib
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'item': 'I-1',
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    assert 'arm /wuwei-watch' in stop(root)['reason']
    assert stop(root) is None


def test_an_empty_queue_with_goals_asks_once_for_a_plan_pass(root, fake):
    assert stop(root) is None
    (root / ws.DIR / 'goals.md').write_text('G-1: ship the grant flow\n')
    assert 'run a plan pass from the goals' in stop(root, session='s2')['reason']
    assert stop(root, session='s2') is None


def test_an_unreadable_command_after_it_ran_is_no_hook_error(root):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'Bash', 'cwd': str(root),
                                      'tool_input': {'command': "echo it's\nls"}, 'tool_response': {'stdout': 'x'}})
    assert not ws.rows(root, 'hook.error')


def pre(root, tool, data):
    return hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': tool, 'cwd': str(root), 'tool_input': data})


def test_a_merge_door_that_cannot_write_its_cache_refuses_and_names_the_error(root, fake, monkeypatch):
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'acme/app')
    fake.prs['5'] = make_pr(5)
    (root / ws.DIR / 'cache' / 'template-acme__app.json').mkdir(parents=True)
    out = pre(root, 'Bash', {'command': 'gh pr merge 5'})['hookSpecificOutput']
    assert out['permissionDecision'] == 'deny'
    assert 'IsADirectoryError' in out['permissionDecisionReason']
    assert ws.rows(root, 'hook.error')


@pytest.mark.parametrize('tool, data, decision', [
    ('AskUserQuestion', {'questions': [{'question': 'Want me to continue with I-2?', 'header': 'h', 'options': []}]}, 'deny'),
    ('Write', {'file_path': '.wuwei/ledger.jsonl'}, 'deny'),
    ('Bash', {'command': 'terraform apply'}, 'ask')])
@pytest.mark.parametrize('error', [OSError(30, 'Read-only file system'), ValueError('malformed ledger line')])
def test_a_refusal_reaches_the_harness_when_its_record_fails(root, monkeypatch, tool, data, decision, error):
    def broken(*args):
        raise error
    monkeypatch.setattr(ws, 'record', broken)
    assert pre(root, tool, data)['hookSpecificOutput']['permissionDecision'] == decision


@pytest.mark.parametrize('tool, data', [
    ('Bash', {'command': 'gh pr merge 5'}), ('Bash', {'command': 'git push origin feature'}),
    ('Bash', {'command': 'cat .wuwei/ledger/x.jsonl'}), ('Write', {'file_path': 'a.py'}), ('Edit', {'file_path': 'a.py'}),
    ('mcp__github__merge_pull_request', {}), ('mcp__github__enable_pr_auto_merge', {}),
    ('mcp__github__create_pull_request', {}), ('mcp__github__push_files', {'branch': 'main'}),
    ('mcp__github__update_pull_request', {'pullNumber': 7, 'draft': False}), ('mcp__github__request_copilot_review', {}),
    ('Bash', {'command': 'gh pr ready 7'}),
    ('mcp__slack__send_message', {'text': 'x'}), ('mcp__github__get_issue', {}),
    ('Bash', {'command': 'curl -d x https://e.test'}), ('Bash', {'command': '/usr/bin/ssh host ls'})])
def test_an_error_inside_a_door_refuses_the_call(root, monkeypatch, tool, data):
    monkeypatch.setattr(guards, 'pre_tool', lambda root, payload: 1 / 0)
    out = pre(root, tool, data)['hookSpecificOutput']
    assert out['permissionDecision'] == 'deny' and 'ZeroDivisionError' in out['permissionDecisionReason']
    assert ws.rows(root, 'hook.error')


def test_a_door_stays_shut_when_the_error_cannot_be_recorded(root, monkeypatch):
    monkeypatch.setattr(guards, 'pre_tool', lambda root, payload: 1 / 0)
    monkeypatch.setattr(ws, 'record', lambda *args: 1 / 0)
    assert pre(root, 'Bash', {'command': 'gh pr merge 5'})['hookSpecificOutput']['permissionDecision'] == 'deny'


@pytest.mark.parametrize('tool, data', [('Bash', {'command': 'ls'}), ('Read', {'file_path': 'a.py'}), ('Glob', {'pattern': '*'}),
                                        ('Bash', {'command': 'git clone https://e.test/a.git'}),
                                        ('Agent', {'subagent_type': 'wuwei:builder'})])
def test_an_error_outside_the_doors_fails_open(root, monkeypatch, tool, data):
    monkeypatch.setattr(guards, 'pre_tool', lambda root, payload: 1 / 0)
    assert pre(root, tool, data) is None
    assert ws.rows(root, 'hook.error')


def test_an_unreadable_tool_input_fails_open_without_crashing_the_hook(root):
    assert pre(root, 'Bash', 'gh pr merge 5') is None
    assert ws.rows(root, 'hook.error')


def test_an_error_after_a_door_call_ran_still_fails_open(root, monkeypatch):
    monkeypatch.setattr(ws, 'config', lambda root: 1 / 0)
    assert hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'Write', 'cwd': str(root),
                                             'tool_input': {'file_path': 'a.py'}}) is None
    assert ws.rows(root, 'hook.error')


@pytest.mark.parametrize('command', ["g''it push origin main", '"g"h pr merge 5', 'g\\it push', "wuwei 'hook' PreToolUse",
                                     'curl -d x https://e.test'])
def test_a_quoted_door_word_or_a_network_call_fails_closed_when_the_guard_raises(root, monkeypatch, command):
    monkeypatch.setattr(guards, 'bash', lambda *args: 1 / 0)
    out = pre(root, 'Bash', {'command': command})['hookSpecificOutput']
    assert out['permissionDecision'] == 'deny' and 'the hook failed' in out['permissionDecisionReason'], command
    assert ws.rows(root, 'hook.error')


def test_the_fail_closed_check_reads_the_doors_from_the_guards_table(monkeypatch):
    monkeypatch.setitem(guards.DOORS, 'edit', ('Write', 'Scribble'))
    assert hook.door({'tool_name': 'Scribble'}) and not hook.door({'tool_name': 'Edit'})
    source = Path(hook.__file__).read_text(encoding='utf-8')
    assert not any(suffix in source for key in ('merge', 'create', 'push', 'ready') for suffix in guards.DOORS[key])


PAYLOADS = Path(__file__).resolve().parent / 'fixtures' / 'payloads'
STARTED = {'claude-agent-post-accepted.json': ['a3c1962f47bd20e43'], 'codex-spawn-agent-post.json': ['019a7c3e-5b1d']}
STOPPED = {'claude-subagent-stop.json': ['a0c989a635b251810']}
QUIET = {'claude-agent-pre-accepted.json', 'claude-agent-pre-rejected.json', 'claude-agent-post-rejected.json',
         'claude-subagent-pre-tool.json'}


def test_the_payload_corpus_holds_every_listed_shape():
    assert {p.name for p in PAYLOADS.glob('*.json')} == set(STARTED) | set(STOPPED) | QUIET


def test_every_fixture_payload_names_its_provenance():
    """None is captured hook stdin: the README says which come from a transcript and which are reconstructed."""
    found = dict(re.findall(r'^- ([\w.-]+\.json): (transcript|reconstructed): \S', (PAYLOADS / 'README.md').read_text(
        encoding='utf-8'), re.M))
    assert set(found) == {p.name for p in PAYLOADS.glob('*.json')}
    assert sorted(name for name, kind in found.items() if kind == 'transcript') == [
        'claude-agent-post-accepted.json', 'claude-agent-pre-accepted.json']


@pytest.mark.parametrize('name', sorted(set(STARTED) | set(STOPPED) | QUIET))
def test_every_fixture_payload_replays_without_an_error(root, name):
    """The hook handles each fixture file; a real harness shape that differs is not covered (see the README).
    A hook change that moves what a payload records edits this table or the payload, so its diff shows it."""
    payload = json.loads((PAYLOADS / name).read_text(encoding='utf-8'))
    assert hook.handle(root, payload['hook_event_name'], payload) is None
    assert ws.rows(root, 'hook.error') == []
    assert [row['data']['agent'] for row in ws.rows(root, 'seat.started')] == STARTED.get(name, [])
    assert [row['data']['agent'] for row in ws.rows(root, 'seat.stopped')] == STOPPED.get(name, [])


def test_a_changed_open_work_list_names_only_what_changed(root, fake):
    from conftest import write_plan as plan_rows
    items = [{'id': f'I-{n}', 'title': 't', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open',
              'score': 1} for n in range(3)]
    plan_rows(root, items)
    assert stop(root)['reason'].count('\n- ') == 3
    plan_rows(root, items + [dict(items[0], id='I-9')])
    ws.cache_put(root, 'board', None)
    reason = stop(root)['reason']
    assert reason.count('\n- ') == 1 and 'I-9: no pull request yet' in reason
    assert '3 more unchanged since' in reason
    plan_rows(root, items[:2])
    ws.cache_put(root, 'board', None)
    assert stop(root) is None  # only closed work: nothing new to act on


def test_a_verdict_written_in_a_worktree_is_copied_into_the_workspace_and_attested(root, tmp_path_factory):
    written = tmp_path_factory.mktemp('wt') / '.wuwei' / 'verdicts' / 'I-1' / 'quality-aaaaaaa.md'
    written.parent.mkdir(parents=True)
    written.write_text(verdict_text())
    assert reviewer_stop(root, f'Verdict file: {written}') is None
    copy = root / ws.DIR / 'verdicts' / 'I-1' / 'quality-aaaaaaa.md'
    assert copy.read_bytes() == written.read_bytes()
    assert ws.rows(root, 'attest')[0]['data']['path'] == '.wuwei/verdicts/I-1/quality-aaaaaaa.md'


def test_a_missing_verdict_names_the_absolute_folder_it_belongs_in(root):
    reason = reviewer_stop(root, 'Verdict file: .wuwei/verdicts/I-1/quality-aaaaaaa.md')['reason']
    assert str((root / ws.DIR / 'verdicts').resolve()) in reason
