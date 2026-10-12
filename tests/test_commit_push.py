"""The commit and push policy pr act --run applies: identity and push shape."""

import importlib
import os

import pytest

from wuwei.registry import Result
from fakes.vcs import Fake


OWNER = {'name': 'Builder', 'email': 'builder@example.test'}
OTHER = {'name': 'Other', 'email': 'other@example.test'}
SHA = 'a' * 40
OLD = 'b' * 40


def set_fast_checks(root, checks):
    """Seed trusted or malformed on-disk evidence for guard policy tables."""
    from wuwei import state
    state._write_state(lambda data: data.update(fast_checks=checks), root)


def guard():
    return importlib.import_module('wuwei.commit_push')


def push(root, refs=('feature',)):
    """The push policy for git push origin <refs> in the fixture repository; 2 when unmeasured."""
    policy = guard()
    try:
        repo, actual, vcs, early = policy.context(root / 'repo', {}, {}, root, push=('origin', list(refs)))
        return policy.push_check(repo, actual, policy.data(early), root, vcs)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return 2, str(exc)


@pytest.mark.parametrize('author,committer,head,code,reason', [
    (OWNER, OWNER, None, 0, ''),
    (OTHER, OTHER, None, 1, 'GIT_AUTHOR_IDENT'),
    (OWNER, OTHER, None, 1, 'GIT_COMMITTER_IDENT'),
    (OWNER, OWNER, {'author': OWNER, 'committer': OWNER}, 0, ''),
    (OTHER, OWNER, {'author': OTHER, 'committer': OTHER}, 1, 'GIT_AUTHOR_IDENT'),
    (OWNER, OTHER, {'author': OTHER, 'committer': OTHER}, 1, 'GIT_COMMITTER_IDENT'),
    (OWNER, OWNER, {'author': OTHER, 'committer': OWNER}, 1, 'HEAD'),
    (OWNER, OWNER, {'author': OWNER, 'committer': OTHER}, 1, 'HEAD'),
    ({}, OWNER, None, 2, 'identity'),
    (OWNER, OWNER, {}, 2, 'identity'),
])
def test_source_harness_refusals_in_order(author, committer, head, code, reason):
    result = guard().identity_check(OWNER, {'author': author, 'committer': committer}, head)
    assert result[0] == code
    assert reason in result[1]


@pytest.mark.parametrize('expected', [{}, {'name': '', 'email': 'x'}, None])
def test_missing_expected_identity_fails_closed(expected):
    assert guard().identity_check(expected, {'author': OWNER, 'committer': OWNER})[0] == 2


@pytest.fixture
def workspace_case(tmp_path, monkeypatch):
    from wuwei import registry, state

    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / 'repo').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('''
[[repos]]
name = "example/project"
path = "repo"
default_branch = "main"
fast_checks = ["unit"]
identity = {name = "Builder", email = "builder@example.test"}
[spec]
engine = "none"
''')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    from fakes.integrity import seed
    seed(tmp_path)
    set_fast_checks(tmp_path, {'example/project': {'unit': {'sha': SHA, 'exit': 0}}})
    context = {'path': str(tmp_path / 'repo'), 'common_dir': str(tmp_path / 'repo/.git'),
               'author': dict(OWNER), 'committer': dict(OWNER)}
    push = {'head': {'sha': SHA, 'author': dict(OWNER), 'committer': dict(OWNER)},
            'updates': [{'source': SHA, 'destination': 'refs/heads/feature'}], 'force': False, 'remote': 'origin'}
    fake = Fake({'commit_context': Result(0, context), 'push_context': Result(0, push),
                 'repo_context': Result(0, {key: context[key] for key in ('path', 'common_dir')}),
                 'head': Result(0, push['head']),
                 'status': Result(0, []),  # #871 L2: a passing build leaves a clean tree
                 'push_commits': Result(0, {'commits': [push['head']]}),
                 'merge_base': Result(0, {'sha': OLD})})
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    return tmp_path, fake


@pytest.mark.parametrize('head_field', ['author', 'committer'])
def test_push_checks_head_identity(workspace_case, head_field):
    root, fake = workspace_case
    fake.results['push_context'].data['head'][head_field] = OTHER
    result = push(root)
    assert result[0] == 1 and 'HEAD' in result[1]


@pytest.mark.parametrize('change,code', [
    ({'updates': [{'source': SHA, 'destination': 'refs/heads/main'}]}, 1),
    ({'updates': [{'source': OLD, 'destination': 'refs/heads/feature'}]}, 1),
    ({'updates': [{'source': SHA, 'destination': 'refs/tags/v1'}]}, 0),  # the deploy guard's release card gates it
    ({'updates': []}, 2), ({'updates': None}, 2), ({'force': True}, 1),
    ({'head': {}}, 2), ({'force': 'false'}, 2),
])
def test_push_context_policy(workspace_case, change, code):
    root, fake = workspace_case
    fake.results['push_context'].data.update(change)
    assert push(root)[0] == code


