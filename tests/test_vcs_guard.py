"""Read-only Git context operations use recorded output, never a real push."""

from pathlib import Path
import subprocess

import pytest

from fakes.replay import install_replay
from test_vcs import adapter
from test_commit_push import OWNER, SHA


def context_steps(tmp_path):
    return [{'stdout': str(tmp_path / '.git') + '\n', 'when': ['--absolute-git-dir']},
            {'stdout': str(tmp_path / '.git') + '\n', 'when': ['--git-common-dir']},
            {'stdout': 'Builder <builder@example.test> 1790596800 +0200\n', 'when': ['GIT_AUTHOR_IDENT']},
            {'stdout': 'Builder <builder@example.test> 1790596800 +0200\n', 'when': ['GIT_COMMITTER_IDENT']}]


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
    from fakes.replay import replay
    replayed = replay(context_steps(tmp_path), 'git')
    def run(argv, **kwargs):
        assert kwargs['env']['GIT_AUTHOR_EMAIL'] == 'override@example.test'
        assert kwargs['env']['GIT_DIR'] == 'selected/.git'
        assert kwargs['cwd'] == str(tmp_path)
        assert argv[:3] == ['git', '-c', 'user.name=Builder']
        return replayed(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'run', run)
    result = adapter().commit_context(str(tmp_path), {'user.name': 'Builder'},
                                     {'GIT_DIR': 'selected/.git', 'GIT_AUTHOR_EMAIL': 'override@example.test'})
    assert result.exit == 0, result.reason


@pytest.mark.parametrize('steps', [[{'exit': 128}], [{'stdout': ''}],
                                  [{'stdout': 'relative\n'}]])
def test_bad_context_fails_closed(tmp_path, monkeypatch, steps):
    assert hasattr(adapter(), 'commit_context'), 'commit context port is missing'
    install_replay(monkeypatch, 'git', steps + context_steps(tmp_path)[1:])
    result = adapter().commit_context(str(tmp_path), {}, {})
    assert result.exit == 2 and result.reason


def test_repository_read_needs_no_identity(tmp_path, monkeypatch):
    # A runner with no configured identity: git var exits 128 on any OS.
    steps = context_steps(tmp_path)[:2] + [{'exit': 128}]
    calls = install_replay(monkeypatch, 'git', steps)
    result = adapter().repo_context(str(tmp_path))
    assert result.exit == 0, result.reason
    assert result.data == {'path': str(tmp_path / '.git'), 'common_dir': str(tmp_path / '.git')}
    assert len(calls) == 2
    install_replay(monkeypatch, 'git', steps)
    assert adapter().commit_context(str(tmp_path), {}, {}).exit == 2


