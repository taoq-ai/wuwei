"""`wuwei worktree add` creates an anchored item worktree through the vcs port."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from fakes.vcs import Fake as VCS
from wuwei import registry, state, workspace
from wuwei.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args, env=None):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, env=env)


def test_worktree_add_anchors_pre_push_outside_claude(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    repo, origin = tmp_path / 'repo', tmp_path / 'origin.git'
    subprocess.run(['git', 'clone', '--shared', str(ROOT), str(repo)], check=True, capture_output=True)
    subprocess.run(['git', 'init', '--bare', str(origin)], check=True, capture_output=True)
    git(repo, 'remote', 'set-url', 'origin', str(origin))
    git(repo, 'config', 'user.name', 'Builder')
    git(repo, 'config', 'user.email', 'builder@example.test')
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "app"\npath = "repo"\ndefault_branch = "main"\n')
    record = tmp_path / 'record.txt'
    stub = tmp_path / 'stub-cli'
    stub.write_text(f'#!/bin/sh\necho "$* $WUWEI_WORKSPACE" >> "{record}"\nexit 1\n')
    stub.chmod(0o755)
    workspace.atomic_write(tmp_path / '.wuwei/executable', str(stub) + '\n')
    state._write_state(lambda data: data.update(gate_approved=True), tmp_path, reserved=False)
    monkeypatch.chdir(tmp_path)
    assert main(['worktree', 'add', 'X']) == 0
    tree = tmp_path / 'worktrees/X'
    assert json.loads(capsys.readouterr().out) == {'branch': 'x', 'path': str(tree)}
    (tree / 'new.txt').write_text('new\n')
    git(tree, 'add', 'new.txt')
    clean = {k: v for k, v in os.environ.items() if k != 'WUWEI_WORKSPACE' and not k.startswith('GIT_')}
    assert git(tree, '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'new', env=clean).returncode == 0
    assert git(tree, 'push', 'origin', 'x', env=clean).returncode != 0
    seen = record.read_text()
    assert 'git-hook pre-push' in seen and str(tmp_path) in seen


@pytest.fixture
def fake(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    (tmp_path / '.wuwei').mkdir()
    state._write_state(lambda data: data.update(gate_approved=True), tmp_path, reserved=False)
    vcs = VCS()
    vcs.results['worktree_add'] = registry.Result(0, {'branch': 'x', 'path': 'p'})
    monkeypatch.setattr(registry, 'load', lambda kind, config: vcs)
    import wuwei.commands.git_hook as git_hook
    monkeypatch.setattr(git_hook, 'install', lambda path, root, vcs: None)
    return tmp_path, vcs


def repos(root, *names):
    (root / '.wuwei/config.toml').write_text(''.join(
        f'[[repos]]\nname = "{name}"\npath = "{name}"\ndefault_branch = "main"\n' for name in names))


def adds(vcs):
    return [call[1] for call in vcs.calls if call[0] == 'worktree_add']


def test_gate_refusal_exits_1_without_vcs_call(fake, capsys):
    root, vcs = fake
    repos(root, 'app')
    state._write_state(lambda data: data.update(gate_approved=False), root, reserved=False)
    assert main(['worktree', 'add', 'X']) == 1
    assert 'gate' in capsys.readouterr().err and not vcs.calls


@pytest.mark.parametrize('names,extra,code,repo', [
    (['app'], [], 0, 'app'),
    (['app', 'web'], [], 2, None),
    (['app', 'web'], ['--repo', 'web'], 0, 'web'),
    (['app'], ['--repo', 'other'], 2, None),
    ([], [], 2, None),
])
def test_repo_selection(fake, capsys, names, extra, code, repo):
    root, vcs = fake
    repos(root, *names)
    assert main(['worktree', 'add', 'X', *extra]) == code
    if repo is None:
        assert not adds(vcs)
        if len(names) > 1:
            assert '--repo' in capsys.readouterr().err
    else:
        assert adds(vcs) == [(str((root / repo).resolve()), 'x', str(root / 'worktrees/X'))]
        assert json.loads(capsys.readouterr().out) == {'branch': 'x', 'path': 'p'}


def test_invalid_item_exits_2_without_vcs_call(fake):
    root, vcs = fake
    repos(root, 'app')
    assert main(['worktree', 'add', '../x']) == 2
    assert not vcs.calls
