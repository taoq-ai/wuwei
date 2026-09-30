"""Native Git hooks call the same policies without shell-command parsing."""

import importlib
import io
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from fakes.replay import install_replay, install_stub
from test_commit_push import OWNER, OTHER, SHA, OLD, workspace_case, set_fast_checks
from test_vcs import adapter

ROOT = Path(__file__).resolve().parents[1]


def command():
    assert (ROOT / 'cli/wuwei/commands/git_hook.py').exists(), 'Git hook entry point is missing'
    return importlib.import_module('wuwei.commands.git_hook')


def invoke(case, monkeypatch, event, updates=''):
    root, _ = case
    monkeypatch.chdir(root / 'repo')
    monkeypatch.setattr(sys, 'stdin', io.StringIO(updates))
    return command().run(SimpleNamespace(event=event, remote='origin', url='unused'))


@pytest.mark.parametrize('event,wrong,updates,code', [
    ('pre-commit', False, '', 0), ('pre-commit', True, '', 1),
    ('pre-push', False, f'refs/heads/feature {SHA} refs/heads/feature {OLD}\n', 0),
    ('pre-push', True, f'refs/heads/feature {SHA} refs/heads/feature {OLD}\n', 1),
    ('pre-push', False, f'refs/heads/feature {SHA} refs/heads/main {OLD}\n', 1),
    ('pre-push', False, f'refs/heads/feature {OLD} refs/heads/feature {OLD}\n', 1),
    ('pre-push', False, f'refs/heads/feature {SHA} refs/heads/feature {"0"*40}\n', 0),
    ('pre-push', False, f'refs/heads/feature {SHA} refs/tags/v1 {OLD}\n', 2),
    ('pre-push', False, '(delete) ' + '0'*40 + f' refs/heads/feature {OLD}\n', 1),
    ('pre-push', False, '', 2), ('pre-push', False, 'malformed\n', 2),
])
def test_native_hook_table(workspace_case, monkeypatch, event, wrong, updates, code):
    _, fake = workspace_case
    if wrong:
        fake.results['commit_context'].data['author'] = OTHER
    assert invoke(workspace_case, monkeypatch, event, updates) == code


def test_native_hook_rejects_non_fast_forward(workspace_case, monkeypatch):
    from wuwei.registry import Result
    _, fake = workspace_case
    fake.results['merge_base'] = Result(0, {'sha': 'c' * 40})
    updates = f'refs/heads/feature {SHA} refs/heads/feature {OLD}\n'
    assert invoke(workspace_case, monkeypatch, 'pre-push', updates) == 1


@pytest.mark.parametrize('failure', ['ancestry', 'head', 'checks'])
def test_native_push_evidence_failures(workspace_case, monkeypatch, failure):
    from wuwei import state
    from wuwei.registry import Result
    root, fake = workspace_case
    if failure == 'ancestry':
        fake.results['merge_base'] = Result(2, None, 'unavailable ancestry')
    elif failure == 'head':
        fake.results['head'].data['committer'] = OTHER
    else:
        set_fast_checks(root, {'example/project': {'unit': {'sha': OLD, 'exit': 0}}})
    updates = f'refs/heads/feature {SHA} refs/heads/feature {OLD}\n'
    assert invoke(workspace_case, monkeypatch, 'pre-push', updates) == (2 if failure == 'ancestry' else 1)


def test_native_push_reads_head_without_inventing_a_destination(workspace_case, monkeypatch):
    from wuwei.registry import Result
    root, fake = workspace_case
    fake.results['push_context'] = Result(2, None, 'push configuration is irrelevant to hook input')
    updates = f'refs/heads/feature {SHA} refs/heads/feature {OLD}\n'
    assert invoke(workspace_case, monkeypatch, 'pre-push', updates) == 0
    assert ('head', (str(root / 'repo'),), root) in fake.calls
    assert not any(call[0] == 'push_context' for call in fake.calls)


@pytest.mark.parametrize('result', [None, {}, {'sha': SHA}])
def test_native_push_missing_head_identity_fails_closed(workspace_case, monkeypatch, result):
    from wuwei.registry import Result
    _, fake = workspace_case
    fake.results['head'] = Result(0, result)
    updates = f'refs/heads/feature {SHA} refs/heads/feature {OLD}\n'
    assert invoke(workspace_case, monkeypatch, 'pre-push', updates) == 2


