"""The PR-thread helpers the merge policy and pr act --reply read, through an in-process code_host port."""

import json

import pytest

from fakes.code_host import Fake
from wuwei import registry, state, workspace
from wuwei.registry import Result

REF = 'acme/widget#7'
ME = 'builder'
AT = '2026-09-28T10:00:00Z'


def comment(id=1, author='reviewer', body='Please fix', **extra):
    return {'id': id, 'author': author, 'is_bot': False, 'body': body,
            'created_at': AT, 'updated_at': AT, **extra}


def review(id=1, author='reviewer', **extra):
    value = comment(id, author)
    value.update(state='commented', submitted_at=AT)
    value.update(extra)
    return value


def thread(comments, **extra):
    return {'id': 'T1', 'resolved': False, 'outdated': False,
            'comments': comments, **extra}


def gate_file(root, verdict='PASS', head='a' * 40):
    path = workspace.day_dir(root) / 'decisions/gate-arch.md'
    path.parent.mkdir(exist_ok=True)
    finding = '' if verdict == 'PASS' else 'P1: src/app.py:1 blocks: yes; fails when input is empty.\n'
    path.write_text(f'Verdict: {verdict}\nHead: {head}\n{finding}'
                    'Probe: not run\nAUTH: PASS\nBlocked: none\nGap: none\nChange: none\n')
    return path


@pytest.fixture
def case(tmp_path, monkeypatch):
    from fakes.integrity import measured
    measured(monkeypatch)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nhandles = ["U12345", "builder"]\n'
                                                 '[adapters]\nchat = "slack"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    host = Fake()
    host.results['threads'] = Result(0, {'comments': [], 'threads': []})
    host.results['reviews'] = Result(0, [])
    monkeypatch.setattr(registry, 'load', lambda kind, config: host)
    state._write_state(lambda data: data.update(
        raised_prs=[REF], channel_posts=[{'pr': REF, 'status': 'posted',
        'url': 'https://chat.example/messages/1', 'reviewers': ['reviewer']}],
        gate_verdicts={'arch': {'pr': REF, 'verdict': 'PASS'}}), tmp_path)
    gate_file(tmp_path)
    return tmp_path, host


def owed(root):
    """#847: (replies, visibility, not applicable) owed on REF, read through the helpers the
    merge policy and pr act read; a damaged or ambiguous input raises."""
    from wuwei import obligations
    config = workspace.load_config(root)
    data = state.read_state(root)
    me = obligations._owner_login(config)
    host = registry.load('code_host', config)
    pr = obligations._read(host.pr, REF, root=root)
    reviews, discussion = obligations._evidence(host, REF, root)
    replies = obligations._replies(reviews, discussion, me,
                                   obligations._ledger(data, root=root).get(REF, {}))
    visibility = obligations._visibility(REF, pr, reviews, data, me, workspace.day_dir(root), config)
    return replies, visibility, obligations._not_applicable(config, data.get('pr_reviewers', {}).get(REF))


@pytest.mark.parametrize('surface,records,expected', [
    ('comments', [], 0),
    ('comments', [comment()], 1),
    ('comments', [comment(), comment(2, ME, created_at='2026-09-28T11:00:00Z')], 1),
    ('comments', [comment(author=ME)], 0),
    ('comments', [comment(is_bot=True)], 0),
    ('comments', [comment(body='')], 0),
    ('reviews', [review()], 1),
    ('reviews', [review(), review(2, ME, submitted_at='2026-09-28T11:00:00Z')], 1),
    ('reviews', [review(state='changes_requested')], 1),
    ('reviews', [review(state='approved')], 0),
    ('reviews', [review(is_bot=True)], 0),
    ('threads', [thread([comment()])], 1),
    ('threads', [thread([comment(), comment(2, ME, created_at='2026-09-28T11:00:00Z')])], 0),
    ('threads', [thread([comment()], resolved=True)], 0),
    ('threads', [thread([comment()], outdated=True)], 1),
    ('threads', [thread([comment(is_bot=True, body='**P1** issue')])], 1),
    ('threads', [thread([comment(is_bot=True, body='badges/p1.svg')])], 1),
    ('threads', [thread([comment(is_bot=True, body='**P2** issue')])], 0),
    ('threads', [thread([comment(is_bot=True, body='**P1** issue')], outdated=True)], 0),
    ('threads', [thread([comment(is_bot=True, body='**P1** issue')], resolved=True)], 0),
    ('threads', [thread([comment(is_bot=True, body='**P1** issue'), comment(2, ME),
                         comment(3, 'robot', is_bot=True)])], 0),
    ('threads', [thread([comment(), comment(2, 'robot', is_bot=True)])], 1),
])
def test_absolute_reply_table(case, surface, records, expected):
    root, host = case
    if surface == 'reviews':
        host.results['reviews'] = Result(0, records)
    else:
        host.results['threads'].data[surface] = records
    replies, visibility, _ = owed(root)
    assert (len(replies), visibility) == (expected, [])


