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
    assert fake.calls[-1][:2] == ('hooks_path', (str(root / 'repo'), str(root / '.wuwei/git-hooks'), 'chain'))


def test_hooks_path_fails_closed(tmp_path, monkeypatch):
    calls = install_replay(monkeypatch, 'git', [{'exit': 128}])
    result = adapter().hooks_path(str(tmp_path / 'repo'), str(tmp_path / 'hooks'), 'chain')
    assert result.exit == 2 and result.reason
    assert len(calls) == 1


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)


def hook_repo(tmp_path, monkeypatch, hooks_path=None, default_hook=False):
    """A repository with a commit and a linked worktree, plus executable WUWEI shims."""
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    tmp_path = tmp_path.resolve()
    repo, tree, shims = tmp_path / 'repo', tmp_path / 'tree', tmp_path / 'shims'
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
    git(repo, 'config', 'user.name', 'Builder')
    git(repo, 'config', 'user.email', 'builder@example.test')
    assert git(repo, 'commit', '-q', '--allow-empty', '-m', 'start').returncode == 0
    assert git(repo, 'worktree', 'add', '-q', '-b', 'x', str(tree)).returncode == 0
    if default_hook:
        (repo / '.git/hooks/pre-commit').write_text('#!/bin/sh\nexit 0\n')
        (repo / '.git/hooks/pre-commit').chmod(0o755)
    if hooks_path is not None:
        git(repo, 'config', 'core.hooksPath', str(hooks_path))
    shims.mkdir()
    for name in ('pre-commit', 'pre-push'):
        (shims / name).write_text('#!/bin/sh\nexit 0\n')
        (shims / name).chmod(0o755)
    return repo, tree, shims


def own_hooks(tmp_path, *names):
    own = tmp_path.resolve() / 'own'
    own.mkdir()
    for name in names:
        (own / name).write_text('#!/bin/sh\nexit 0\n')
        (own / name).chmod(0o755)
    return own


def test_hooks_path_chains_custom_hooks_path(tmp_path, monkeypatch):
    own = own_hooks(tmp_path, 'pre-commit', 'post-checkout')
    repo, tree, shims = hook_repo(tmp_path, monkeypatch, own)
    result = adapter().hooks_path(str(tree), str(shims), 'chain')
    assert result.exit == 0, result.reason
    assert result.data['chained'] == str(own)
    chain = Path(git(tree, 'rev-parse', '--absolute-git-dir').stdout.strip()) / 'wuwei-hooks'
    assert git(tree, 'config', '--worktree', '--get', 'core.hooksPath').stdout.strip() == str(chain)
    assert git(repo, 'config', '--local', '--get', 'core.hooksPath').stdout.strip() == str(own)
    for name in ('pre-commit', 'pre-push', 'commit-msg', 'post-checkout'):
        assert os.access(chain / name, os.X_OK), name
    assert str(shims / 'pre-commit') in (chain / 'pre-commit').read_text()
    assert str(own / 'pre-commit') in (chain / 'pre-commit').read_text()
    assert str(shims) not in (chain / 'commit-msg').read_text()


def test_hooks_path_chains_relative_hooks_path(tmp_path, monkeypatch):
    _, tree, shims = hook_repo(tmp_path, monkeypatch, '.husky')
    result = adapter().hooks_path(str(tree), str(shims), 'chain')
    assert result.exit == 0, result.reason
    assert result.data['chained'] == str(tree / '.husky')


def test_hooks_path_chains_default_hooks(tmp_path, monkeypatch):
    repo, tree, shims = hook_repo(tmp_path, monkeypatch, default_hook=True)
    result = adapter().hooks_path(str(tree), str(shims), 'chain')
    assert result.exit == 0, result.reason
    assert result.data['chained'] == str(repo / '.git/hooks')


def test_hooks_path_plain_without_custom_hooks(tmp_path, monkeypatch):
    _, tree, shims = hook_repo(tmp_path, monkeypatch)
    result = adapter().hooks_path(str(tree), str(shims), 'chain')
    assert result.exit == 0, result.reason
    assert result.data['chained'] == ''
    assert git(tree, 'config', '--worktree', '--get', 'core.hooksPath').stdout.strip() == str(shims)
    assert not (Path(result.data['git_dir']) / 'wuwei-hooks').exists()


def test_hooks_path_rerun_finds_the_original(tmp_path, monkeypatch):
    own = own_hooks(tmp_path, 'pre-commit')
    _, tree, shims = hook_repo(tmp_path, monkeypatch, own)
    first = adapter().hooks_path(str(tree), str(shims), 'chain')
    script = Path(first.data['git_dir']) / 'wuwei-hooks/pre-commit'
    script.write_text('changed')
    again = adapter().hooks_path(str(tree), str(shims), 'chain')
    assert again.exit == 0 and again.data['chained'] == str(own)
    assert str(own / 'pre-commit') in script.read_text()


