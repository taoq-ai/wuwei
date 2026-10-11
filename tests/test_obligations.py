"""The PR-thread helpers the merge policy and pr act --reply read, through an in-process code_host port."""

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
    return tmp_path, host


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
