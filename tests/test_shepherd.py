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
[outbound]
default_tier = "ask"
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
        login = {'alice@example.test': 'alice', 'bob@example.test': 'bob',
                 'lead@example.test': 'lead', 'carol@example.test': 'carol',
                 'builder@example.test': 'builder'}.get(email)
        return Result(0, {'login': login}) if login else Result(2, reason='author login unavailable')
    host.author_login = author_login
    host.results['files'] = Result(0, [{'path': 'src/app.py'}])
    bot = Port(score=Result(0, 5), open_findings=Result(0, []))
    chat = Port(post=Result(0, {'channel': 'CREVIEW', 'ts': '1.1'}))
    vcs = Port(worktrees=Result(0, []), authorship=Result(0, [
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


def test_claim_links_existing_pr_for_ownership_and_metrics(case):
    from wuwei.__main__ import main
    from wuwei import metrics
    root, host, _, _, _ = case
    claimed = 'acme/widget#8'
    host.results['pr'].data.update(number=8, url='https://github.com/acme/widget/pull/8')
    state._write_state(lambda data: (data['items'].update(A={}),
                      data['approved_items'].append('A')), root, reserved=False)
    assert main(['pr', 'claim', claimed, '--item', 'A']) == 0
    data = state.read_state(root)
    assert data['items']['A']['pr'] == claimed
    assert data['claimed_prs'] == [claimed]
    assert metrics._references(root)[1] == {'A': {claimed}}
    assert main(['pr', 'claim', claimed, '--item', 'A']) == 0
    assert state.read_state(root)['claimed_prs'] == [claimed]


def adopted_day(root, goals):
    state._write_state(lambda data: data.update(gate_approved=True, goals=goals), root, reserved=False)


def test_claim_creates_an_adopted_item(case, capsys):
    from wuwei.__main__ import main
    root, host, _, _, _ = case
    host.results['pr'].data.update(number=8, url='https://github.com/acme/widget/pull/8')
    adopted_day(root, ['G-1', 'G-2'])
    before = state.read_state(root)
    assert main(['pr', 'claim', 'acme/widget#8']) == 1
    assert '--goal' in capsys.readouterr().out and state.read_state(root) == before
    assert main(['pr', 'claim', 'acme/widget#8', '--goal', 'G-1']) == 0
    data = state.read_state(root)
    item = data['items']['PR-8']
    assert {key: item[key] for key in ('source', 'title', 'phase', 'pr', 'goal')} == {
        'source': 'adopted', 'title': 'Add a widget option', 'phase': 'raised',
        'pr': 'acme/widget#8', 'goal': 'G-1'}
    assert 'PR-8' in data['approved_items'] and data['claimed_prs'] == ['acme/widget#8']
    assert main(['pr', 'claim', '8']) == 0
    assert [name for name in state.read_state(root)['items']] == ['PR-8']


def test_claim_bare_number_takes_the_only_goal(case):
    from wuwei.__main__ import main
    root, host, _, _, _ = case
    host.results['pr'].data.update(number=8, url='https://github.com/acme/widget/pull/8')
    adopted_day(root, ['G-1'])
    assert main(['pr', 'claim', '8']) == 0
    assert state.read_state(root)['items']['PR-8']['goal'] == 'G-1'


def test_claim_adopts_the_branch_worktree(case, monkeypatch, capsys):
    from wuwei.__main__ import main
    root, host, _, _, vcs = case
    host.results['pr'].data.update(number=8, url='https://github.com/acme/widget/pull/8')
    adopted_day(root, ['G-1'])
    adopted = []

    def adopt(root, item, path, vcs):
        adopted.append((item, path))
        if path == 'dirty':
            raise state.StateError('worktree has unrecorded changes: a.txt')
        return {'item': item, 'path': path, 'head': SHA}
    monkeypatch.setattr(workspace, 'adopt_worktree', adopt)
    vcs.responses['worktrees'] = Result(0, [{'path': 'main', 'branch': 'main', 'head': SHA},
                                            {'path': 'house', 'branch': 'feature', 'head': SHA}])
    assert main(['pr', 'claim', '8']) == 0
    assert adopted == [('PR-8', 'house')] and '"path": "house"' in capsys.readouterr().out
    vcs.responses['worktrees'] = Result(0, [{'path': 'dirty', 'branch': 'feature', 'head': SHA}])
    assert main(['pr', 'claim', '8']) == 0
    assert 'worktree not adopted: worktree has unrecorded changes' in capsys.readouterr().err
    vcs.responses['worktrees'] = Result(2, reason='git.worktrees: could not run')
    assert main(['pr', 'claim', '8']) == 2
    assert state.read_state(root)['items']['PR-8']['pr'] == 'acme/widget#8'


def test_claim_refuses_pr_already_raised_today(case):
    from wuwei.__main__ import main
    root, _, _, _, _ = case
    state._write_state(lambda data: (data['items'].update(A={'pr': REF}),
                      data['approved_items'].append('A')), root, reserved=False)
    before = state.read_state(root)
    assert main(['pr', 'claim', REF, '--item', 'A']) == 1
    assert state.read_state(root) == before


def test_claim_refuses_unapproved_item_and_unreadable_pr(case):
    from wuwei.__main__ import main
    root, host, _, _, _ = case
    state._write_state(lambda data: data['items'].update(A={}), root, reserved=False)
    assert main(['pr', 'claim', REF, '--item', 'A']) == 1
    state._write_state(lambda data: data['approved_items'].append('A'), root, reserved=False)
    host.results['pr'] = Result(2, reason='offline')
    assert main(['pr', 'claim', REF, '--item', 'A']) == 2
    assert 'pr' not in state.read_state(root)['items']['A']


def test_claim_refuses_conflicting_link_without_state_change(case):
    from wuwei.__main__ import main
    root, host, _, _, _ = case
    state._write_state(lambda data: (data['items'].update(A={'pr': 'acme/widget#8'}, B={}),
                      data['approved_items'].extend(['A', 'B'])), root, reserved=False)
    before = state.read_state(root)
    assert main(['pr', 'claim', REF, '--item', 'A']) == 1
    assert state.read_state(root) == before
    state._write_state(lambda data: data['items']['A'].update(pr=REF), root, reserved=False)
    before = state.read_state(root)
    assert main(['pr', 'claim', REF, '--item', 'B']) == 1
    assert state.read_state(root) == before


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


@pytest.mark.parametrize('approved', [True, False])
@pytest.mark.parametrize('solo', [False, True])
def test_raise_checks_gates_then_requests_recent_authors(case, monkeypatch, approved, solo):
    from wuwei import dispatch, shepherd
    tracker_calls = []
    monkeypatch.setattr(dispatch, 'tracker_call', lambda *args: tracker_calls.append(args))
    root, host, _, _, vcs = case
    tree = root / 'item-tree'
    tree.mkdir()
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00Z')
    vcs.responses['repo_context'] = Result(0, {'common_dir': str(root / 'repo.git')})
    vcs.responses.update(identity=Result(0, {'name': 'Builder', 'email': 'builder@example.test',
                                             'author': {'name': 'Builder', 'email': 'builder@example.test'},
                                             'committer': {'name': 'Builder', 'email': 'builder@example.test'}}),
                         head=Result(0, {'sha': SHA}),
                         branch=Result(0, {'name': 'feature'}),
                         merge_base=Result(0, {'sha': 'b' * 40}),
                         diff_stat=Result(0, [{'path': 'src/app.py', 'additions': 1, 'deletions': 0}]))
    host.results['create_pr'] = Result(0, {'number': 7, 'url': 'https://github.com/acme/widget/pull/7'})
    if solo:
        vcs.responses['authorship'] = Result(0, [])
        host.results['request_reviewers'] = Result(0, {'requested': ['lead']})
    monkeypatch.setattr('wuwei.guards.pr.gate_check', lambda *a, **kw: (0, ''))
    state._write_state(lambda data: (data['items'].update({'ITEM-1': {'worktree': str(tree)}}),
                      data['approved_items'].extend(['ITEM-1'] if approved else [])), root, reserved=False)
    if not approved:
        assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
        assert not any(name == 'create_pr' for name, _, _ in host.calls)
        assert tracker_calls == []
        return
    for phase in ('implement', 'gate', 'fix', 'delta'):
        state.transition('ITEM-1', phase, root)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert state.read_state(root)['items']['ITEM-1']['phase'] == 'raised'
    assert tracker_calls == [('ITEM-1', 'in_review', root)]
    expected_reviewers = ['lead'] if solo else ['alice', 'bob', 'lead']
    assert state.read_state(root)['pr_reviewers'][REF] == expected_reviewers
    assert all(args[0] == str(tree) for name, args in vcs.calls
               if name in ('head', 'identity', 'merge_base', 'diff_stat', 'authorship', 'branch'))
    assert ('request_reviewers', (REF, expected_reviewers), root) in host.calls
    assert not any(name == 'post' for name, _ in case[3].calls)


def solo_raise(case, monkeypatch, minimum=0):
    from wuwei import dispatch
    monkeypatch.setattr(dispatch, 'tracker_call', lambda *args: None)
    root, host, _, _, vcs = case
    config_path = root / '.wuwei/config.toml'
    config_path.write_text(config_path.read_text().replace(
        'lead_login = "lead"', f'lead_login = ""\nmin_reviewers = {minimum}'))
    tree = root / 'item-tree'
    tree.mkdir()
    identity = {'name': 'Builder', 'email': 'builder@example.test'}
    vcs.responses.update(repo_context=Result(0, {'common_dir': str(root / 'repo.git')}),
                         identity=Result(0, {**identity, 'author': identity, 'committer': identity}),
                         head=Result(0, {'sha': SHA}), branch=Result(0, {'name': 'feature'}),
                         merge_base=Result(0, {'sha': 'b' * 40}),
                         diff_stat=Result(0, [{'path': 'src/app.py', 'additions': 1, 'deletions': 0}]),
                         authorship=Result(0, [{'email': 'builder@example.test', 'commits': 5}]))
    host.results['create_pr'] = Result(0, {'number': 7, 'url': 'https://github.com/acme/widget/pull/7'})
    host.results['request_reviewers'] = Result(2, reason='empty reviewer list')
    monkeypatch.setattr('wuwei.guards.pr.gate_check', lambda *a, **kw: (0, ''))
    state._write_state(lambda data: (data['items'].update({'ITEM-1': {'worktree': str(tree)}}),
                      data['approved_items'].append('ITEM-1')), root, reserved=False)
    return root, host


def test_solo_owner_raise_requests_no_reviewer(case, monkeypatch):
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert state.read_state(root)['pr_reviewers'][REF] == []
    assert not any(name == 'request_reviewers' for name, _, _ in host.calls)


@pytest.mark.parametrize('adapter,moved,printed', [
    ('github', Result(1, reason='ITEM-1 not moved to In Review: missing'), True),
    ('github', Result(0), False),
    ('none', Result(2, reason='tracker adapter is none'), False)])
def test_raise_prints_the_tracker_reason(case, monkeypatch, capsys, adapter, moved, printed):
    """#670: pr raise names why the in-review move failed; its exit and stdout stay."""
    from wuwei import dispatch, shepherd
    root, _ = solo_raise(case, monkeypatch)
    monkeypatch.setattr(dispatch, 'tracker_call', lambda *args: moved)
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace(
        'review_bot = "greptile"', f'review_bot = "greptile"\ntracker = "{adapter}"'))
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    out, err = capsys.readouterr()
    assert REF in out and 'tracker:' not in out
    assert ('tracker: ITEM-1 not moved to In Review: missing\n' in err) is printed
    assert ('tracker:' in err) is printed


def test_raise_humanizes_title_and_body(case, monkeypatch, capsys):
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch)
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[outward]\nhumanize_strict = true\n')
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'We delve into it.', 'ITEM-1') == 1
    assert 'stock-word' in capsys.readouterr().out
    assert not any(name == 'create_pr' for name, _, _ in host.calls)