@pytest.mark.parametrize('change,expected', [
    ('clean', 0), ('no_reviewer', 1), ('submitted_review', 0), ('bot_review', 1),
    ('team', 0), ('held', 1), ('prose', 1), ('no_url', 1), ('bad_url', 1),
    ('no_mentions', 1), ('wrong_mentions', 1), ('wrong_pr', 1),
    ('no_verdict', 1), ('wrong_head', 1), ('empty_verdict', 1), ('fix_verdict', 0),
])
def test_visibility_table(case, change, expected):
    root, host = case
    data = state.read_state(root)
    post = data['channel_posts'][0]
    if change in ('no_reviewer', 'submitted_review', 'bot_review', 'team'):
        host.results['pr'].data['requested_reviewers'] = []
        if change in ('submitted_review', 'bot_review'):
            host.results['reviews'] = Result(0, [review(state='approved', is_bot=change == 'bot_review')])
        if change == 'team':
            host.results['pr'].data['requested_teams'] = ['review-team']
            post['reviewers'] = ['review-team']
    if change == 'held': post['status'] = 'held'
    if change == 'prose': data['channel_posts'] = [f'{REF} HELD https://chat.example/1']
    if change == 'no_url': post.pop('url')
    if change == 'bad_url': post['url'] = 'https://'
    if change == 'no_mentions': post['reviewers'] = []
    if change == 'wrong_mentions': post['reviewers'] = ['someone-else']
    if change == 'wrong_pr': post['pr'] = REF + '0'
    if change == 'no_verdict': gate_file(root).unlink()
    if change == 'wrong_head': gate_file(root, head='b' * 40)
    if change == 'empty_verdict': gate_file(root, verdict='')
    if change == 'fix_verdict': gate_file(root, verdict='FIX')
    state._write_state(lambda fresh: fresh.update(data), root)
    assert len(owed(root)[1]) == expected


@pytest.mark.parametrize('minimum,gate,owes,skipped', [
    (0, True, [], {'reviewer': 'shepherd.min_reviewers = 0', 'channel-post': 'shepherd.min_reviewers = 0'}),
    (1, True, ['reviewer'], {'channel-post': 'adapters.chat = "none"'}),
    (0, False, ['verdict'], {'reviewer': 'shepherd.min_reviewers = 0',
                             'channel-post': 'shepherd.min_reviewers = 0'}),
])
def test_solo_owner_visibility_not_applicable(case, minimum, gate, owes, skipped):
    root, host = case
    (root / '.wuwei/config.toml').write_text(
        f'[owner]\nhandles = ["U12345", "builder"]\n[shepherd]\nmin_reviewers = {minimum}\n')
    host.results['pr'].data['requested_reviewers'] = []
    state._write_state(lambda data: data.update(channel_posts=[]), root)
    if not gate:
        gate_file(root).unlink()
    _, visibility, not_applicable = owed(root)
    assert (visibility, not_applicable) == (owes, skipped)


@pytest.mark.parametrize('value', ['PASS', 'FIX', 'PARK', 'ESCALATE'])
def test_linted_gate_file_supplies_verdict_without_state(case, value):
    root, _ = case
    state._write_state(lambda data: data.update(gate_verdicts={}), root)
    gate_file(root, verdict=value)
    assert owed(root)[:2] == ([], [])