@pytest.mark.parametrize('operation', ['commit_context', 'push_context'])
@pytest.mark.parametrize('result', [Result(2, None, 'offline'), Result(0, {}), Result(0, None)])
def test_port_errors_fail_closed(workspace_case, operation, result):
    root, fake = workspace_case
    fake.results[operation] = result
    assert push(root)[0] == 2


@pytest.mark.parametrize('settings,env', [({'user.name': 'Other'}, {}), ({}, {'GIT_DIR': 'other/.git'})])
def test_identity_free_context_refuses_overrides(workspace_case, settings, env):
    root, fake = workspace_case
    with pytest.raises(ValueError, match='identity-free'):
        guard().context(root / 'repo', settings, env, root, identity=False)
    assert not fake.calls


def test_identity_free_context_refuses_push(workspace_case):
    root, fake = workspace_case
    with pytest.raises(ValueError, match='push checks need the commit identity'):
        guard().context(root / 'repo', {}, {}, root, push=('origin', ['feature']), identity=False)
    assert not fake.calls


@pytest.mark.parametrize('kind', ['author', 'committer'])
def test_entire_pushed_range_identity(workspace_case, kind):
    root, fake = workspace_case
    commits = [{'sha': SHA, 'author': OWNER, 'committer': OWNER},
               {'sha': OLD, 'author': OWNER, 'committer': OWNER}]
    commits[1][kind] = OTHER
    fake.results['push_commits'] = Result(0, {'commits': commits})
    assert push(root)[0] == 1
    assert any(call[0] == 'push_commits' for call in fake.calls)


@pytest.mark.parametrize('result', [Result(2, None, 'unavailable'), Result(0, {}),
                                    Result(0, {'commits': [{}]})])
def test_range_read_fails_closed(workspace_case, result):
    root, fake = workspace_case
    fake.results['push_commits'] = result
    assert push(root)[0] == 2


def test_push_context_overlaps_repository_context(workspace_case):
    import threading
    root, fake = workspace_case
    barrier = threading.Barrier(2, timeout=2)
    original = fake._call
    def call(operation, args, context):
        if operation in ('commit_context', 'push_context') and not any(
                seen[0] == operation for seen in fake.calls):
            barrier.wait()
        return original(operation, args, context)
    fake._call = call
    assert push(root, ['HEAD:refs/heads/feature']) == (0, '')
    assert ('push_context', (str(root / 'repo'), 'origin', ['HEAD:refs/heads/feature']), root) in fake.calls


def test_identity_refusal_names_the_fix():
    for kind, actual in (('AUTHOR', {'author': OTHER, 'committer': OWNER}),
                         ('COMMITTER', {'author': OWNER, 'committer': OTHER})):
        code, reason = guard().identity_check(OWNER, actual)
        assert code == 1
        assert reason.startswith(f'GIT_{kind}_IDENT differs from configured identity')
        assert 'wuwei worktree add' in reason
        assert 'git config user.name Builder' in reason
        assert 'git config user.email builder@example.test' in reason
    demo = {'name': 'Demo Owner', 'email': 'demo@example.test'}
    assert "git config user.name 'Demo Owner'" in guard().identity_check(
        demo, {'author': OTHER, 'committer': demo})[1]


@pytest.mark.parametrize('identity', ['{name = "", email = ""}', '{name = "<name>", email = "<email>"}'])
def test_empty_identity_names_the_config_set(workspace_case, identity):
    # #605: an empty or malformed repos.N.identity fails with the reason and fix doctor's row
    # shows; the fix names the identity git resolves, read with no new git call.
    root, fake = workspace_case
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('{name = "Builder", email = "builder@example.test"}', identity))
    calls = len(fake.calls)
    reason, fix = guard().unset_identity({'name': '<name>', 'email': ''}, 0, OWNER)
    assert reason == 'repos.0.identity is empty or malformed'
    assert fix == "bin/wuwei config set repos.0.identity '{name = \"Builder\", email = \"builder@example.test\"}'"
    assert not any(call[0] == 'identity' for call in fake.calls[calls:])
    assert guard().unset_identity(OWNER, 0) is None
    assert guard().unset_identity({'name': '', 'email': ''}, 0, {'name': '<name>', 'email': ''})[1] == (
        "bin/wuwei config set repos.0.identity '{name = \"<name>\", email = \"<email>\"}'")