def test_hook_installer_writes_executable_safe_shims(workspace_case):
    root, fake = workspace_case
    from wuwei.registry import Result
    fake.results['hooks_path'] = Result(0, {'git_dir': str(root / 'repo')})
    command().install(root / 'repo', root, fake)
    for event in ('pre-commit', 'pre-push'):
        hook = root / '.wuwei/git-hooks' / event
        assert hook.is_file() and os.access(hook, os.X_OK)
        source = hook.read_text()
        assert '.wuwei/executable' in source and 'git-hook ' + event in source
        assert 'wuwei-workspace' in source
    assert fake.calls[-1][:2] == ('hooks_path', (str(root / 'repo'), str(root / '.wuwei/git-hooks')))


@pytest.mark.parametrize('existing,exit_code,expected', [('', 1, 0), ('custom\n', 0, 2), ('', 128, 2)])
def test_hooks_path_preserves_custom_hooks(tmp_path, monkeypatch, existing, exit_code, expected):
    assert hasattr(adapter(), 'hooks_path'), 'hook configuration port is missing'
    calls = install_replay(monkeypatch, 'git', [
        {'stdout': str(tmp_path / 'private-git')}, {'stdout': str(tmp_path / 'common-git')},
        {'stdout': existing, 'exit': exit_code},
        {'stdout': str(tmp_path / 'default-hooks') + '\n'},
        {'stdout': 'false'}, {'exit': 1}, {'stdout': ''}, {'stdout': ''}])
    result = adapter().hooks_path(str(tmp_path / 'repo'), str(tmp_path / 'hooks'))
    assert result.exit == expected
    if expected:
        assert len(calls) == 3


def test_worktree_install_failure_is_not_clean(tmp_path, monkeypatch):
    assert hasattr(command(), 'install')
    (tmp_path / '.wuwei').mkdir()
    install_replay(monkeypatch, 'git', [{'exit': 128}])
    result = adapter().worktree_add(str(tmp_path / 'repo'), 'feature', str(tmp_path / 'tree'), root=tmp_path)
    assert result.exit == 2 and result.reason


@pytest.mark.parametrize('event', ['pre-commit', 'pre-push'])
def test_installed_hook_executes_cli_safely(workspace_case, monkeypatch, event):
    from wuwei.registry import Result
    root, fake = workspace_case
    fake.results['hooks_path'] = Result(0, {'git_dir': str(root / 'repo')})
    command().install(root / 'repo', root, fake)
    # A shadow package must never replace the guard.
    (root / 'repo/wuwei').mkdir()
    (root / 'repo/wuwei/__main__.py').write_text('raise SystemExit(0)\n')
    (root / '.wuwei/executable').write_text(str(ROOT / 'bin/wuwei') + '\n')
    steps = [
        {'stdout': str(root / 'repo') + '\n', 'when': ['--absolute-git-dir']},
        {'stdout': str(root / 'repo/.git') + '\n', 'when': ['--git-common-dir']},
        {'stdout': 'Other <other@example.test> 1790596800 +0200\n', 'when': ['GIT_AUTHOR_IDENT']},
        {'stdout': 'Builder <builder@example.test> 1790596800 +0200\n', 'when': ['GIT_COMMITTER_IDENT']},
    ] * 2
    original_path = os.environ['PATH']
    install_stub(root, monkeypatch, 'git', [{'stdout': str(root / 'repo') + '\n'}] + steps)
    monkeypatch.setenv('PATH', str(root / 'tools') + os.pathsep + original_path)
    (root / 'tools/python3').symlink_to(sys.executable)
    result = subprocess.run([str(root / '.wuwei/git-hooks' / event), 'origin', 'unused'],
                            cwd=root / 'repo', text=True, capture_output=True)
    assert result.returncode == 1, result.stderr
    assert 'GIT_AUTHOR_IDENT' in result.stderr


