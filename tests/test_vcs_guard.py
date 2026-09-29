"""Read-only Git context operations use recorded output, never a real push."""

from pathlib import Path
import subprocess

import pytest

from fakes.replay import install_replay
from test_vcs import adapter
from test_commit_push import OWNER, SHA


def context_steps(tmp_path):
    return [{'stdout': str(tmp_path / '.git') + '\n'},
            {'stdout': str(tmp_path / '.git') + '\n'},
            {'stdout': 'Builder <builder@example.test> 1790596800 +0200\n'},
            {'stdout': 'Builder <builder@example.test> 1790596800 +0200\n'}]


def test_commit_context(tmp_path, monkeypatch):
    assert hasattr(adapter(), 'commit_context'), 'commit context port is missing'
    calls = install_replay(monkeypatch, 'git', context_steps(tmp_path))
    result = adapter().commit_context(str(tmp_path), {}, {})
    assert result.exit == 0, result.reason
    assert result.data == {'path': str(tmp_path / '.git'), 'common_dir': str(tmp_path / '.git'),
                           'author': OWNER, 'committer': OWNER}
    assert len(calls) == 4


def test_context_applies_environment_and_config_without_shell(tmp_path, monkeypatch):
    assert hasattr(adapter(), 'commit_context'), 'commit context port is missing'
    steps = context_steps(tmp_path)
    calls = []
    def run(argv, **kwargs):
        assert kwargs['env']['GIT_AUTHOR_EMAIL'] == 'override@example.test'
        assert kwargs['env']['GIT_DIR'] == 'selected/.git'
        assert kwargs['cwd'] == str(tmp_path)
        assert argv[:3] == ['git', '-c', 'user.name=Builder']
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, steps[len(calls)-1]['stdout'].encode(), b'')
    monkeypatch.setattr(subprocess, 'run', run)
    result = adapter().commit_context(str(tmp_path), {'user.name': 'Builder'},
                                     {'GIT_DIR': 'selected/.git', 'GIT_AUTHOR_EMAIL': 'override@example.test'})
    assert result.exit == 0, result.reason


@pytest.mark.parametrize('steps', [[{'exit': 128}], [{'stdout': ''}],
                                  [{'stdout': 'relative\n'}]])
def test_bad_context_fails_closed(tmp_path, monkeypatch, steps):
    assert hasattr(adapter(), 'commit_context'), 'commit context port is missing'
    install_replay(monkeypatch, 'git', steps)
    result = adapter().commit_context(str(tmp_path), {}, {})
    assert result.exit == 2 and result.reason


def push_steps(tmp_path, mirror='false', tags='false', configured=''):
    return [
        {'stdout': SHA + '\0Builder\0builder@example.test\0Builder\0builder@example.test\n'},
        {'stdout': 'feature\n'},
        {'stdout': tags + '\n'}, {'stdout': mirror + '\n'},
        {'stdout': configured, 'exit': 0 if configured else 1}, {'stdout': ''},
    ]


@pytest.mark.parametrize('refs,destination,mirror', [
    (['HEAD:refs/heads/topic'], 'refs/heads/topic', 'false'),
    (['HEAD:refs/heads/main'], 'refs/heads/main', 'false'),
    (['feature'], 'refs/heads/feature', 'false'),
    (['refs/heads/feature'], 'refs/heads/feature', 'false'),
    (['feature'], 'refs/heads/feature', 'true'),
])
def test_push_context(tmp_path, monkeypatch, refs, destination, mirror):
    calls = install_replay(monkeypatch, 'git', push_steps(tmp_path, mirror))
    result = adapter().push_context(str(tmp_path), 'origin', refs)
    assert result.exit == 0, result.reason
    assert result.data == {'head': {'sha': SHA, 'author': OWNER, 'committer': OWNER},
                           'updates': [{'source': SHA, 'destination': destination}],
                           'force': mirror == 'true', 'remote': 'origin'}
    assert any(call[-2:] == ['check-ref-format', destination] for call in calls)
    assert any(call[-4:] == ['config', '--type=bool', '--get', 'push.followtags'] for call in calls)


@pytest.mark.parametrize('refs', [[], ['HEAD:refs/tags/v1'], [':feature'], [':'],
                                  ['other:feature'], ['HEAD:topic']])
def test_ambiguous_push_context_fails_closed(tmp_path, monkeypatch, refs):
    install_replay(monkeypatch, 'git', push_steps(tmp_path))
    result = adapter().push_context(str(tmp_path), 'origin', refs)
    assert result.exit == 2 and result.reason
    if not refs:
        assert 'explicit' in result.reason


