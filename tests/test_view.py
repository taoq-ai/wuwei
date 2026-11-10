"""The plan as a view to approve (#990): one picture, one short question."""

from conftest import answered
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
    hook.handle(root, 'PostToolUse', answered(root, [question], {question: 'Approve'}))
    assert all(item['approved'] for item in plan.items(root))
    assert sorted(ws.rows(root, 'plan.approved')[0]['data']['items']) == ['I-1', 'I-2', 'I-3']
    ws.cache_put(root, 'board', None)
    assert board.compute(root)[0]['gaps'][0]['text'] == 'no pull request yet'


def test_a_change_answer_is_recorded_and_approves_nothing(root):
    setup_plan(root)
    question = 'plan: approve this plan?'
    hook.handle(root, 'PostToolUse', answered(root, [question], {question: 'Change: drop I-3'}))
    assert not any(item['approved'] for item in plan.items(root))
    assert ws.rows(root, 'plan.change')[0]['data']['answer'] == 'Change: drop I-3'


def ai_history(root, monkeypatch, merged=5, days=3, key='D'):  # each merged item: size 2, a 1 h builder and a 0.5 h gate seat
    import datetime
    real, start = ws.now, ws.now() - datetime.timedelta(days=days)
    for n in range(merged):
        plan.add(root, f'{key}-{n}', 'Done', 'G-1', 'acme/app', 'standard', scores(size=2))
        plan.mark(root, f'{key}-{n}', 'done', f'merged as acme/app#{n}')
        for role, agent, hours in (('builder', f'{key}b{n}', 1), ('sentinel-quality', f'{key}g{n}', 0.5)):
            for kind, at in (('seat.started', start), ('seat.stopped', start + datetime.timedelta(hours=hours))):
                monkeypatch.setattr(ws, 'now', lambda at=at: at)
                ws.record(root, kind, {'role': role, 'agent': agent, 'item': f'{key}-{n}'})
    monkeypatch.setattr(ws, 'now', real)


def test_the_view_adds_an_ai_estimate_from_seat_wall_clock_beside_build_hours(root, monkeypatch):
    setup_plan(root)
    ai_history(root, monkeypatch)
    page, summary, line = view.render(root)
    assert line == '3 items on 2 goals and 1 unplanned, about 6 build hours (1 size point = 1 h); the plan is shown above.'
    assert 'AI estimate: 4.5 h (0.75 h per size point, n=5 merged items)' in summary.splitlines()
    assert '<b>4.5 h</b><span>AI estimate (0.75 h per size point, n=5 merged items)</span>' in page
    assert '<b>6</b><span>build hours (1 size point = 1 h)</span>' in page


def test_the_ai_estimate_is_unmeasured_below_five_merged_items(root, monkeypatch):
    setup_plan(root)
    ai_history(root, monkeypatch, merged=4)
    ai_history(root, monkeypatch, days=29, key='OLD')  # outside the 28-day window
    page, summary, line = view.render(root)
    assert 'AI estimate: unmeasured (4 merged items)' in summary.splitlines()
    assert '<b>unmeasured</b><span>AI estimate (4 merged items)</span>' in page