@pytest.mark.parametrize('bad', ['missing', 'unlinted', 'quoted', 'duplicate_head', 'stale'])
def test_state_verdict_cannot_replace_linted_current_gate(case, bad):
    root, _ = case
    path = gate_file(root)
    text = path.read_text()
    if bad == 'missing': path.unlink()
    if bad == 'unlinted': path.write_text(text.replace('Probe: not run\n', ''))
    if bad == 'quoted': path.write_text('```\n' + text + '```\n')
    if bad == 'duplicate_head': path.write_text(text + 'Head: ' + 'a' * 40 + '\n')
    if bad == 'stale': gate_file(root, head='b' * 40)
    assert owed(root)[1] == ['verdict']


def test_gate_symlink_keeps_target_lint_requirements(case):
    root, _ = case
    path = gate_file(root)
    target = path.with_name('quality.md')
    path.rename(target)
    path.symlink_to(target.name)
    assert owed(root)[1] == ['verdict']


@pytest.mark.parametrize('handles', [[], ['U12345'], ['builder', 'reviewer'], ['bad handle']])
def test_identity_must_be_unambiguous_config(case, handles):
    root, _ = case
    (root / '.wuwei/config.toml').write_text('[owner]\nhandles = ' + json.dumps(handles) + '\n')
    with pytest.raises(ValueError, match='owner.handles'):
        owed(root)


def test_me_comes_from_config_only(case, monkeypatch):
    # The former --me override: the owner login is owner.handles, never a caller's value.
    from wuwei import obligations
    root, host = case
    monkeypatch.setenv('WUWEI_ME', 'reviewer')
    assert obligations._owner_login(workspace.load_config(root)) == ME
    host.results['reviews'] = Result(0, [review(author=ME)])
    host.results['pr'].data['requested_reviewers'] = ['reviewer']
    assert owed(root)[:2] == ([], [])


@pytest.mark.parametrize('requested,mentions,expected', [
    (['reviewer'], ['reviewer'], 0),
    (['reviewer', 'second'], ['reviewer'], 1),
    ([], ['past-reviewer'], 0),
    ([], ['reviewer'], 1),
])
def test_mentions_cover_requests_or_fallback_authors(case, requested, mentions, expected):
    root, host = case
    host.results['pr'].data['requested_reviewers'] = requested
    host.results['reviews'] = Result(0, [review(author='past-reviewer', state='approved')])
    state._write_state(lambda data: data['channel_posts'][0].update(reviewers=mentions), root)
    assert len(owed(root)[1]) == expected


def reply_command(monkeypatch, surface='review', id=1):
    """#838: wuwei reply is gone; pr act --reply posts through obligations.reply."""
    from wuwei import obligations
    try:
        return obligations.reply(REF, surface, id, 'Fixed in the current change.')
    except Exception:  # the CLI reports any error as exit 2
        return 2


def posting(host, failure=None):
    def post(ref, text, thread, root=None):
        assert ref == REF and thread is None
        if failure == 'denied': return Result(1, reason='outward policy')
        if failure == 'error': return Result(2, reason='offline')
        reply_id = 99 + len(host.results['threads'].data['comments'])
        row = comment(reply_id, ME, text, created_at='2026-09-28T11:00:00Z')
        if failure == 'wrong_author': row['author'] = 'other'
        if failure == 'wrong_body': row['body'] = 'different'
        if failure != 'unseen': host.results['threads'].data['comments'].append(row)
        if failure == 'edited': host.results['reviews'].data[0]['body'] = 'Changed request'
        if failure == 'read_error': host.results['threads'] = Result(2, reason='offline')
        if failure == 'day_rollover':
            import os
            os.environ['WUWEI_NOW'] = '2026-09-29T00:00:00Z'
        return Result(0, {'id': reply_id, 'url': 'https://code.example/comment/99'})
    host.comment = post


@pytest.mark.parametrize('failure,expected', [
    ('denied', 1), ('error', 2), ('wrong_author', 2), ('wrong_body', 2),
    ('unseen', 2), ('edited', 2), ('read_error', 2),
])
def test_failed_reply_never_acknowledges(case, monkeypatch, failure, expected):
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    posting(host, failure)
    assert reply_command(monkeypatch) == expected
    assert not state.read_state(root).get('reply_acks')