def test_owner_handle_case_differs_from_code_host_login(case, monkeypatch, capsys):
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch, minimum=1)
    host.author_login = lambda repo, email, root=None: Result(0, {'login': 'Builder'})
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert 'reviewers: none (solo)' in capsys.readouterr().out
    assert state.read_state(root)['pr_reviewers'][REF] == []


def test_single_author_raises_solo_on_defaults(case, monkeypatch, capsys):
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch, minimum=1)
    config_path = root / '.wuwei/config.toml'
    config_path.write_text(config_path.read_text().replace('lead_login = ""', 'lead_login = "builder"'))
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    out = capsys.readouterr().out
    assert REF in out and 'reviewers: none (solo)' in out
    assert state.read_state(root)['pr_reviewers'][REF] == []
    assert not any(name == 'request_reviewers' for name, _, _ in host.calls)


def test_empty_code_host_login_raises_solo(case, monkeypatch, capsys):
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch)
    host.author_login = lambda repo, email, root=None: Result(0, {'login': ''})
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert 'reviewers: none (solo)' in capsys.readouterr().out
    assert unresolved_events(root) == [{'repo': 'acme/widget', 'author': 'builder'}]


def test_solo_ping_requests_and_posts_nothing(case, capsys):
    from wuwei import shepherd
    root, host, _, chat, _ = case
    host.results['threads'].data['comments'] = [{'id': 1, 'author': 'review-bot', 'is_bot': True,
        'body': 'Confidence Score: 5/5 /commit/' + SHA,
        'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}]
    state._write_state(lambda data: data.update(pr_reviewers={REF: []}), root, reserved=False)
    assert shepherd.post_review_request(root, REF) == 0
    assert 'reviewers: none (solo)' in capsys.readouterr().out
    assert not any(name == 'request_reviewers' for name, _, _ in host.calls)
    assert not chat.calls
    assert 'channel_posts' not in state.read_state(root)


def test_raise_refuses_item_already_linked_before_creating_pr(case):
    from wuwei import shepherd
    root, host, _, _, _ = case
    state._write_state(lambda data: (data['items'].update(A={'pr': 'acme/widget#8'}),
                      data['approved_items'].append('A')), root, reserved=False)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'A') == 1
    assert not any(name == 'create_pr' for name, _, _ in host.calls)


def test_raise_refuses_failed_gate_without_creating(case, monkeypatch):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    vcs.responses['head'] = Result(0, {'sha': SHA})
    monkeypatch.setattr('wuwei.guards.pr.gate_check', lambda *a, **kw: (1, 'gate failed'))
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
    assert not any(name == 'create_pr' for name, _, _ in host.calls)


def test_raise_checks_item_worktree_head(case, monkeypatch):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    tree = root / 'item-tree'
    tree.mkdir()
    state._write_state(lambda data: (data['items'].update({'ITEM-1': {'worktree': str(tree)}}),
                       data['approved_items'].append('ITEM-1')), root, reserved=False)
    vcs.responses['repo_context'] = Result(0, {'common_dir': str(root / 'repo.git')})
    vcs.responses['head'] = Result(0, {'sha': SHA})
    observed = []
    monkeypatch.setattr('wuwei.guards.pr.gate_check',
                        lambda _, path, __, **kw: (observed.append((path, kw['sha'])) or 1, 'stop'))
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
    assert observed == [(tree, SHA)]
    assert ('head', (str(tree),)) in vcs.calls


def test_raise_refuses_worktree_from_another_repository(case, capsys):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    tree = root / 'other-repo'
    tree.mkdir()
    state._write_state(lambda data: (data['items'].update({'ITEM-1': {'worktree': str(tree)}}),
                       data['approved_items'].append('ITEM-1')), root, reserved=False)
    vcs.responses['repo_context'] = lambda path, *_: Result(0, {
        'common_dir': str(root / ('other.git' if path == str(tree) else 'repo.git'))})

    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
    assert 'item worktree does not belong to the raised repository' in capsys.readouterr().out
    assert not any(name == 'head' for name, _ in vcs.calls)
    assert not any(name == 'create_pr' for name, _, _ in host.calls)


def test_minimum_one_reviewer_can_be_lead(case):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    vcs.responses['authorship'] = Result(0, [])
    assert shepherd.select_reviewers(root, REF) == ['lead']
    vcs.responses['authorship'] = Result(0, [{'email': 'alice@example.test', 'commits': 1}])
    lines = []
    assert shepherd.select_reviewers(root, REF, explain=lines) == ['alice', 'lead']
    assert lines == ['window: all history', 'alice 1: src/app.py 1 (selected)',
                     'lead: shepherd.lead_login (selected)']


def test_zero_reviewers_is_solo(case, capsys):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    vcs.responses['authorship'] = Result(0, [])
    config_path = root / '.wuwei/config.toml'
    config_path.write_text(config_path.read_text().replace('lead_login = "lead"', 'lead_login = ""'))
    assert shepherd.select_reviewers(root, REF) == []


def test_configured_minimum_two_requires_two(case):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    vcs.responses['authorship'] = Result(0, [])
    config_path = root / '.wuwei/config.toml'
    config_path.write_text(config_path.read_text().replace('lead_login = "lead"',
                                                'lead_login = "lead"\nmin_reviewers = 2'))
    with pytest.raises(shepherd.merge.Refused, match='shepherd.min_reviewers') as refused:
        shepherd.select_reviewers(root, REF)
    assert 'shepherd.min_reviewers 0' in str(refused.value) and 'shepherd.reviewers' in str(refused.value)
    assert 'no setting lowers it' not in str(refused.value)


def unresolved_events(root):
    from wuwei import watch
    return [row['payload'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == 'reviewer.unresolved']


def test_history_reviewers_need_no_authors_table(case):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    config_path = root / '.wuwei/config.toml'
    text = config_path.read_text()
    config_path.write_text(text.replace('"alice@example.test" = { login = "alice", mention = "UALICE" }\n', '')
                           .replace('"bob@example.test" = { login = "bob", mention = "UBOB" }\n', ''))
    history = [{'email': 'alice@example.test', 'commits': 5}, {'email': 'bob@example.test', 'commits': 4},
               {'email': 'carol@example.test', 'commits': 1}]
    vcs.responses['authorship'] = Result(0, history)
    assert shepherd.select_reviewers(root, REF) == ['alice', 'bob', 'lead']
    history[2]['commits'] = 3
    assert shepherd.select_reviewers(root, REF) == ['alice', 'bob', 'carol', 'lead']


@pytest.mark.parametrize('answer', [
    Result(2, reason='author login unavailable'),
    Result(0, {'login': ''}),
    Result(2, reason='github.author_login: could not run: invalid author email'),
])
def test_unresolved_author_is_skipped_once(case, answer):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    asked = []
    known = host.author_login
    host.author_login = lambda repo, email, root=None: (asked.append(email), answer if email ==
                                                        'missing@example.test' else known(repo, email))[1]
    vcs.responses['authorship'] = Result(0, [{'email': 'alice@example.test', 'commits': 4},
                                             {'email': 'missing@example.test', 'commits': 3}])
    assert shepherd.select_reviewers(root, REF) == ['alice', 'lead']
    assert unresolved_events(root) == [{'repo': 'acme/widget', 'author': 'missing'}]
    assert state.read_state(root)['author_logins'] == {'missing@example.test': None}
    assert shepherd.select_reviewers(root, REF) == ['alice', 'lead']
    assert asked.count('missing@example.test') == 1
    assert len(unresolved_events(root)) == 1


@pytest.mark.parametrize('answer', [Result(2, reason='offline'), Result(0, {'message': 'Not Found'})])
def test_unreachable_code_host_fails_closed(case, answer):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    host.author_login = lambda repo, email, root=None: answer
    vcs.responses['authorship'] = Result(0, [{'email': 'missing@example.test', 'commits': 3}])
    with pytest.raises(ValueError):
        shepherd.select_reviewers(root, REF)
    assert unresolved_events(root) == []


def test_author_login_without_a_reason_names_the_next_step(case):
    # #362: a code host failure with no reason still says what to run.
    from wuwei import shepherd
    root, host, _, _, vcs = case
    host.author_login = lambda repo, email, root=None: Result(2)
    vcs.responses['authorship'] = Result(0, [{'email': 'missing@example.test', 'commits': 3}])
    with pytest.raises(ValueError, match='^author login unmeasured; retry; if it repeats, run bin/wuwei '
                                         'doctor, which tests the code host adapter$'):
        shepherd.select_reviewers(root, REF)


def test_only_excluded_paths_names_the_reviewers_override(case):
    # #362: every changed path matches shepherd.source_exclude and no override is set.
    from wuwei import merge, shepherd
    root, host, _, _, _ = case
    configure(root, 'review_channel = "CREVIEW"', 'review_channel = "CREVIEW"\nsource_exclude = ["docs/*"]')
    host.results['files'] = Result(0, [{'path': 'docs/a.md'}])
    with pytest.raises(merge.Refused, match=r"""^no changed source paths for reviewer selection; run bin/wuwei config set shepherd.reviewers '\["login"\]'$"""):
        shepherd.select_reviewers(root, REF)


def configure(root, old, new):
    config_path = root / '.wuwei/config.toml'
    config_path.write_text(config_path.read_text().replace(old, new, 1))


BOT_CLEAR = {'id': 1, 'author': 'review-bot', 'is_bot': True, 'body': 'Confidence Score: 5/5 /commit/' + SHA,
             'created_at': '2026-09-29T10:00:00Z', 'updated_at': '2026-09-29T10:00:00Z'}


def test_owner_override_replaces_history_and_lead(case):
    from wuwei import shepherd
    root, host, _, chat, vcs = case
    configure(root, 'lead_login = "lead"', 'lead_login = "lead"\nreviewers = ["pat-dev"]')
    configure(root, '[shepherd.authors]', '[shepherd.authors]\n"pat@example.test" = { login = "pat-dev", mention = "UPAT" }')
    host.results['threads'].data['comments'] = [BOT_CLEAR]
    host.results['request_reviewers'] = Result(0, {'requested': ['pat-dev']})
    assert shepherd.select_reviewers(root, REF) == ['pat-dev']
    assert not any(name == 'authorship' for name, _ in vcs.calls)
    assert not any(name == 'author_login' for name, _, _ in host.calls)
    assert shepherd.post_review_request(root, REF) == 0
    assert ('request_reviewers', (REF, ['pat-dev']), root) in host.calls


def test_repository_override_wins_and_drops_the_author(case):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    configure(root, 'lead_login = "lead"', 'lead_login = "lead"\nreviewers = ["pat-dev"]')
    configure(root, 'bot_login = "review-bot"', 'bot_login = "review-bot"\n[repos.shepherd]\nreviewers = ["sam-dev", "Builder"]')
    host.results['pr'].data['author'] = 'builder'
    assert shepherd.select_reviewers(root, REF) == ['sam-dev']
    host.results['files'] = Result(0, [{'path': 'specs/x.md'}])
    assert shepherd.select_reviewers(root, REF) == ['sam-dev']


@pytest.mark.parametrize('excluded,expected', [('Alice', ['bob', 'lead']), ('lead', ['alice', 'bob'])])
def test_excluded_logins_leave_history_and_lead(case, excluded, expected):
    from wuwei import shepherd
    root, _, _, _, _ = case
    configure(root, 'lead_login = "lead"', f'lead_login = "lead"\nreviewers_exclude = ["{excluded}"]')
    assert shepherd.select_reviewers(root, REF) == expected


def test_reviewers_command_explains_the_selection(case, capsys):
    from wuwei.__main__ import main
    root, host, _, _, vcs = case
    host.results['files'] = Result(0, [{'path': 'src/app.py'}, {'path': 'src/util.py'}])
    host.results['pr'].data['changed_files'] = 2
    per_path = {'src/app.py': {'alice': 4, 'bob': 3, 'missing': 1}, 'src/util.py': {'alice': 3, 'bob': 2}}

    def authorship(repo, branch, paths, days):
        counts = {}
        for path in paths:
            for name, commits in per_path[path].items():
                counts[name] = counts.get(name, 0) + commits
        return Result(0, [{'email': f'{name}@example.test', 'commits': n} for name, n in counts.items()])
    vcs.responses['authorship'] = authorship
    assert main(['pr', 'reviewers', REF, '--explain']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ['window: 90 days', 'alice 7: src/app.py 4, src/util.py 3 (selected)',
                     'bob 5: src/app.py 3, src/util.py 2 (selected)',
                     'lead: shepherd.lead_login (selected)', 'unresolved: missing',
                     'reviewers: alice bob lead']
    assert main(['pr', 'reviewers', REF]) == 0
    assert capsys.readouterr().out.splitlines() == ['reviewers: alice bob lead']
    configure(root, 'lead_login = "lead"', 'lead_login = "lead"\nreviewers_exclude = ["alice", "bob", "lead"]')
    assert main(['pr', 'reviewers', REF]) == 0
    assert capsys.readouterr().out.splitlines() == ['reviewers: none (solo)']
    configure(root, 'reviewers_exclude = ["alice", "bob", "lead"]', 'min_reviewers = 4')
    assert main(['pr', 'reviewers', REF]) == 1
    assert 'shepherd.min_reviewers' in capsys.readouterr().out
    host.results['pr'] = Result(2, reason='offline')
    assert main(['pr', 'reviewers', REF]) == 2
    assert 'offline' in capsys.readouterr().out


def test_unmapped_author_falls_back_to_code_host_login(case):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    vcs.responses['authorship'] = Result(0, [
        {'email': 'alice@example.test', 'commits': 4},
        {'email': 'Carol@example.test', 'commits': 3},
    ])
    assert shepherd.select_reviewers(root, REF) == ['alice', 'carol', 'lead']


def test_unmapped_owner_email_resolves_and_is_excluded(case):
    from wuwei import shepherd
    root, host, _, _, vcs = case
    host.results['pr'].data['author'] = 'builder'
    vcs.responses['authorship'] = Result(0, [{'email': 'builder@example.test', 'commits': 9}])
    assert shepherd.select_reviewers(root, REF) == ['lead']


def test_raise_none_code_host_has_actionable_error(case, capsys):
    from wuwei import shepherd
    root, _, _, _, _ = case
    config_path = root / '.wuwei/config.toml'
    config_path.write_text(config_path.read_text().replace('[adapters]',
                                                 '[adapters]\ncode_host = "none"'))
    state._write_state(lambda data: (data['items'].update({'ITEM-1': {'worktree': str(root / 'repo')}}),
                       data['approved_items'].append('ITEM-1')), root, reserved=False)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 2
    assert 'code_host adapter is none; configure github' in capsys.readouterr().out


def test_raise_unmeasured_names_vcs_adapter(case, capsys):
    from wuwei import shepherd
    root, _, _, _, vcs = case
    state._write_state(lambda data: (data['items'].update({'ITEM-1': {'worktree': str(root / 'repo')}}),
                       data['approved_items'].append('ITEM-1')), root, reserved=False)
    vcs.responses['head'] = Result(2, reason='unavailable')
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 2
    assert 'adapters.vcs' in capsys.readouterr().out


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
    card = 'publish: bin/wuwei merge x on y is a merge; the owner decides: bin/wuwei decision show D-1 --widget'
    monkeypatch.setattr('wuwei.merge.execute', lambda ref, root=None: Result(1, reason=card))
    assert pr_actions.act(root, REF) == 1
    # #524: the merge's own reason (the card or the owner's command), never a generic owner wall.
    assert capsys.readouterr().out == f'{REF}: {card}\n'


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


def test_missing_branch_protection_reads_rulesets_for_fallback(monkeypatch):
    # An empty required_checks list triggers shepherd's default-branch and config fallback.
    from adapters.code_host import github
    from fakes.replay import install_replay
    install_replay(monkeypatch, 'gh', [{'exit': 1, 'stderr': 'gh: Branch not protected (HTTP 404)'},
                                       {'stdout': '[[]]'}, {'stdout': '{"allow_squash_merge": true}'}])
    result = github.protection('acme/widget', 'feature-base')
    assert result.exit == 0
    assert result.data['required_checks'] == [] and result.data['classic'] is False


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


@pytest.mark.parametrize('gates,body', [
    ({'tier': 'light', 'computed': 'light', 'reasons': ['docs/guide.md'], 'roles': ['quality']},
     'Body\n\nReview tier: light (quality)\n\nchecks: none configured'),
    ({}, 'Body\n\nchecks: none configured'),  # #600: no fast checks, the CLI writes the line
])
def test_raise_body_names_the_review_tier(case, monkeypatch, gates, body):
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch)
    state._write_state(lambda data: data['items']['ITEM-1'].update(gates=gates), root, reserved=False)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    [args] = [args for name, args, _ in host.calls if name == 'create_pr']
    assert args[0]['body'] == body
    assert not any(name == 'label' for name, _, _ in host.calls)



def test_raise_records_owner_merge_on_the_pr(case, monkeypatch):
    # #678: a flagged item's PR says who keeps the merge, in the body and as a label.
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch)
    host.results['label'] = Result(0, {'labels': ['owner-merge']})
    state._write_state(lambda data: data['items']['ITEM-1'].update(owner_merge={
        'value': True, 'by': 'planner', 'at': '2026-09-29T08:00:00+00:00'}), root, reserved=False)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    [args] = [args for name, args, _ in host.calls if name == 'create_pr']
    assert args[0]['body'] == ('Body\n\nOwner merges: owner_merge set by planner on 2026-09-29'
                               '\n\nchecks: none configured')
    assert [args for name, args, _ in host.calls if name == 'label'] == [(REF, 'owner-merge', True)]


def test_raise_body_names_no_checks_once_and_only_when_none(case, monkeypatch):
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body\n\nchecks: none configured',
                             'ITEM-1') == 0
    [args] = [args for name, args, _ in host.calls if name == 'create_pr']
    assert args[0]['body'] == 'Body\n\nchecks: none configured'
    config_path = root / '.wuwei/config.toml'
    config_path.write_text(config_path.read_text().replace('path = "repo"', 'path = "repo"\nfast_checks = ["make lint"]'))
    state._write_state(lambda data: data['items']['ITEM-1'].update(pr=None), root, reserved=False)
    host.calls.clear()
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    [args] = [args for name, args, _ in host.calls if name == 'create_pr']
    assert args[0]['body'] == 'Body'