def test_existing_default_hook_is_not_disabled(tmp_path, monkeypatch):
    default_hooks = tmp_path / 'default-hooks'
    default_hooks.mkdir()
    (default_hooks / 'pre-commit').write_text('#!/bin/sh\nexit 1\n')
    calls = install_replay(monkeypatch, 'git', [
        {'stdout': str(tmp_path / 'private-git')}, {'stdout': str(tmp_path / 'common-git')},
        {'exit': 1}, {'stdout': str(default_hooks) + '\n'}, {'stdout': ''},
    ])
    result = adapter().hooks_path(str(tmp_path / 'repo'), str(tmp_path / 'managed'))
    assert result.exit == 2 and 'existing' in result.reason
    assert len(calls) == 4


def test_native_hook_rejects_common_directory_override(workspace_case, monkeypatch):
    root, _ = workspace_case
    monkeypatch.setenv('GIT_COMMON_DIR', str(root / 'other/.git'))
    assert invoke(workspace_case, monkeypatch, 'pre-commit') == 2


def test_hook_failure_prevents_core_success(workspace_case):
    from wuwei import workspace
    from wuwei.registry import Result
    root, fake = workspace_case
    from wuwei import state
    state._write_state(lambda data: data.update(gate_approved=True), root, reserved=False)
    fake.results['worktree_add'] = Result(0, {'branch': 'feature', 'path': str(root / 'tree')})
    fake.results['hooks_path'] = Result(2, None, 'unavailable hooks')
    with pytest.raises(ValueError, match='unavailable hooks'):
        workspace.create_worktree(root / 'repo', 'feature', root / 'tree', root, fake)
    assert [call[0] for call in fake.calls] == ['worktree_add', 'hooks_path']


def test_worktree_port_is_only_git(tmp_path, monkeypatch):
    calls = install_replay(monkeypatch, 'git', [{'stdout': ''}])
    result = adapter().worktree_add(str(tmp_path / 'repo'), 'feature', str(tmp_path / 'tree'))
    assert result.exit == 0, result.reason
    assert calls == [['git', '-C', str(tmp_path / 'repo'), 'worktree', 'add', '-b', 'feature', '--', str(tmp_path / 'tree')]]


def test_managed_worktree_isolation_and_runtime_pointer(tmp_path, monkeypatch):
    from wuwei import workspace
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    owner = tmp_path / 'owner'
    subprocess.run(['git', 'clone', '--shared', str(ROOT), str(owner)], check=True, capture_output=True)
    def git(repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    git(owner, 'config', 'user.name', 'Builder')
    git(owner, 'config', 'user.email', 'builder@example.test')
    sibling, managed = tmp_path / 'sibling', tmp_path / 'managed'
    assert git(owner, 'worktree', 'add', '-b', 'unmanaged', str(sibling)).returncode == 0
    (tmp_path / '.wuwei').mkdir()
    workspace.atomic_write(tmp_path / '.wuwei/executable', str(ROOT / 'bin/wuwei') + '\n')
    from wuwei import state
    state._write_state(lambda data: data.update(gate_approved=True), tmp_path, reserved=False)
    assert hasattr(workspace, 'create_worktree'), 'core worktree caller is missing'
    workspace.create_worktree(owner, 'managed', managed, tmp_path, adapter())
    assert git(owner, 'config', '--get', 'extensions.worktreeConfig').stdout.strip() == 'true'
    for repo in (owner, sibling):
        assert git(repo, 'config', '--get', 'core.hooksPath').returncode == 1
    assert git(managed, 'config', '--worktree', '--get', 'core.hooksPath').stdout.strip() == str(tmp_path / '.wuwei/git-hooks')
    directory = Path(git(managed, 'rev-parse', '--absolute-git-dir').stdout.strip())
    assert (directory / 'wuwei-workspace').read_text().strip() == str(tmp_path)
    hook = tmp_path / '.wuwei/git-hooks/pre-commit'
    assert str(ROOT) not in hook.read_text()
    (tmp_path / '.wuwei/executable').unlink()
    for repo in (owner, sibling):
        assert subprocess.run([str(hook)], cwd=repo, capture_output=True).returncode == 0
    result = subprocess.run([str(hook)], cwd=managed, capture_output=True, text=True)
    assert result.returncode == 2 and 'executable' in result.stderr
    replacement = tmp_path / 'replacement cli'
    replacement.write_text('#!/bin/sh\nexit 1\n')
    replacement.chmod(0o755)
    (tmp_path / '.wuwei/executable').write_text(str(replacement) + '\n')
    assert subprocess.run([str(hook)], cwd=managed, capture_output=True).returncode == 1
