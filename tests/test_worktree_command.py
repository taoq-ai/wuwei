"""`wuwei worktree add` creates an anchored item worktree through the vcs port."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

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
    vcs.results['worktree_identity'] = registry.Result(0, {})
    monkeypatch.setattr(registry, 'load', lambda kind, config: vcs)
    import wuwei.commands.git_hook as git_hook
    monkeypatch.setattr(git_hook, 'install', lambda path, root, vcs: None)
    return tmp_path, vcs


def repos(root, *names, identity=''):
    (root / '.wuwei/config.toml').write_text(''.join(
        f'[[repos]]\nname = "{name}"\npath = "{name}"\ndefault_branch = "main"\n'
        + (f'identity = {{name = "{name.title()}", email = "{name}@example.test"}}\n' if identity else '')
        for name in names))


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


def identities(vcs):
    return [call[1] for call in vcs.calls if call[0] == 'worktree_identity']


def test_worktree_add_writes_configured_identity(fake, capsys):
    root, vcs = fake
    repos(root, 'app', identity=True)
    assert main(['worktree', 'add', 'X']) == 0
    assert [call[0] for call in vcs.calls][-2:] == ['worktree_add', 'worktree_identity']
    assert identities(vcs) == [(str(root / 'worktrees/X'), 'App', 'app@example.test')]
    assert json.loads(capsys.readouterr().out) == {'branch': 'x', 'path': 'p'}


def test_worktree_add_writes_selected_repository_identity(fake):
    root, vcs = fake
    repos(root, 'app', 'web', identity=True)
    assert main(['worktree', 'add', 'X', '--repo', 'web']) == 0
    assert identities(vcs) == [(str(root / 'worktrees/X'), 'Web', 'web@example.test')]


def test_worktree_add_without_identity_writes_none(fake):
    root, vcs = fake
    repos(root, 'app')
    assert main(['worktree', 'add', 'X']) == 0
    assert not identities(vcs)


def test_worktree_identity_failure_exits_2(fake):
    root, vcs = fake
    repos(root, 'app', identity=True)
    vcs.results['worktree_identity'] = registry.Result(
        2, None, 'git.worktree_identity: could not run: invalid identity')
    assert main(['worktree', 'add', 'X']) == 2


def commit_through_hook(tree, monkeypatch, capsys):
    from wuwei.commands.hook import run
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({
        'hook_event_name': 'PreToolUse', 'session_id': 'fixture',
        'transcript_path': str(tree / 'transcript.jsonl'), 'cwd': str(tree),
        'tool_name': 'Bash', 'tool_input': {'command': 'git commit -qm x'}})))
    code = run(SimpleNamespace(event='PreToolUse'))
    out = capsys.readouterr().out
    return code, json.loads(out)['hookSpecificOutput']['permissionDecisionReason'] if out else ''


def test_template_identity_lets_a_seat_commit(tmp_path, monkeypatch, capsys):
    from fakes.integrity import seed
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    repo = tmp_path / 'repo'
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
    (repo / 'a.txt').write_text('a\n')
    git(repo, 'add', 'a.txt')
    seeded = git(repo, '-c', 'user.name=Seed', '-c', 'user.email=seed@example.test', 'commit', '-qm', 'seed')
    assert seeded.returncode == 0, seeded.stderr
    template = (ROOT / 'templates/workspace/config.toml').read_text().splitlines()
    line = next(line for line in template if line.startswith('# identity = '))
    assert 'wuwei worktree add' in line
    assignment = line[2:].split(' # ')[0]
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        f'[[repos]]\nname = "app"\npath = "repo"\ndefault_branch = "main"\n{assignment}\n')
    seed(tmp_path)
    state._write_state(lambda data: data.update(gate_approved=True), tmp_path, reserved=False)
    monkeypatch.chdir(tmp_path)
    assert main(['worktree', 'add', 'X']) == 0
    capsys.readouterr()
    tree = tmp_path / 'worktrees/X'
    (tree / 'new.txt').write_text('new\n')
    git(tree, 'add', 'new.txt')
    assert commit_through_hook(tree, monkeypatch, capsys) == (0, '')
    assert git(repo, 'config', '--local', '--get', 'user.name').returncode == 1
    assert git(tree, 'config', '--worktree', '--get', 'user.email').stdout.strip() == 'builder@example.test'
    git(tree, 'config', '--worktree', 'user.email', 'other@example.test')
    code, reason = commit_through_hook(tree, monkeypatch, capsys)
    assert code == 2
    assert 'wuwei worktree add' in reason and 'git config user.email builder@example.test' in reason


def claimed_events(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row for row in map(json.loads, path.read_text().splitlines())
            if row['kind'] == 'item.claimed']


def test_worktree_add_refuses_item_claimed_by_live_session(fake, monkeypatch, capsys):
    root, vcs = fake
    repos(root, 'app')
    stamp = workspace.now().isoformat()
    state._write_state(lambda data: data.update(
        claims={'ITEM-1': 'A'}, sessions={'A': {'role': 'adhoc', 'started': stamp,
                                                'last_seen': stamp, 'cwd': str(root)}}),
        root, reserved=False)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'B')
    assert main(['worktree', 'add', 'ITEM-1']) == 2
    assert 'claimed by live session A' in capsys.readouterr().err and adds(vcs) == []
    monkeypatch.setenv('WUWEI_SESSION_ID', 'A')
    assert main(['worktree', 'add', 'ITEM-1']) == 0
    assert len(adds(vcs)) == 1
    assert claimed_events(root)[-1]['payload'] == {'item': 'ITEM-1', 'session': 'A',
                                                   'prs_seen': False}


def test_gate_refusal_makes_no_claim(fake, monkeypatch):
    root, vcs = fake
    repos(root, 'app')
    state._write_state(lambda data: data.update(gate_approved=False), root, reserved=False)
    monkeypatch.setenv('WUWEI_SESSION_ID', 'A')
    assert main(['worktree', 'add', 'X']) == 1
    assert claimed_events(root) == []