def test_reply_pins_day_directory(case, monkeypatch):
    root, host = case
    directory = workspace.day_dir(root)
    host.results['reviews'] = Result(0, [review()])
    posting(host, 'day_rollover')
    assert reply_command(monkeypatch) == 0
    assert state.read_state(directory=directory)['reply_acks']
    assert not workspace.day_dir(root).exists()


def test_reply_ack_survives_days_until_new_comment_or_changed_evidence(case, monkeypatch):
    from wuwei import pr_actions
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    posting(host)
    assert reply_command(monkeypatch) == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    measured = {'reviews': host.results['reviews'].data, 'threads': host.results['threads'].data}
    assert pr_actions._owed(root, REF, measured) == []
    assert owed(root)[0] == []
    host.results['threads'].data['comments'].append(comment(101, created_at='2026-09-29T11:00:00Z'))
    assert owed(root)[0] == ['comment:101']
    host.results['reviews'].data[0]['body'] = 'Changed request'
    assert owed(root)[0] == ['comment:101', 'review:1']


def test_malformed_prior_day_ack_is_ignored_and_reply_is_owed(case, monkeypatch):
    from wuwei import pr_actions
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    state._write_state(lambda data: data.update(reply_acks={REF: {'review:1': {'bad': True}}}), root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    measured = {'reviews': host.results['reviews'].data, 'threads': host.results['threads'].data}
    assert [surface for surface, *_ in pr_actions._owed(root, REF, measured)] == ['review']


@pytest.mark.parametrize('surface,id', [('review', 999), ('comment', 999)])
def test_reply_missing_target_never_posts(case, monkeypatch, surface, id):
    _, host = case
    assert reply_command(monkeypatch, surface, id) == 2
    assert not [call for call in host.calls if call[0] == 'comment']


def test_ack_cannot_use_a_preexisting_reply(case, monkeypatch):
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    host.results['threads'].data['comments'] = [comment(99, ME, 'Fixed in the current change.')]
    host.comment = lambda *args, **kwargs: Result(0, {'id': 99})
    assert reply_command(monkeypatch) == 2
    assert not state.read_state(root).get('reply_acks')


def test_answered_is_the_latest_human_comment():
    from wuwei import obligations
    later = '2026-09-28T11:00:00Z'
    bot = comment(3, author='bot', is_bot=True, created_at=later, updated_at=later)
    assert obligations.answered(thread([comment(1), comment(2, author=ME, created_at=later), bot]), ME)
    assert not obligations.answered(thread([comment(1, author=ME), comment(2, created_at=later)]), ME)
    assert not obligations.answered(thread([]), ME)


@pytest.mark.parametrize('surface', ['comment', 'review'])
def test_specific_ack_only_after_reply_and_edits_reopen(case, monkeypatch, surface):
    root, host = case
    rows = [comment(), comment(2)] if surface == 'comment' else [review(), review(2)]
    if surface == 'comment': host.results['threads'].data['comments'] = rows
    else: host.results['reviews'] = Result(0, rows)
    posting(host)
    assert owed(root)[0] == [f'{surface}:1', f'{surface}:2']
    assert reply_command(monkeypatch, surface) == 0
    assert owed(root)[0] == [f'{surface}:2']
    ledger = state.read_state(root)['reply_acks'][REF]
    assert set(ledger) == {f'{surface}:1'}
    assert 'Please fix' not in json.dumps(ledger)
    assert reply_command(monkeypatch, surface, 2) == 0
    assert owed(root)[0] == []
    rows[0]['body'] = 'Edited finding'
    assert owed(root)[0] == [f'{surface}:1']


def test_deleted_reply_reopens_ack(case, monkeypatch):
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    posting(host)
    assert reply_command(monkeypatch) == 0
    assert owed(root)[0] == []
    host.results['threads'].data['comments'] = []
    assert owed(root)[0] == ['review:1']


def test_edited_reply_reopens_ack(case, monkeypatch):
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    posting(host)
    assert reply_command(monkeypatch) == 0
    host.results['threads'].data['comments'][0]['body'] = 'Reply retracted'
    assert owed(root)[0] == ['review:1']