GATE_MISS = f'pre-PR gates not passed at current HEAD {SHA} for item ITEM-1: security; run the named gate for this HEAD'


def gate_miss(case, monkeypatch, posture):
    root, host = solo_raise(case, monkeypatch)
    monkeypatch.setattr('wuwei.guards.pr.gate_check', lambda *a, **kw: (1, GATE_MISS))
    if posture:
        with (root / '.wuwei/config.toml').open('a') as stream:
            stream.write(f'\n[security]\nposture = "{posture}"\n')
    return root, host


def created(host):
    return [call for call in host.calls if call[0] == 'create_pr']


def would_refuse(root):
    import json
    return [json.loads(line)['payload'] for path in root.glob('.wuwei/days/*/events.jsonl')
            for line in path.read_text().splitlines() if json.loads(line)['kind'] == 'guard.would_refuse']


def test_raise_gate_miss_warns_under_observe(case, monkeypatch, capsys):
    # #530: a missing gate verdict is a warning under observe; the PR is raised.
    from wuwei import shepherd
    root, host = gate_miss(case, monkeypatch, 'observe')
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert len(created(host)) == 1 and 'warning: ' + GATE_MISS in capsys.readouterr().err
    [event] = would_refuse(root)
    assert event['reason'] == GATE_MISS and event['level'] == 'warn'


