import json

from conftest import HEAD, make_pr, verdict_text, write_plan
from wuwei import board, evidence, hook, plan, ws


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


def test_pre_tool_deny_holds_when_the_last_ledger_line_is_not_a_row(root):
    path = root / ws.DIR / 'ledger' / f'{ws.clone(root)}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[1]\n')
    out = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': 'Write', 'cwd': str(root),
                                           'tool_input': {'file_path': '.wuwei/ledger.jsonl'}})
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
    hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': 'Agent', 'cwd': str(root),
                                     'tool_input': {'subagent_type': 'wuwei:builder', 'prompt': 'Build I-1'}})
    assert stop(root) is None
    hook.handle(root, 'SubagentStop', {'session_id': 's1', 'agent_id': 'b1', 'agent_type': 'wuwei:builder',
                                       'last_assistant_message': 'done', 'cwd': str(root)})
    assert stop(root, session='s2')['decision'] == 'block'


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


def test_a_verdict_is_attested_from_the_handback_when_the_stop_could_not_read_it(root):
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    reviewer_stop(root, '', active=True, transcript='/nowhere/agent.jsonl')
    assert not ws.rows(root, 'attest')
    handback = {'session_id': 's1', 'cwd': str(root), 'tool_name': 'Agent',
                'tool_input': {'subagent_type': 'wuwei:sentinel-quality'},
                'tool_response': {'content': [{'type': 'text', 'text': 'Reviewed.\nVerdict file: .wuwei/verdicts/I-1/quality.md'}]}}
    hook.handle(root, 'PostToolUse', handback)
    hook.handle(root, 'PostToolUse', handback)
    assert [(r['data']['gate'], r['data']['verdict']) for r in ws.rows(root, 'attest')] == [('quality', 'PASS')]


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
