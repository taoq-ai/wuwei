"""A PR the team raises is put in front of reviewers where the team asks for reviews (#884)."""

from conftest import make_pr, write_plan
from wuwei import __main__ as cli, board, evidence, hook, ws

PLACE = 'Slack #eng-reviews'


def standards(root):
    (root / ws.DIR / 'standards.md').write_text(f'# Standards\n\nReview requests: {PLACE}\n')


def planned(root):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open'}])


def duty(root):
    return [g for g in evidence.gaps(root, 'acme/app', 42) if g['text'].startswith('review not requested')]


def test_an_unannounced_pr_owes_a_review_request_that_shows_but_does_not_hold_the_merge(root, fake):
    standards(root)
    planned(root)
    fake.prs['42'] = make_pr()
    [found] = duty(root)
    assert PLACE in found['text'] and found['kind'] == 'duty' and found['actionable']
    assert found not in evidence.blocking(evidence.gaps(root, 'acme/app', 42))
    assert any(g['text'] == found['text'] for row in board.compute(root) for g in row['gaps'])


def test_a_send_naming_the_pr_meets_the_duty(root, fake):
    standards(root)
    planned(root)
    fake.prs['42'] = make_pr()
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'mcp__slack__slack_send_message',
                                      'tool_input': {'channel_id': 'C1', 'text': 'Review please: https://github.com/acme/app/pull/42'}})
    assert duty(root) == []


def test_a_post_made_outside_the_session_is_recorded_with_its_link(root, fake, monkeypatch):
    standards(root)
    planned(root)
    fake.prs['42'] = make_pr()
    monkeypatch.chdir(root)
    assert cli.main(['sent', 'acme/app#42', 'https://acme.slack.com/archives/C1/p1700000000000100']) == 0
    assert duty(root) == []


def test_no_place_named_or_a_review_already_in_means_no_duty(root, fake):
    planned(root)
    fake.prs['42'] = make_pr()
    assert duty(root) == []
    standards(root)
    fake.prs['42'] = make_pr(reviews=(('alice', 'COMMENTED'),))
    assert duty(root) == []


def test_a_pr_raised_by_hand_is_adopted_by_the_board(root, fake):
    standards(root)
    fake.prs['51'] = make_pr(number=51, body='quick fix', author='owner')
    fake.prs['52'] = make_pr(number=52, body='not ours', author='someone-else')
    rows = [r for r in board.compute(root) if r['item'] == 'unplanned']
    assert [r['pr'] for r in rows] == ['acme/app#51']
    assert any(g['text'].startswith('review not requested') for g in rows[0]['gaps'])


def test_the_old_item_line_shows_on_the_full_board_only(root, fake):
    planned(root)
    fake.prs['42'] = make_pr(body='WUWEI-Item: I-1')
    old = 'PR names its item by the old WUWEI-Item line: end the body with the WUWEI footer'
    shown = lambda everything: [g['text'] for row in board.compute(root, everything) if row['item'] == 'I-1' for g in row['gaps']]  # noqa: E731
    assert old in shown(True) and old not in shown(False)


def test_an_unlinked_draft_by_the_session_login_shows_as_unplanned(root, fake):
    fake.prs['53'] = {**make_pr(number=53, body='wip', author='owner'), 'isDraft': True, 'headRefName': 'wip-thing'}
    fake.prs['54'] = {**make_pr(number=54, body='wip', author='someone-else'), 'isDraft': True, 'headRefName': 'other'}
    assert [r['pr'] for r in board.compute(root) if r['item'] == 'unplanned'] == ['acme/app#53']