def test_push_ref_validation_uses_git(tmp_path, monkeypatch):
    steps = push_steps(tmp_path)
    steps[-1] = {'exit': 1}
    install_replay(monkeypatch, 'git', steps)
    assert adapter().push_context(str(tmp_path), 'origin', ['HEAD:refs/heads/bad.lock/branch']).exit == 2



def test_configured_context_ignores_inherited_repository_and_config(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv('GIT_DIR', 'unrelated/.git')
    monkeypatch.setenv('GIT_CONFIG_PARAMETERS', "'user.email'='wrong@example.test'")
    steps = context_steps(tmp_path)
    calls = []
    def run(argv, **kwargs):
        assert 'GIT_DIR' not in kwargs['env']
        assert 'GIT_CONFIG_PARAMETERS' not in kwargs['env']
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, steps[len(calls)-1]['stdout'].encode(), b'')
    monkeypatch.setattr(subprocess, 'run', run)
    assert adapter().commit_context(str(tmp_path), {}, {}).exit == 0


def test_guard_reads_ignore_replacement_objects(tmp_path, monkeypatch):
    from fakes.replay import replay
    run = replay(push_steps(tmp_path), 'git')
    def checked(argv, **kwargs):
        assert kwargs['env'].get('GIT_NO_REPLACE_OBJECTS') == '1'
        return run(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'run', checked)
    assert adapter().push_context(str(tmp_path), 'origin', ['feature']).exit == 0


def test_selected_repository_reads_use_git_directory(tmp_path, monkeypatch):
    calls = install_replay(monkeypatch, 'git', context_steps(tmp_path))
    assert adapter().commit_context(str(tmp_path), {}, {'GIT_DIR': 'other/.git'}).exit == 0
    assert calls[0][-2:] == ['rev-parse', '--absolute-git-dir']


@pytest.mark.parametrize('refs,config', [
    (['feature'], 'remote.origin.push\nrefs/heads/feature:refs/heads/main\0'),
    (['HEAD:topic'], ''),
])
def test_ambiguous_unqualified_destinations_are_not_guessed(tmp_path, monkeypatch, refs, config):
    install_replay(monkeypatch, 'git', push_steps(tmp_path, configured=config))
    assert adapter().push_context(str(tmp_path), 'origin', refs).exit == 2


@pytest.mark.parametrize('remote_sha,tracking', [(None, True), (None, False), ('c'*40, True), ('0'*40, False)])
def test_pushed_range_uses_author_and_committer(tmp_path, monkeypatch, remote_sha, tracking):
    assert hasattr(adapter(), 'push_commits')
    base = 'c'*40
    steps = []
    if remote_sha is None:
        steps.append({'stdout': base + '\n'} if tracking else {'exit': 1})
    if remote_sha == '0'*40 or remote_sha is None and not tracking:
        steps.append({'stdout': base + '\n'})
    steps.append({'stdout': SHA + '\0Builder\0builder@example.test\0Other\0other@example.test\0'})
    calls = install_replay(monkeypatch, 'git', steps)
    result = adapter().push_commits(str(tmp_path), 'origin', 'refs/heads/feature', SHA, remote_sha, 'main')
    assert result.exit == 0, result.reason
    assert result.data['commits'][0]['committer']['name'] == 'Other'
    assert calls[-1][-2] == base + '..' + SHA
    if remote_sha is None:
        assert 'refs/remotes/origin/feature^{commit}' in calls[0]
    if not tracking:
        assert any(call[-1] == 'refs/remotes/origin/main' for call in calls)


@pytest.mark.parametrize('index,failure,reason,action', [
    (1, {'exit': 1}, 'detached HEAD', 'check out a branch'),
    (0, {'exit': 128}, 'HEAD', 'create a commit'),
    (1, {'exit': 128}, 'symbolic-ref', 'check repository state'),
    (2, {'exit': 128}, 'config', 'check repository state'),
    (5, {'exit': 1}, 'check-ref-format', 'refs/heads/'),
])
def test_push_context_failures_explain_recovery(tmp_path, monkeypatch, index, failure, reason, action):
    steps = push_steps(tmp_path)
    steps[index] = failure
    install_replay(monkeypatch, 'git', steps)
    result = adapter().push_context(str(tmp_path), 'origin', ['HEAD:refs/heads/feature'])
    assert result.exit == 2
    assert reason in result.reason
    assert action in result.reason


@pytest.mark.parametrize('failure', [FileNotFoundError(), subprocess.TimeoutExpired('git', 30)])
def test_push_context_tool_failure_explains_recovery(tmp_path, monkeypatch, failure):
    def run(*args, **kwargs):
        raise failure
    monkeypatch.setattr(subprocess, 'run', run)
    result = adapter().push_context(str(tmp_path), 'origin', ['feature'])
    assert result.exit == 2
    assert 'HEAD' in result.reason and 'check' in result.reason