def test_hooks_path_skippable_layouts(tmp_path, monkeypatch):
    hooks_file = tmp_path.resolve() / 'hooks-file'
    hooks_file.write_text('')
    repo, tree, shims = hook_repo(tmp_path, monkeypatch, hooks_file)
    result = adapter().hooks_path(str(tree), str(shims), 'chain')
    assert result.exit == 1 and 'not a directory' in result.reason
    assert git(repo, 'config', '--get', 'extensions.worktreeConfig').stdout.strip() == 'true'
    assert git(tree, 'config', '--worktree', '--get', 'core.hooksPath').returncode == 1


def test_hooks_path_skips_core_worktree(tmp_path, monkeypatch):
    repo, tree, shims = hook_repo(tmp_path, monkeypatch)
    git(repo, 'config', 'core.worktree', str(repo))
    result = adapter().hooks_path(str(tree), str(shims), 'chain')
    assert result.exit == 1 and 'core.worktree' in result.reason
    assert git(repo, 'config', '--get', 'extensions.worktreeConfig').returncode == 1


def test_hooks_path_modes(tmp_path, monkeypatch):
    own = own_hooks(tmp_path, 'pre-commit')
    repo, tree, shims = hook_repo(tmp_path, monkeypatch, own)
    result = adapter().hooks_path(str(tree), str(shims), 'replace')
    assert result.exit == 0 and result.data['chained'] == ''
    assert git(tree, 'config', '--worktree', '--get', 'core.hooksPath').stdout.strip() == str(shims)
    assert not (Path(result.data['git_dir']) / 'wuwei-hooks').exists()
    git(tree, 'config', '--worktree', '--unset', 'core.hooksPath')
    result = adapter().hooks_path(str(tree), str(shims), 'skip')
    assert result.exit == 0, result.reason
    assert git(tree, 'config', '--worktree', '--get', 'core.hooksPath').returncode == 1
    assert git(repo, 'config', '--get', 'extensions.worktreeConfig').stdout.strip() == 'true'


def test_hooks_target_reads_without_writing(tmp_path, monkeypatch):
    own = own_hooks(tmp_path, 'pre-commit')
    repo, _, _ = hook_repo(tmp_path, monkeypatch)
    assert adapter().hooks_target(str(repo)).data == {'chain': ''}
    git(repo, 'config', 'core.hooksPath', str(own))
    assert adapter().hooks_target(str(repo)).data == {'chain': str(own)}
    (tmp_path / 'file').write_text('')
    git(repo, 'config', 'core.hooksPath', str(tmp_path.resolve() / 'file'))
    config = (repo / '.git/config').read_text()
    assert adapter().hooks_target(str(repo)).exit == 1
    assert (repo / '.git/config').read_text() == config


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


def test_git_hooks_mode_config(tmp_path):
    from wuwei import workspace
    (tmp_path / '.wuwei').mkdir()
    config = tmp_path / '.wuwei/config.toml'
    config.write_text('')
    assert workspace.load_config(tmp_path)['worktree']['git_hooks'] == 'chain'
    config.write_text('[worktree]\ngit_hooks = "replace"\n')
    assert workspace.load_config(tmp_path)['worktree']['git_hooks'] == 'replace'
    config.write_text('[worktree]\ngit_hooks = "other"\n')
    with pytest.raises(workspace.ConfigError, match='worktree.git_hooks'):
        workspace.load_config(tmp_path)


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


def test_init_upgrade_regenerates_worktree_hooks(tmp_path, monkeypatch, capsys):
    from argparse import Namespace
    from wuwei import state, workspace
    from wuwei.commands import init
    from test_workspace import previous_workspace
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    own = own_hooks(tmp_path, 'pre-commit')
    repo, _, _ = hook_repo(tmp_path, monkeypatch, own)
    root = tmp_path.resolve() / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    state._write_state(lambda data: data.update(gate_approved=True), root, reserved=False)
    workspace.create_worktree(repo, 'item', root / 'worktrees/X', root, adapter())
    script = Path(git(root / 'worktrees/X', 'rev-parse', '--absolute-git-dir').stdout.strip()) / 'wuwei-hooks/pre-commit'
    script.unlink()
    (root / 'worktrees/A').mkdir()
    (root / 'worktrees/A/.git').write_text('gitdir: ' + str(tmp_path / 'gone') + '\n')
    init._worktree_hooks(root)
    assert str(own / 'pre-commit') in script.read_text()
    assert 'wuwei init warning: A: ' in capsys.readouterr().err

    upgraded = tmp_path / 'upgraded'
    previous_workspace(upgraded)
    seen = []
    monkeypatch.setattr(init, '_worktree_hooks', seen.append)
    assert init.run(Namespace(path=str(upgraded), upgrade=True, dry_run=True)) == 0
    assert seen == []
    assert init.run(Namespace(path=str(upgraded), upgrade=True, dry_run=False)) == 0
    assert seen == [upgraded]
