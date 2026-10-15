"""The plan as a view to approve (#990): one picture, one short question."""

from wuwei import board, hook, plan, view, ws


def scores(value=8, time=5, risk=3, size=2):
    return {'value': value, 'time': time, 'risk': risk, 'size': size}


def setup_plan(root):
    (root / ws.DIR / 'goals.md').write_text('## G-1\nOutcome: Login is safe under load\nDate: 2026-10-31\n\n'
                                            '## G-2\noutcome: Faster imports\n')
    plan.add(root, 'I-1', 'Rate limits <for> login', 'G-1', 'acme/app', 'standard', scores(size=3))
    plan.add(root, 'I-2', 'Retry policy', 'G-2', 'acme/app', 'light', scores(size=1))
    plan.add(root, 'I-3', 'Docs cleanup', 'unplanned', 'acme/app', 'light', scores(value=1, size=2))


def test_the_view_shows_framework_hours_goals_and_items(root):
    setup_plan(root)
    page, summary, line = view.render(root)
    assert 'WSJF: (value + time + risk) / size' in page and 'Login is safe under load' in page
    assert 'Rate limits &lt;for&gt; login' in page and '<script' not in page
    assert 'prefers-color-scheme: dark' in page
    assert line == '3 items on 2 goals and 1 unplanned, about 6 build hours (1 size point = 1 h); the plan is shown above.'
    assert len(summary.splitlines()) <= 30 and '| I-1 |' in summary


def test_new_items_wait_for_the_owner_to_approve_the_plan(root, fake):
    setup_plan(root)
    gaps = {row['item']: row['gaps'] for row in board.compute(root)}
    assert gaps['I-1'][0]['text'] == 'awaiting plan approval' and gaps['I-1'][0]['owner']
    question = 'plan: approve this plan? 3 items on 2 goals and 1 unplanned, about 6 build hours.'
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'AskUserQuestion', 'cwd': str(root),
                                      'tool_input': {'questions': [{'question': question}]},
                                      'tool_response': {'answers': {question: 'Approve'}}})
    assert all(item['approved'] for item in plan.items(root))
    assert sorted(ws.rows(root, 'plan.approved')[0]['data']['items']) == ['I-1', 'I-2', 'I-3']
    ws.cache_put(root, 'board', None)
    assert board.compute(root)[0]['gaps'][0]['text'] == 'no pull request yet'


def test_a_change_answer_is_recorded_and_approves_nothing(root):
    setup_plan(root)
    question = 'plan: approve this plan?'
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'AskUserQuestion', 'cwd': str(root),
                                      'tool_input': {'questions': [{'question': question}]},
                                      'tool_response': {'answers': {question: 'Change: drop I-3'}}})
    assert not any(item['approved'] for item in plan.items(root))
    assert ws.rows(root, 'plan.change')[0]['data']['answer'] == 'Change: drop I-3'
