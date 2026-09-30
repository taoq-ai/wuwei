"""Absolute obligations through the CLI and an in-process code_host port."""

from copy import deepcopy
import importlib
import io
import json

import pytest

from fakes.code_host import Fake
from fakes.replay import install_replay
from wuwei import registry, state, workspace
from wuwei.__main__ import main
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
        gate_verdicts={'arch': {'pr': REF, 'verdict': 'PASS'}}), tmp_path, reserved=False)
    gate_file(tmp_path)
    return tmp_path, host


def sweep():
    try:
        return main(['sweep', 'obligations'])
    except SystemExit as exc:
        return exc.code


def sweep_event(root):
    rows = [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    return [row['payload'] for row in rows if row['kind'] == 'watch: sweep']


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
def test_absolute_reply_table(case, surface, records, expected, capsys):
    root, host = case
    if surface == 'reviews':
        host.results['reviews'] = Result(0, records)
    else:
        host.results['threads'].data[surface] = records
    assert sweep() == expected
    event, = sweep_event(root)
    assert event['reply_owed'] == expected
    assert event['owed'] == expected
    assert 'Please fix' not in capsys.readouterr().out


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
    state._write_state(lambda fresh: fresh.update(data), root, reserved=False)
    assert sweep() == expected
    assert sweep_event(root)[0]['visibility_owed'] == expected


@pytest.mark.parametrize('minimum,gate,expected,owed,skipped', [
    (0, True, 0, [], ['reviewer: shepherd.min_reviewers = 0', 'channel-post: shepherd.min_reviewers = 0']),
    (1, True, 1, ['reviewer'], ['channel-post: adapters.chat = "none"']),
    (0, False, 1, ['verdict'], ['reviewer: shepherd.min_reviewers = 0']),
])
def test_solo_owner_visibility_not_applicable(case, capsys, minimum, gate, expected, owed, skipped):
    root, host = case
    (root / '.wuwei/config.toml').write_text(
        f'[owner]\nhandles = ["U12345", "builder"]\n[shepherd]\nmin_reviewers = {minimum}\n')
    host.results['pr'].data['requested_reviewers'] = []
    state._write_state(lambda data: data.update(channel_posts=[]), root, reserved=False)
    if not gate:
        gate_file(root).unlink()
    assert sweep() == expected
    assert sweep_event(root)[0]['visibility_owed'] == len(owed)
    out = capsys.readouterr().out
    assert [line.split(' OWED ')[1] for line in out.splitlines() if ' OWED ' in line] == owed
    for line in skipped:
        assert f'{REF} NOT APPLICABLE {line}' in out


@pytest.mark.parametrize('operation,bad', [
    ('pr', Result(2, reason='offline')), ('threads', Result(2, reason='offline')),
    ('reviews', Result(2, reason='offline')),
    ('pr', Result(0, {'message': 'Not Found'})), ('pr', Result(0, {'state': 'unknown'})),
    ('threads', Result(0, {})), ('reviews', Result(0, {'message': 'denied'})),
    ('reviews', Result(0, [review(submitted_at='broken')])),
    ('threads', Result(0, {'comments': [comment(author=None)], 'threads': []})),
    ('threads', Result(0, {'comments': [], 'threads': [thread([])]})),
])
def test_unreadable_is_owed(case, operation, bad, capsys):
    root, host = case
    host.results[operation] = bad
    assert sweep() == 2
    event, = sweep_event(root)
    assert event['unreadable'] == 1 and event['owed'] >= 1
    assert 'unreadable' in capsys.readouterr().out.lower()


def test_api_error_body_stdout_is_unreadable(case, monkeypatch):
    root, _ = case
    adapter = importlib.import_module('adapters.code_host.github')
    monkeypatch.setattr(registry, 'load', lambda kind, config: adapter)
    install_replay(monkeypatch, 'gh', [{'stdout': '{"message":"Not Found","documentation_url":"https://docs.github.com"}'}])
    assert sweep() == 2
    assert sweep_event(root)[0]['unreadable'] == 1


def test_union_deduplicates_and_continues_after_error(case):
    root, host = case
    other = 'acme/widget#8'
    state._write_state(lambda data: data.update(claimed_prs=[REF, other]), root, reserved=False)
    original = host.pr
    def pr(ref, root=None):
        if ref == other:
            return Result(2, reason='unavailable')
        return original(ref, root)
    host.pr = pr
    assert sweep() == 2
    assert len([c for c in host.calls if c[0] == 'pr']) == 1
    event, = sweep_event(root)
    assert event['prs'] == 2 and event['unreadable'] == 1


@pytest.mark.parametrize('mode,expected', [('empty', 0), ('closed', 0), ('missing', 2), ('malformed', 2)])
def test_day_and_closed_pr(case, monkeypatch, mode, expected):
    root, host = case
    if mode == 'empty':
        monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
        state._write_state(lambda data: data.update(raised_prs=[]), root, reserved=False)
    if mode == 'closed': host.results['pr'].data['state'] = 'closed'
    if mode == 'missing': (workspace.day_dir(root) / 'state.json').unlink()
    if mode == 'malformed':
        data = state.read_state(root)
        data['raised_prs'] = ['widget#7 widget#8']
        workspace.atomic_write(workspace.day_dir(root) / 'state.json', json.dumps(data))
    assert sweep() == expected
    event, = sweep_event(root)
    assert event['exit'] == expected
    if mode in ('empty', 'missing', 'malformed'):
        assert not host.calls
    if mode == 'closed':
        assert [call[0] for call in host.calls] == ['pr']


def reply_command(monkeypatch, surface='review', id=1):
    monkeypatch.setattr('sys.stdin', io.StringIO('Fixed in the current change.'))
    try:
        return main(['reply', REF, '--surface', surface, '--id', str(id)])
    except SystemExit as exc:
        return exc.code


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


@pytest.mark.parametrize('surface', ['comment', 'review'])
def test_specific_ack_only_after_reply_and_edits_reopen(case, monkeypatch, surface):
    root, host = case
    rows = [comment(), comment(2)] if surface == 'comment' else [review(), review(2)]
    if surface == 'comment': host.results['threads'].data['comments'] = rows
    else: host.results['reviews'] = Result(0, rows)
    posting(host)
    assert sweep() == 1
    assert reply_command(monkeypatch, surface) == 0
    assert sweep() == 1
    assert sweep_event(root)[-1]['reply_owed'] == 1
    ledger = state.read_state(root)['reply_acks'][REF]
    assert set(ledger) == {f'{surface}:1'}
    assert 'Please fix' not in json.dumps(ledger)
    assert reply_command(monkeypatch, surface, 2) == 0
    assert sweep() == 0
    rows[0]['body'] = 'Edited finding'
    assert sweep() == 1
    assert sweep_event(root)[-1]['reply_owed'] == 1


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


@pytest.mark.parametrize('path,value', [
    ('reply_acks', {}), ('other.reply_acks', {}),
    ('other', {'reply_acks': {REF: {'review:1': 'forged'}}}),
])
def test_generic_state_cannot_forge_acknowledgements(case, path, value):
    root, _ = case
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state(path, value, root)


@pytest.mark.parametrize('bad', [[], {'bad-ref': {}}, {REF: {'review:1': 'forged'}}])
def test_corrupt_ledger_is_unreadable(case, bad):
    root, _ = case
    state._write_state(lambda data: data.update(reply_acks=bad), root, reserved=False)
    assert sweep() == 2
    assert sweep_event(root)[-1]['unreadable'] == 1


def test_deleted_reply_reopens_ack(case, monkeypatch):
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    posting(host)
    assert reply_command(monkeypatch) == 0
    host.results['threads'].data['comments'] = []
    assert sweep() == 1


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


def test_bad_reference_does_not_skip_other_prs(case):
    root, host = case
    state._write_state(lambda data: data.update(raised_prs=['invalid', REF]), root, reserved=False)
    host.results['reviews'] = Result(0, [review()])
    assert sweep() == 2
    event, = sweep_event(root)
    assert event['reply_owed'] == 1 and event['unreadable'] == 1
    assert len([call for call in host.calls if call[0] == 'pr']) == 1


def test_ack_cannot_use_a_preexisting_reply(case, monkeypatch):
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    host.results['threads'].data['comments'] = [comment(99, ME, 'Fixed in the current change.')]
    host.comment = lambda *args, **kwargs: Result(0, {'id': 99})
    assert reply_command(monkeypatch) == 2
    assert not state.read_state(root).get('reply_acks')


def test_edited_reply_reopens_ack(case, monkeypatch):
    root, host = case
    host.results['reviews'] = Result(0, [review()])
    posting(host)
    assert reply_command(monkeypatch) == 0
    host.results['threads'].data['comments'][0]['body'] = 'Reply retracted'
    assert sweep() == 1
    assert sweep_event(root)[-1]['reply_owed'] == 1


@pytest.mark.parametrize('path,value', [
    ('channel_posts', []), ('other.channel_posts', []),
    ('other', {'channel_posts': [{'pr': REF, 'status': 'posted'}]}),
])
def test_channel_posts_require_dedicated_producer(case, path, value):
    root, _ = case
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state(path, value, root)


def test_channel_post_stays_owed_without_producer(case):
    root, _ = case
    state._write_state(lambda data: data.pop('channel_posts'), root, reserved=False)
    assert sweep() == 1
    assert sweep_event(root)[-1]['visibility_owed'] == 1


@pytest.mark.parametrize('value', ['PASS', 'FIX', 'PARK', 'ESCALATE'])
def test_linted_gate_file_supplies_verdict_without_state(case, value):
    root, _ = case
    state._write_state(lambda data: data.update(gate_verdicts={}), root, reserved=False)
    gate_file(root, verdict=value)
    assert sweep() == 0


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
    assert sweep() == 1
    assert sweep_event(root)[-1]['visibility_owed'] == 1


@pytest.mark.parametrize('history', ['state_write', 'dedicated_write', 'raised_prs', 'claimed_prs', 'sweep'])
def test_empty_pr_set_cannot_erase_today_history(case, history):
    root, _ = case
    directory = workspace.day_dir(root)
    if history != 'state_write':
        (directory / 'events.jsonl').unlink()
        if history == 'dedicated_write':
            state._write_state(lambda data: None, root, kind='seat stopped')
        elif history == 'sweep':
            state.append_event('watch: sweep', {'sweep': 'obligations', 'prs': 1}, root)
        else:
            state.append_event('state.set', {'path': history, 'value': [REF]}, root)
    data = state.read_state(root)
    data.update(raised_prs=[], claimed_prs=[])
    workspace.atomic_write(directory / 'state.json', json.dumps(data))
    state.set_state('cap', 2, root)
    assert sweep() == 2
    assert sweep_event(root)[-1]['unreadable'] == 1


@pytest.mark.parametrize('events', [None, '{bad json', '[]', '{"kind":"state.set"}'])
def test_empty_pr_set_requires_readable_history(case, events):
    root, _ = case
    directory = workspace.day_dir(root)
    workspace.atomic_write(directory / 'state.json', json.dumps(state.DAY_DEFAULTS))
    path = directory / 'events.jsonl'
    path.unlink()
    if events is not None: path.write_text(events + '\n')
    assert sweep() == 2
    assert sweep() == 2


@pytest.mark.parametrize('handles', [[], ['U12345'], ['builder', 'reviewer'], ['bad handle']])
def test_identity_must_be_unambiguous_config(case, handles):
    root, _ = case
    (root / '.wuwei/config.toml').write_text('[owner]\nhandles = ' + json.dumps(handles) + '\n')
    assert sweep() == 2
    assert sweep_event(root)[-1]['unreadable'] == 1


@pytest.mark.parametrize('command', ['sweep', 'reply'])
def test_me_override_is_not_accepted(case, monkeypatch, command):
    _, host = case
    host.results['reviews'] = Result(0, [review(author=ME)])
    host.results['pr'].data['requested_reviewers'] = ['reviewer']
    monkeypatch.setattr('sys.stdin', io.StringIO('Acknowledged'))
    args = ['sweep', 'obligations'] if command == 'sweep' else [
        'reply', REF, '--surface', 'review', '--id', '1']
    with pytest.raises(SystemExit) as exc:
        main([*args, '--me', 'reviewer'])
    assert exc.value.code == 2
    assert not host.calls


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
    state._write_state(lambda data: data['channel_posts'][0].update(reviewers=mentions),
                       root, reserved=False)
    assert sweep() == expected
    assert sweep_event(root)[-1]['visibility_owed'] == expected


def test_gate_symlink_keeps_target_lint_requirements(case):
    root, _ = case
    path = gate_file(root)
    target = path.with_name('quality.md')
    path.rename(target)
    path.symlink_to(target.name)
    assert sweep() == 1
    assert sweep_event(root)[-1]['visibility_owed'] == 1