def test_raise_gate_miss_is_a_card_under_guarded(case, monkeypatch, capsys):
    from types import SimpleNamespace
    from wuwei import integrity, shepherd
    from wuwei.commands import decision
    root, host = gate_miss(case, monkeypatch, None)
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
    out = capsys.readouterr().out
    assert not created(host) and 'decision show D-1' in out and 'security' in out
    assert 'host terminal' not in out
    monkeypatch.setattr(integrity, '_host_confirm', lambda *args, **kwargs: True)
    assert decision.owner_outcome(SimpleNamespace(id='D-1', option='Allow once'), root=root) == (0, 'once')
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert len(created(host)) == 1 and state.read_state(root)['grants']['D-1']['spent'] is True


def test_raise_gate_miss_refuses_under_strict(case, monkeypatch, capsys):
    from wuwei import shepherd
    root, host = gate_miss(case, monkeypatch, 'strict')
    assert shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 1
    assert capsys.readouterr().out.strip() == GATE_MISS and not created(host)
    assert 'grants' not in state.read_state(root) or not state.read_state(root)['grants']


@pytest.mark.parametrize('where', ['.', 'docs'])
def test_raise_from_any_directory_in_the_workspace(case, monkeypatch, where):
    # #534: pr raise reads the recorded worktree, whatever the caller's directory.
    from wuwei import shepherd
    root, host = solo_raise(case, monkeypatch)
    (root / where).mkdir(exist_ok=True)
    monkeypatch.chdir(root / where)
    monkeypatch.delenv('WUWEI_WORKSPACE')
    assert shepherd.raise_pr(workspace.find_workspace(), 'acme/widget', 'main', 'Feature', 'Body', 'ITEM-1') == 0
    assert created(host)[0][1][0]['head'] == 'feature'