def push_steps(tmp_path, mirror='false', tags='false', configured=''):
    settings = f'push.followtags\n{tags}\0remote.origin.mirror\n{mirror}\0' + configured
    return [
        {'stdout': SHA + '\0Builder\0builder@example.test\0Builder\0builder@example.test\n', 'when': ['show']},
        {'stdout': 'feature\n', 'when': ['symbolic-ref']},
        {'stdout': settings, 'when': ['--get-regexp']},
        {'stdout': '', 'when': ['check-ref-format']},
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
    assert [call[-4:] for call in calls if 'config' in call] == [
        ['config', '-z', '--get-regexp', r'^(push\.followtags|remote\.origin\.(mirror|push))$']]


@pytest.mark.parametrize('settings,code,force', [
    ('', 0, False), ('remote.origin.mirror\0', 0, True), ('remote.origin.mirror\nYes\0', 0, True),
    ('remote.origin.mirror\non\0remote.origin.mirror\n0\0', 0, False),
    ('remote.origin.mirror\n2\0', 0, True), ('remote.origin.mirror\nmaybe\0', 2, None),
    ('push.followtags\nTRUE\0', 2, None), ('push.followtags\noff\0', 0, False),
])
def test_push_settings_parse_git_booleans(tmp_path, monkeypatch, settings, code, force):
    steps = push_steps(tmp_path)
    steps[2] = {'stdout': settings, 'exit': 0 if settings else 1, 'when': ['--get-regexp']}
    install_replay(monkeypatch, 'git', steps)
    result = adapter().push_context(str(tmp_path), 'origin', ['HEAD:refs/heads/feature'])
    assert result.exit == code, result.reason
    if code == 0:
        assert result.data['force'] is force


@pytest.mark.parametrize('refs,source', [(['HEAD:refs/tags/v1'], SHA), (['refs/tags/v1'], 'c' * 40)])
def test_push_context_measures_a_tag_destination(tmp_path, monkeypatch, refs, source):
    # #530: a tag push is measured, so push_check can gate it on the release grant.
    steps = push_steps(tmp_path) + [{'stdout': 'c' * 40 + '\n', 'when': ['rev-parse']}]
    install_replay(monkeypatch, 'git', steps)
    result = adapter().push_context(str(tmp_path), 'origin', refs)
    assert result.exit == 0, result.reason
    assert result.data['updates'] == [{'source': source, 'destination': 'refs/tags/v1'}]


@pytest.mark.parametrize('refs', [[], [':feature'], [':'],
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
    from fakes.replay import replay
    replayed = replay(context_steps(tmp_path), 'git')
    def run(argv, **kwargs):
        assert 'GIT_DIR' not in kwargs['env']
        assert 'GIT_CONFIG_PARAMETERS' not in kwargs['env']
        return replayed(argv, **kwargs)
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
    assert any(call[-2:] == ['rev-parse', '--absolute-git-dir'] for call in calls)


@pytest.mark.parametrize('refs,config', [
    (['feature'], 'remote.origin.push\nrefs/heads/feature:refs/heads/main\0'),
    (['feature'], 'remote.origin.push\0'),
    (['HEAD:topic'], ''),
])
def test_ambiguous_unqualified_destinations_are_not_guessed(tmp_path, monkeypatch, refs, config):
    install_replay(monkeypatch, 'git', push_steps(tmp_path, configured=config))
    assert adapter().push_context(str(tmp_path), 'origin', refs).exit == 2


@pytest.mark.parametrize('remote_sha,tracking', [(None, True), (None, False), ('c'*40, True), ('0'*40, False)])
def test_pushed_range_uses_author_and_committer(tmp_path, monkeypatch, remote_sha, tracking):
    assert hasattr(adapter(), 'push_commits')
    record = SHA + '\0Builder\0builder@example.test\0Other\0other@example.test\0'
    steps = []
    if remote_sha is None:
        steps.append({**({'stdout': 'c' * 40 + '\n'} if tracking else {'exit': 1}), 'when': ['--verify']})
        steps.append({**({'stdout': record} if tracking else {'exit': 128}),
                      'when': ['refs/remotes/origin/feature..' + SHA]})
    if remote_sha != 'c' * 40:
        steps.append({'stdout': record, 'when': ['refs/remotes/origin/main..' + SHA]})
    else:
        steps.append({'stdout': record, 'when': ['c' * 40 + '..' + SHA]})
    calls = install_replay(monkeypatch, 'git', steps)
    result = adapter().push_commits(str(tmp_path), 'origin', 'refs/heads/feature', SHA, remote_sha, 'main')
    assert result.exit == 0, result.reason
    assert result.data['commits'][0]['committer']['name'] == 'Other'
    assert len(calls) == len(steps)
    if remote_sha is None:
        assert any('refs/remotes/origin/feature^{commit}' in call for call in calls)


def test_pushed_range_needs_the_default_branch_tracking_ref(tmp_path, monkeypatch):
    install_replay(monkeypatch, 'git', [{'exit': 1, 'when': ['--verify']},
                                        {'exit': 128, 'when': ['refs/remotes/origin/feature..' + SHA]},
                                        {'exit': 128, 'when': ['refs/remotes/origin/main..' + SHA]}])
    result = adapter().push_commits(str(tmp_path), 'origin', 'refs/heads/feature', SHA, None, 'main')
    assert result.exit == 2


@pytest.mark.parametrize('index,failure,reason,action', [
    (1, {'exit': 1}, 'detached HEAD', 'check out a branch'),
    (0, {'exit': 128}, 'HEAD', 'create a commit'),
    (1, {'exit': 128}, 'symbolic-ref', 'check repository state'),
    (2, {'exit': 128}, 'config', 'check repository state'),
    (3, {'exit': 1}, 'check-ref-format', 'refs/heads/'),
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


def concurrent_run(monkeypatch, outputs):
    """Replace git._run so reads succeed only when all of them wait together."""
    import threading
    git = adapter()
    barrier = threading.Barrier(len(outputs), timeout=2)
    def run(repo, *args, **kwargs):
        output = next(value for key, value in outputs.items() if key in args)
        barrier.wait()
        return output
    monkeypatch.setattr(git, '_run', run)
    return git


def test_commit_context_reads_run_together(tmp_path, monkeypatch):
    ident = 'Builder <builder@example.test> 1790596800 +0200\n'
    git = concurrent_run(monkeypatch, {'--absolute-git-dir': str(tmp_path / '.git') + '\n',
                                       '--git-common-dir': str(tmp_path / '.git') + '\n',
                                       'GIT_AUTHOR_IDENT': ident, 'GIT_COMMITTER_IDENT': ident})
    result = git.commit_context(str(tmp_path), {}, {})
    assert result.data == {'path': str(tmp_path / '.git'), 'common_dir': str(tmp_path / '.git'),
                           'author': OWNER, 'committer': OWNER}


def test_push_context_reads_run_together(tmp_path, monkeypatch):
    git = concurrent_run(monkeypatch, {
        'show': SHA + '\0Builder\0builder@example.test\0Builder\0builder@example.test\n',
        'symbolic-ref': 'feature\n', '--get-regexp': ''})
    monkeypatch.setattr(git, '_run', lambda repo, *args, _run=git._run, **kwargs:
                        '' if args[0] == 'check-ref-format' else _run(repo, *args, **kwargs))
    result = git.push_context(str(tmp_path), 'origin', ['feature'])
    assert result.data == {'head': {'sha': SHA, 'author': OWNER, 'committer': OWNER},
                           'updates': [{'source': SHA, 'destination': 'refs/heads/feature'}],
                           'force': False, 'remote': 'origin'}


def test_workspace_changes_reads_run_together(tmp_path, monkeypatch):
    (tmp_path / '.git').mkdir()
    git = concurrent_run(monkeypatch, {'status': ' M charters/builder.md\0',
                                       'log': '\x1ewuwei\n\0\ncharters/old.md\0'})
    assert git.workspace_changes(tmp_path).data == ['charters/builder.md']


def test_new_branch_range_reads_run_together(tmp_path, monkeypatch):
    record = SHA + '\0Builder\0builder@example.test\0Builder\0builder@example.test\0'
    git = concurrent_run(monkeypatch, {'--verify': '', 'refs/remotes/origin/feature..' + SHA: '',
                                       'refs/remotes/origin/main..' + SHA: record})
    result = git.push_commits(str(tmp_path), 'origin', 'refs/heads/feature', SHA, None, 'main')
    assert result.data == {'commits': [{'sha': SHA, 'author': OWNER, 'committer': OWNER}]}
