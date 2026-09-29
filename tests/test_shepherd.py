"""Shepherd flow against fresh, in-process port evidence."""

from copy import deepcopy

import pytest

from fakes.code_host import Fake as Host
from wuwei import registry, state, workspace
from wuwei.registry import Result

REF = 'acme/widget#7'
SHA = 'a' * 40


class Port:
    def __init__(self, **responses):
        self.responses = responses
        self.calls = []

    def __getattr__(self, name):
        def call(*args, root=None):
            self.calls.append((name, args))
            value = self.responses.get(name, Result(2, reason='unconfigured port call'))
            return value(*args) if callable(value) else value
        return call


@pytest.fixture
def case(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('''
[owner]
name = "Builder"
handles = ["U12345", "builder"]
[[repos]]
name = "acme/widget"
path = "repo"
default_branch = "main"
[repos.merge]
bot_login = "review-bot"
[adapters]
review_bot = "greptile"
[shepherd]
review_channel = "CREVIEW"
lead_login = "lead"
review_gate_check = "Review Gate"
[shepherd.authors]
"alice@example.test" = { login = "alice", mention = "UALICE" }
"bob@example.test" = { login = "bob", mention = "UBOB" }
"lead@example.test" = { login = "lead", mention = "ULEAD" }
''')
    (tmp_path / 'repo').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    host = Host()
    host.results['pr'].data['requested_reviewers'] = ['alice', 'bob']
    host.results['threads'] = Result(0, {'comments': [], 'threads': []})
    host.results['reviews'] = Result(0, [])
    host.results['request_reviewers'] = Result(0, {'requested': ['alice', 'bob', 'lead']})
    def author_login(repo, email, root=None):
        return Result(0, {'login': {
            'alice@example.test': 'alice', 'bob@example.test': 'bob',
            'lead@example.test': 'lead'}[email]})
    host.author_login = author_login
    host.results['files'] = Result(0, [{'path': 'src/app.py'}])
    bot = Port(score=Result(0, 5), open_findings=Result(0, []))
    chat = Port(post=Result(0, {'channel': 'CREVIEW', 'ts': '1.1'}))
    vcs = Port(authorship=Result(0, [
        {'email': 'alice@example.test', 'commits': 4},
        {'email': 'bob@example.test', 'commits': 3},
    ]))
    ports = {'code_host': host, 'review_bot': bot, 'chat': chat, 'vcs': vcs}
    monkeypatch.setattr(registry, 'load', lambda kind, config: ports[kind])
    state._write_state(lambda data: data.update(raised_prs=[REF]), tmp_path, reserved=False)
    return tmp_path, host, bot, chat, vcs


def test_two_authors_selected_and_named(case):
    from wuwei import shepherd
    root, host, _, chat, vcs = case
    host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    reviewers = shepherd.select_reviewers(root, REF)
    assert reviewers == ['alice', 'bob', 'lead']
    assert next(args[1] for name, args in vcs.calls if name == 'authorship') == 'origin/main'
    assert shepherd.post_review_request(root, REF) == 0
    assert ('request_reviewers', (REF, ['alice', 'bob', 'lead']), root) in host.calls
    text = next(args[1] for name, args in chat.calls if name == 'post')
    assert '<@UALICE>' in text and '<@UBOB>' in text and '<@ULEAD>' in text
    assert state.read_state(root)['channel_posts'][0]['reviewers'] == reviewers


@pytest.mark.parametrize('change,expected', [
    ('clean', 0), ('dirty', 1), ('behind', 1), ('red', 1),
    ('pending', 1), ('missing_required', 1), ('no_required', 1),
    ('bot_low', 1), ('bot_stale', 1), ('bot_findings', 1),
    ('owed_reply', 1),
    ('unreadable', 2),
])
def test_production_ping_refusals(case, change, expected):
    from wuwei import shepherd
    root, host, bot, chat, _ = case
    if change in ('dirty', 'behind'):
        host.results['pr'].data['merge_state'] = change
    if change in ('red', 'pending'):
        host.results['checks'].data[0]['conclusion'] = 'failure' if change == 'red' else None
        host.results['checks'].data[0]['state'] = 'completed' if change == 'red' else 'in_progress'
    if change == 'missing_required':
        host.results['checks'].data.pop(0)
    if change == 'no_required':
        host.results['protection'].data['required_checks'] = []
    if change == 'bot_low': bot.responses['score'] = Result(0, 4)
    if change == 'bot_stale':
        host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
            'body': 'Confidence Score: 5/5 /commit/' + 'b' * 40,
            'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    if change != 'bot_stale':
        host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
            'body': 'Confidence Score: 5/5 /commit/' + SHA,
            'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    if change == 'owed_reply':
        host.results['threads'].data['comments'].append({
            'id': 2, 'author': 'alice', 'is_bot': False, 'body': 'Please explain this change.',
            'created_at': '2026-09-29T11:00:00Z'})
    if change == 'bot_findings': bot.responses['open_findings'] = Result(0, [{'id': 1}])
    if change == 'unreadable': host.results['checks'] = Result(2, reason='offline')
    result = shepherd.ping_gate(root, REF)
    assert result.exit == expected
    if change == 'owed_reply':
        assert result.reason == 'review replies are owed'
    if expected:
        assert result.reason
        assert shepherd.post_review_request(root, REF) == expected
        assert not chat.calls


def test_review_request_rechecks_gate_after_requesting_reviewers(case):
    from wuwei import shepherd
    root, host, _, chat, _ = case
    host.results['threads'].data['comments'] = [{
        'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]

    def request_reviewers(ref, logins, root=None):
        host.results['checks'].data[0]['conclusion'] = 'failure'
        return Result(0, {'requested': logins})

    host.request_reviewers = request_reviewers
    assert shepherd.post_review_request(root, REF) == 1
    assert not chat.calls


def test_raise_checks_gates_then_requests_recent_authors(case, monkeypatch):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00Z')
    vcs.responses.update(identity=Result(0, {'name': 'Builder', 'email': 'builder@example.test',
                                             'author': {'name': 'Builder', 'email': 'builder@example.test'},
                                             'committer': {'name': 'Builder', 'email': 'builder@example.test'}}),
                         head=Result(0, {'sha': SHA}),
                         branch=Result(0, {'name': 'feature'}),
                         merge_base=Result(0, {'sha': 'b' * 40}),
                         diff_stat=Result(0, [{'path': 'src/app.py', 'additions': 1, 'deletions': 0}]))
    host.results['create_pr'] = Result(0, {'number': 7, 'url': 'https://github.com/acme/widget/pull/7'})
    monkeypatch.setattr('wuwei.guards.pr.gate_check', lambda *a, **kw: (0, ''))
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert state.read_state(root)['pr_reviewers'][REF] == ['alice', 'bob', 'lead']
    assert ('request_reviewers', (REF, ['alice', 'bob', 'lead']), root) in host.calls
    assert not any(name == 'post' for name, _ in case[3].calls)


def test_raise_refuses_failed_gate_without_creating(case, monkeypatch):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    vcs.responses['head'] = Result(0, {'sha': SHA})
    monkeypatch.setattr('wuwei.guards.pr.gate_check', lambda *a, **kw: (1, 'gate failed'))
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
    assert not any(name == 'create_pr' for name, _, _ in host.calls)


def test_thread_reply_rechecks_last_word(case):
    from wuwei import obligations
    root, host, _, _, _ = case
    row = {'id': 31, 'author': 'alice', 'is_bot': False, 'body': 'Why?',
           'created_at': '2026-09-29T10:00:00Z'}
    host.results['threads'] = Result(0, {'comments': [], 'threads': [
        {'id': 'T1', 'resolved': False, 'outdated': False, 'comments': [row]}]})
    def changed(ref, root=None):
        value = deepcopy(host.results['threads'].data)
        value['threads'][0]['comments'].append({**row, 'id': 32, 'author': 'bob'})
        return Result(0, value)
    original = host.threads
    calls = 0
    def threads(ref, root=None):
        nonlocal calls
        calls += 1
        return original(ref, root) if calls == 1 else changed(ref, root)
    host.threads = threads
    assert obligations.reply(REF, 'thread', 31, 'Acknowledged', root) == 1
    assert not any(name == 'comment' for name, _, _ in host.calls)


def test_review_gate_check_is_excluded(case):
    from wuwei import shepherd
    root, host, _, _, _ = case
    host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    host.results['checks'].data.append({'name': 'Review Gate', 'state': 'pending',
                                         'conclusion': None, 'sha': SHA})
    host.results['protection'].data['required_checks'].append({'name': 'Review Gate', 'app_id': None})
    assert shepherd.ping_gate(root, REF).exit == 0


def test_approved_action_runs_existing_merge(case, monkeypatch):
    from wuwei import pr_actions
    root, _, _, _, _ = case
    monkeypatch.setattr(pr_actions, 'evaluate', lambda root, refs=None: (1, [
        {'pr': REF, 'state': 'approved', 'action': 'wuwei merge or merge decision',
         'exit': 1, 'parked': False}]))
    called = []
    monkeypatch.setattr('wuwei.merge.execute', lambda ref, root=None: called.append(ref) or Result(0, {'merged': True}))
    assert pr_actions.act(root, REF) == 0
    assert called == [REF]


def test_uncleared_merge_keeps_owner_decision_due(case, monkeypatch, capsys):
    from wuwei import pr_actions
    root, _, _, _, _ = case
    monkeypatch.setattr(pr_actions, 'evaluate', lambda root, refs=None: (1, [
        {'pr': REF, 'state': 'approved', 'action': 'wuwei merge or merge decision',
         'exit': 1, 'parked': False}]))
    monkeypatch.setattr('wuwei.merge.execute', lambda ref, root=None: Result(1, reason='soak window'))
    assert pr_actions.act(root, REF) == 1
    assert 'owner merge decision' in capsys.readouterr().out


def test_review_request_outbound_tier_uses_fresh_gate(case):
    from wuwei import outward
    root, host, _, _, _ = case
    config = workspace.load_config(root)
    config['outbound']['work_channels'] = ['CREVIEW']
    state._write_state(lambda data: data.update(pr_reviewers={REF: ['alice', 'bob', 'lead']}), root, reserved=False)
    host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    text = 'PR #7 ready for review: <https://github.com/acme/widget/pull/7|#7> <@UALICE> <@UBOB> <@ULEAD>'
    assert outward.classify(text, root, config, {'channel': 'CREVIEW', 'text': text}, kind='chat') == (0, 'send')
    host.results['checks'].data[0]['conclusion'] = 'failure'
    assert outward.classify(text, root, config, {'channel': 'CREVIEW', 'text': text}, kind='chat')[1] == 'draft'


def test_reviewer_ladder_widens_for_sparse_history(case):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    def history(repo, branch, paths, days):
        return Result(0, [{'email': 'alice@example.test', 'commits': 2}] if days == 90 else [
            {'email': 'alice@example.test', 'commits': 3},
            {'email': 'bob@example.test', 'commits': 1}])
    vcs.responses['authorship'] = history
    assert shepherd.select_reviewers(root, REF) == ['alice', 'bob', 'lead']
    assert [args[-1] for name, args in vcs.calls if name == 'authorship'] == [90, 180]


def test_unverified_reviewer_login_refuses_request(case):
    from wuwei import shepherd
    root, host, _, _, _ = case
    host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    host.author_login = lambda repo, email, root=None: Result(0, {'login': 'stranger'})
    assert shepherd.post_review_request(root, REF) == 2
    assert not any(name == 'request_reviewers' for name, _, _ in host.calls)


def test_raise_body_obeys_review_voice(case, monkeypatch):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    (root / '.wuwei/memory').mkdir()
    (root / '.wuwei/memory/voice.md').write_text('## review\n- never: Body\n')
    vcs.responses['head'] = Result(0, {'sha': SHA})
    monkeypatch.setattr('wuwei.guards.pr.gate_check', lambda *a, **kw: (0, ''))
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
    assert not any(name == 'create_pr' for name, _, _ in host.calls)


def test_new_port_adapters_parse_recorded_output(tmp_path, monkeypatch):
    from adapters.code_host import github
    from adapters.vcs import git
    from fakes.replay import install_replay
    install_replay(monkeypatch, 'gh', [{'stdout': '{"total_count":1,"items":[{"author":{"login":"alice"}}]}'}])
    assert github.author_login('acme/widget', 'alice@example.test').data == {'login': 'alice'}
    install_replay(monkeypatch, 'git', [{'stdout': 'alice@example.test\nalice@example.test\nbob@example.test\n'}])
    assert git.authorship(str(tmp_path), 'origin/main', ['src/app.py'], 90).data == [
        {'email': 'alice@example.test', 'commits': 2},
        {'email': 'bob@example.test', 'commits': 1}]


def test_missing_branch_protection_keeps_reason_for_fallback(monkeypatch):
    from adapters.code_host import github
    from fakes.replay import install_replay
    install_replay(monkeypatch, 'gh', [{'exit': 1, 'stderr': 'HTTP 404: Not Found'}])
    result = github.protection('acme/widget', 'feature-base')
    assert result.exit == 2
    assert 'branch protection absent' in result.reason


def test_thread_reply_posts_to_current_root_and_verifies_last_word(case):
    from wuwei import obligations
    root, host, _, _, _ = case
    first = {'id': 31, 'author': 'alice', 'is_bot': False, 'body': 'Why?',
             'created_at': '2026-09-29T10:00:00Z'}
    host.results['threads'] = Result(0, {'comments': [], 'threads': [
        {'id': 'T1', 'resolved': False, 'outdated': False, 'comments': [first]}]})
    def post(ref, text, thread, root=None):
        assert thread == 31
        host.results['threads'].data['threads'][0]['comments'].append({
            'id': 32, 'author': 'builder', 'is_bot': False, 'body': text,
            'created_at': '2026-09-29T11:00:00Z'})
        return Result(0, {'id': 32})
    host.comment = post
    assert obligations.reply(REF, 'thread', 31, 'Acknowledged', root) == 0
    assert not state.read_state(root).get('reply_acks')


def test_configured_required_check_fallback_for_unprotected_base(case, monkeypatch):
    from wuwei import shepherd
    root, host, _, _, _ = case
    config = workspace.load_config(root)
    config['repos'][0]['review_required_checks'] = ['tests']
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    host.results['protection'].data['required_checks'] = []
    host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    assert shepherd.ping_gate(root, REF).exit == 0


def test_review_post_restarts_stale_window(case, monkeypatch):
    from wuwei import pr_actions
    root, host, _, _, _ = case
    assert pr_actions.evaluate(root, [REF])[1][0]['state'] == 'waiting'
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T14:01:00Z')
    assert pr_actions.evaluate(root, [REF])[1][0]['state'] == 'review_stale'
    state._write_state(lambda data: data.update(channel_posts=[{
        'pr': REF, 'status': 'posted', 'head': SHA,
        'url': 'https://slack.com/archives/CREVIEW/p11', 'reviewers': ['alice', 'bob'],
        'posted_at': '2026-09-29T14:01:00+00:00'}]), root, reserved=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T14:02:00Z')
    assert pr_actions.evaluate(root, [REF])[1][0]['state'] == 'waiting'


def test_authorship_windows_are_configured(case, monkeypatch):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    config = workspace.load_config(root)
    config['shepherd']['author_windows_days'] = [30, 60]
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    vcs.responses['authorship'] = lambda repo, branch, paths, days: Result(0,
        [{'email': 'alice@example.test', 'commits': 2}] if days == 30 else [
            {'email': 'alice@example.test', 'commits': 3},
            {'email': 'bob@example.test', 'commits': 1}])
    assert shepherd.select_reviewers(root, REF) == ['alice', 'bob', 'lead']
    assert [args[-1] for name, args in vcs.calls if name == 'authorship'] == [30, 60]


def test_all_history_before_lead_floor(case):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    vcs.responses['authorship'] = lambda repo, branch, paths, days: Result(0,
        [{'email': 'alice@example.test', 'commits': 2}] if days else [
            {'email': 'alice@example.test', 'commits': 3},
            {'email': 'bob@example.test', 'commits': 1}])
    assert shepherd.select_reviewers(root, REF) == ['alice', 'bob', 'lead']
    assert [args[-1] for name, args in vcs.calls if name == 'authorship'] == [90, 180, 0]


def test_review_bot_uninstalled_is_distinct_from_not_reviewed(case, monkeypatch):
    from wuwei import shepherd
    root, host, bot, _, _ = case
    config = workspace.load_config(root)
    config['adapters']['review_bot'] = 'none'
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    assert shepherd.ping_gate(root, REF).exit == 0
    assert bot.calls == []


def test_stacked_base_uses_default_branch_required_checks(case):
    from wuwei import shepherd
    root, host, _, _, _ = case
    host.results['pr'].data['base'] = 'feature-base'
    host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    calls = []
    def protection(repo, branch, root=None):
        calls.append(branch)
        return Result(2, reason='branch protection absent') if branch == 'feature-base' else host.results['protection']
    host.protection = protection
    assert shepherd.ping_gate(root, REF).exit == 0
    assert calls == ['feature-base', 'main']
