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
    # A bare clone, not a push: the CI checkout is shallow and a shallow push is refused.
    subprocess.run(['git', 'clone', '-q', '--bare', '--shared', str(repo), str(origin)], check=True, capture_output=True)
    assert git(origin, 'update-ref', 'refs/heads/main', git(repo, 'rev-parse', 'HEAD').stdout.strip()).returncode == 0
    assert git(origin, 'symbolic-ref', 'HEAD', 'refs/heads/main').returncode == 0
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
    start = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    assert json.loads(capsys.readouterr().out) == {'branch': 'x', 'path': str(tree), 'start': start}
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
    vcs.results['worktree_add'] = registry.Result(0, {'branch': 'x', 'path': 'p', 'start': 'a' * 40})
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
            assert '(app, web); pass --repo' in capsys.readouterr().err
    else:
        assert adds(vcs) == [(str((root / repo).resolve()), 'x', str(root / 'worktrees/X'), 'origin', 'main')]
        assert json.loads(capsys.readouterr().out) == {'branch': 'x', 'path': 'p', 'start': 'a' * 40}


def test_add_falls_back_to_the_proposed_repository(fake, capsys):
    # #603: a remediation line names worktree add <item>; today's proposal knows the repository.
    root, vcs = fake
    repos(root, 'app', 'web')
    day = workspace.day_dir(root)
    day.mkdir(parents=True, exist_ok=True)
    (day / 'proposal.json').write_text(json.dumps({'candidates': [{'id': 'X', 'repo': 'web'}]}))
    assert main(['worktree', 'add', 'X']) == 0, capsys.readouterr().err
    assert adds(vcs) == [(str((root / 'web').resolve()), 'x', str(root / 'worktrees/X'), 'origin', 'main')]


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
    assert json.loads(capsys.readouterr().out) == {'branch': 'x', 'path': 'p', 'start': 'a' * 40}


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
        f'[[repos]]\nname = "app"\npath = "repo"\ndefault_branch = "main"\n{assignment}\n[brief]\nremote = "."\n')
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


def hooked_workspace(tmp_path, monkeypatch, config=''):
    """A fresh repository with a bare origin, a workspace and a recording stub CLI (#472)."""
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    tmp_path = tmp_path.resolve()
    repo, origin = tmp_path / 'repo', tmp_path / 'origin.git'
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
    subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(origin)], check=True)
    git(repo, 'remote', 'add', 'origin', str(origin))
    git(repo, 'config', 'user.name', 'Builder')
    git(repo, 'config', 'user.email', 'builder@example.test')
    assert git(repo, 'commit', '-q', '--allow-empty', '-m', 'start').returncode == 0
    assert git(repo, 'push', '-q', 'origin', 'main').returncode == 0
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "app"\npath = "repo"\ndefault_branch = "main"\n' + config)
    stub = tmp_path / 'stub-cli'
    stub.write_text(f'#!/bin/sh\necho "$*" >> "{tmp_path / "record.txt"}"\n[ "$2" != pre-push ]\n')
    stub.chmod(0o755)
    workspace.atomic_write(tmp_path / '.wuwei/executable', str(stub) + '\n')
    state._write_state(lambda data: data.update(gate_approved=True), tmp_path, reserved=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path, repo


def marker_hooks(directory, record, *names):
    directory.mkdir(exist_ok=True)
    for name in names:
        (directory / name).write_text(f'#!/bin/sh\necho {name} >> "{record}"\n')
        (directory / name).chmod(0o755)


def commit_and_push(tree):
    clean = {k: v for k, v in os.environ.items() if k != 'WUWEI_WORKSPACE' and not k.startswith('GIT_')}
    (tree / 'new.txt').write_text('new\n')
    git(tree, 'add', 'new.txt')
    return (git(tree, 'commit', '-qm', 'new', env=clean), git(tree, 'push', 'origin', 'x', env=clean))


def test_worktree_add_chains_repository_hooks_path(tmp_path, monkeypatch, capsys):
    root, repo = hooked_workspace(tmp_path, monkeypatch)
    marker_hooks(root / 'own', root / 'marker.txt', 'pre-commit', 'pre-push')
    git(repo, 'config', 'core.hooksPath', str(root / 'own'))
    assert main(['worktree', 'add', 'X']) == 0, capsys.readouterr().err
    committed, pushed = commit_and_push(root / 'worktrees/X')
    assert committed.returncode == 0, committed.stderr
    assert pushed.returncode != 0
    assert 'git-hook pre-commit' in (root / 'record.txt').read_text()
    assert 'git-hook pre-push' in (root / 'record.txt').read_text()
    assert (root / 'marker.txt').read_text().split() == ['pre-commit']
    assert git(repo, 'config', '--local', '--get', 'core.hooksPath').stdout.strip() == str(root / 'own')


def test_worktree_add_chains_default_hooks(tmp_path, monkeypatch, capsys):
    root, repo = hooked_workspace(tmp_path, monkeypatch)
    marker_hooks(repo / '.git/hooks', root / 'marker.txt', 'pre-commit')
    assert main(['worktree', 'add', 'X']) == 0, capsys.readouterr().err
    committed, _ = commit_and_push(root / 'worktrees/X')
    assert committed.returncode == 0, committed.stderr
    assert 'git-hook pre-commit' in (root / 'record.txt').read_text()
    assert (root / 'marker.txt').read_text().split() == ['pre-commit']


def hooks_skipped(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row['payload'] for row in map(json.loads, path.read_text().splitlines())
            if row['kind'] == 'worktree.hooks_skipped']


def test_worktree_add_skips_unchainable_hooks_under_guarded(tmp_path, monkeypatch, capsys):
    root, repo = hooked_workspace(tmp_path, monkeypatch)
    (root / 'hooks-file').write_text('')
    git(repo, 'config', 'core.hooksPath', str(root / 'hooks-file'))
    assert main(['worktree', 'add', 'X']) == 0
    tree = root / 'worktrees/X'
    git_dir = Path(git(tree, 'rev-parse', '--absolute-git-dir').stdout.strip())
    assert (git_dir / 'wuwei-workspace').read_text().strip() == str(root)
    assert git(tree, 'config', '--worktree', '--get', 'core.hooksPath').returncode == 1
    lines = [line for line in capsys.readouterr().err.splitlines() if 'git hooks skipped' in line]
    assert len(lines) == 1 and 'not a directory' in lines[0] and 'PreToolUse' in lines[0]
    events = hooks_skipped(root)
    assert len(events) == 1 and events[0]['worktree'] == 'X' and 'not a directory' in events[0]['reason']


def test_worktree_add_refuses_unchainable_hooks_under_strict(tmp_path, monkeypatch, capsys):
    root, repo = hooked_workspace(tmp_path, monkeypatch, '[security]\nposture = "strict"\n')
    (root / 'hooks-file').write_text('')
    git(repo, 'config', 'core.hooksPath', str(root / 'hooks-file'))
    assert main(['worktree', 'add', 'X']) == 2
    err = capsys.readouterr().err
    assert 'not a directory' in err and 'worktree add again' in err


def test_worktree_add_skip_mode_never_refuses(tmp_path, monkeypatch, capsys):
    root, repo = hooked_workspace(tmp_path, monkeypatch, (
        'identity = {name = "Builder", email = "builder@example.test"}\n'
        '[security]\nposture = "strict"\n[worktree]\ngit_hooks = "skip"\n'))
    assert main(['worktree', 'add', 'X']) == 0, capsys.readouterr().err
    assert 'git hooks skipped' in capsys.readouterr().err
    assert hooks_skipped(root)[0]['reason'] == 'worktree.git_hooks = "skip"'
    tree = root / 'worktrees/X'
    assert git(tree, 'config', '--worktree', '--get', 'user.email').stdout.strip() == 'builder@example.test'
    assert git(repo, 'config', '--local', '--get', 'user.email').stdout.strip() == 'builder@example.test'
    git(repo, 'config', '--local', '--unset', 'user.email')
    assert git(tree, 'config', '--worktree', '--get', 'user.email').stdout.strip() == 'builder@example.test'


def test_worktree_identity_skip_warns(fake, capsys):
    root, vcs = fake
    repos(root, 'app', identity=True)
    vcs.results['worktree_identity'] = registry.Result(
        1, None, 'git.worktree_identity: extensions.worktreeConfig is off')
    assert main(['worktree', 'add', 'X']) == 0
    assert 'extensions.worktreeConfig is off' in capsys.readouterr().err


def test_worktree_adopted_event_is_reserved(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    (tmp_path / '.wuwei').mkdir()
    assert main(['event', 'worktree.adopted', '{}']) == 1
    assert 'wuwei worktree adopt' in capsys.readouterr().err


def adopt_workspace(tmp_path, monkeypatch, config=''):
    """A configured repository with husky-style hooks, a house worktree on feature-x and item A."""
    root, repo = hooked_workspace(tmp_path, monkeypatch, config)
    (repo / '.husky').mkdir()
    marker_hooks(repo / '.husky/_', root / 'marker.txt', 'pre-commit')
    (repo / 'a.txt').write_text('a\n')
    git(repo, 'add', '.husky', 'a.txt')
    assert git(repo, 'commit', '-qm', 'husky').returncode == 0
    assert git(repo, 'push', '-q', 'origin', 'main').returncode == 0
    git(repo, 'config', 'core.hooksPath', '.husky/_')
    git(repo, 'branch', 'feature-x')
    tree = root / 'house/feature-x'
    assert git(repo, 'worktree', 'add', '-q', str(tree), 'feature-x').returncode == 0
    state._write_state(lambda data: data.update(items={'A': {}, 'B': {}},
                                                approved_items=['A', 'B']), root, reserved=False)
    return root, repo, tree


def day_events(root):
    return [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]


def test_worktree_adopt_chains_hooks_and_anchors(tmp_path, monkeypatch, capsys):
    root, repo, tree = adopt_workspace(
        tmp_path, monkeypatch, 'identity = {name = "Builder", email = "builder@example.test"}\n')
    assert main(['worktree', 'adopt', str(tree), '--item', 'A']) == 0, capsys.readouterr().err
    head = git(tree, 'rev-parse', 'HEAD').stdout.strip()
    assert json.loads(capsys.readouterr().out) == {'item': 'A', 'path': str(tree), 'head': head}
    assert state.read_state(root)['items']['A']['worktree'] == str(tree)
    event = day_events(root)[-1]
    assert event['kind'] == 'worktree.adopted' and event['payload']['head'] == head
    git_dir = Path(git(tree, 'rev-parse', '--absolute-git-dir').stdout.strip())
    assert (git_dir / 'wuwei-workspace').read_text().strip() == str(root)
    assert git(tree, 'config', '--worktree', '--get', 'user.email').stdout.strip() == 'builder@example.test'
    committed, _ = commit_and_push(tree)
    assert committed.returncode == 0, committed.stderr
    assert 'git-hook pre-commit' in (root / 'record.txt').read_text()
    assert (root / 'marker.txt').read_text().split() == ['pre-commit']


def test_worktree_adopt_refuses_a_dirty_tree(tmp_path, monkeypatch, capsys):
    root, repo, tree = adopt_workspace(tmp_path, monkeypatch)
    (tree / 'a.txt').write_text('changed\n')
    (tree / 'b.txt').write_text('new\n')
    before = (workspace.day_dir(root) / 'state.json').read_bytes(), len(day_events(root))
    assert main(['worktree', 'adopt', str(tree), '--item', 'A']) == 1
    err = capsys.readouterr().err
    assert 'a.txt' in err and 'b.txt' in err and 'stash push --include-untracked' in err
    assert ((workspace.day_dir(root) / 'state.json').read_bytes(), len(day_events(root))) == before
    assert git(repo, 'config', '--local', '--get', 'extensions.worktreeConfig').returncode == 1


def test_worktree_adopt_preconditions(tmp_path, monkeypatch, capsys):
    root, repo, tree = adopt_workspace(tmp_path, monkeypatch)
    (root / 'plain').mkdir()
    other = root / 'other'
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(other)], check=True)
    git(other, '-c', 'user.name=B', '-c', 'user.email=b@example.test', 'commit', '-q', '--allow-empty', '-m', 'x')
    git(other, 'worktree', 'add', '-q', '-b', 'y', str(root / 'other-y'))
    before = (workspace.day_dir(root) / 'state.json').read_bytes()
    for path in (root / 'plain', root / 'other-y', repo):
        assert main(['worktree', 'adopt', str(path), '--item', 'A']) == 1
    assert 'worktree add A --branch' in capsys.readouterr().err
    assert (workspace.day_dir(root) / 'state.json').read_bytes() == before
    assert main(['worktree', 'adopt', str(tree), '--item', 'A']) == 0
    git(repo, 'worktree', 'add', '-q', '-b', 'z', str(root / 'house/z'))
    assert main(['worktree', 'adopt', str(root / 'house/z'), '--item', 'A']) == 1
    assert 'another worktree' in capsys.readouterr().err
    state._write_state(lambda data: data.update(gate_approved=False), root, reserved=False)
    assert main(['worktree', 'adopt', str(root / 'house/z'), '--item', 'B']) == 1
    assert 'gate' in capsys.readouterr().err


def test_worktree_adopt_refuses_a_subdirectory_and_a_shared_tree(tmp_path, monkeypatch, capsys):
    root, repo, tree = adopt_workspace(tmp_path, monkeypatch)
    assert main(['worktree', 'adopt', str(tree / '.husky'), '--item', 'A']) == 1
    assert str(tree) in capsys.readouterr().err
    assert 'worktree' not in state.read_state(root)['items']['A']
    assert main(['worktree', 'adopt', str(tree), '--item', 'A']) == 0
    capsys.readouterr()
    assert main(['worktree', 'adopt', str(tree), '--item', 'B']) == 1
    assert 'item A already records' in capsys.readouterr().err
    assert 'worktree' not in state.read_state(root)['items']['B']


def test_worktree_add_on_an_existing_branch(tmp_path, monkeypatch, capsys):
    root, repo, _ = adopt_workspace(tmp_path, monkeypatch)
    git(repo, 'worktree', 'remove', str(root / 'house/feature-x'))
    assert main(['worktree', 'add', 'A', '--branch', 'feature-x']) == 0, capsys.readouterr().err
    tree = root / 'worktrees/A'
    assert git(tree, 'branch', '--show-current').stdout.strip() == 'feature-x'
    assert git(repo, 'branch', '--list', 'a').stdout == ''
    assert state.read_state(root)['items']['A']['worktree'] == str(tree)
    committed, _ = commit_and_push(tree)
    assert committed.returncode == 0, committed.stderr
    assert 'git-hook pre-commit' in (root / 'record.txt').read_text()
    assert main(['worktree', 'add', 'B']) == 0
    assert git(repo, 'branch', '--list', '--format=%(refname:short)', 'b').stdout.strip() == 'b'
    assert 'worktree' not in state.read_state(root)['items']['B']


def test_claimed_pr_fix_round_after_adoption(tmp_path, monkeypatch, capsys):
    import shlex
    from fakes.code_host import Fake as Host
    root, repo, house = adopt_workspace(tmp_path, monkeypatch, 'fast_checks = ["true"]\n')
    config = root / '.wuwei/config.toml'
    config.write_text('[owner]\nhandles = ["builder"]\n'
                      + config.read_text().replace('name = "app"', 'name = "acme/widget"'))
    git(repo, 'worktree', 'remove', str(house))
    git(repo, 'push', '-q', 'origin', 'main')
    git(repo, 'fetch', '-q', 'origin')
    state._write_state(lambda data: data.update(goals=['G-1']), root, reserved=False)
    host = Host()
    host.results['pr'].data.update(branch='feature-x', merged=False,
                                   head=git(repo, 'rev-parse', 'feature-x').stdout.strip())
    host.results['reviews'] = registry.Result(0, [])
    host.results['threads'] = registry.Result(0, {'comments': [], 'threads': []})
    host.results['checks'] = registry.Result(0, [{'name': 'tests', 'sha': host.results['pr'].data['head'],
        'state': 'completed', 'conclusion': 'failure', 'url': 'https://example.test/check'}])
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'code_host' else load(kind, config))
    ref = 'acme/widget#7'
    assert main(['pr', 'claim', ref, '--goal', 'G-1']) == 0, capsys.readouterr()
    capsys.readouterr()
    assert main(['pr', 'act', ref]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['command'] == 'bin/wuwei worktree add PR-7 --branch feature-x --repo acme/widget'
    assert main(shlex.split(action['command'])[1:]) == 0, capsys.readouterr().err
    capsys.readouterr()
    assert main(['pr', 'act', ref]) == 1
    tree = root / 'worktrees/PR-7'
    launched = json.loads(capsys.readouterr().out)
    assert launched['action'] == 'launch' and launched['worktree'] == str(tree)
    committed, _ = commit_and_push(tree)
    assert committed.returncode == 0, committed.stderr
    assert (root / 'marker.txt').read_text().split() == ['pre-commit']


def test_worktree_add_runs_checks_bootstrap_once(tmp_path, monkeypatch, capsys):
    # #520: the bootstrap builds the new worktree's own venv; the check then runs in it.
    boot = tmp_path / 'boot.sh'
    boot.write_text(f'echo run >> "{tmp_path / "count.txt"}"\nmkdir -p .venv/bin\n'
                    "printf '#!/bin/sh\\nexit 0\\n' > .venv/bin/python\nchmod +x .venv/bin/python\n")
    root, repo = hooked_workspace(tmp_path, monkeypatch, 'fast_checks = [".venv/bin/python -m pytest -q"]\n'
                                  f'[checks]\nbootstrap = "sh {boot}"\n')
    assert main(['worktree', 'add', 'X']) == 0
    tree = root / 'worktrees/X'
    assert (root / 'count.txt').read_text() == 'run\n'
    assert (tree / '.venv/bin/python').exists()
    assert 'warning' not in capsys.readouterr().err
    assert main(['fast-checks', str(tree)]) == 0
    row = state.read_state(root)['fast_checks']['app']['.venv/bin/python -m pytest -q']
    assert row['exit'] == 0 and row['interpreter'] == str(tree / '.venv/bin/python')


def checked(root, vcs, monkeypatch, check, bootstrap='', result=registry.Result(0)):
    (root / '.wuwei/config.toml').write_text(
        f'[[repos]]\nname = "app"\npath = "app"\ndefault_branch = "main"\nfast_checks = ["{check}"]\n'
        + (f'[checks]\nbootstrap = "{bootstrap}"\n' if bootstrap else ''))
    runs = []
    port = SimpleNamespace(run=lambda path, command, root=None: runs.append((path, command)) or result)
    monkeypatch.setattr(registry, 'load', lambda kind, config: port if kind == 'checks' else vcs)
    return runs


@pytest.mark.parametrize('result,line', [
    (registry.Result(1, {'error': 'install output'}), 'wuwei worktree warning: checks.bootstrap exited 1'),
    (registry.Result(2, reason='fast check could not run: TimeoutExpired'),
     'wuwei worktree warning: checks.bootstrap exited 2: fast check could not run: TimeoutExpired'),
])
def test_worktree_add_failed_bootstrap_warns(fake, monkeypatch, capsys, result, line):
    root, vcs = fake
    runs = checked(root, vcs, monkeypatch, '.venv/bin/python -m pytest -q', 'make venv', result)
    assert main(['worktree', 'add', 'X']) == 0
    assert runs == [(str(root / 'worktrees/X'), 'make venv')]
    out = capsys.readouterr()
    assert json.loads(out.out) == {'branch': 'x', 'path': 'p', 'start': 'a' * 40}
    lines = out.err.splitlines()
    assert len(lines) == 1 and lines[0].startswith(line) and 'install output' not in out.err


@pytest.mark.parametrize('check,warned', [('.venv/bin/python -m pytest -q', True), ('python3 -m pytest -q', False)])
def test_worktree_add_warns_when_the_check_uses_the_main_worktree(fake, monkeypatch, capsys, check, warned):
    root, vcs = fake
    runs = checked(root, vcs, monkeypatch, check)
    python = root / 'app/.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.write_text('')
    assert main(['worktree', 'add', 'X']) == 0
    err = capsys.readouterr().err
    assert not runs
    if warned:
        lines = err.splitlines()
        assert len(lines) == 1 and lines[0].startswith('wuwei worktree warning:')
        assert str(python.resolve()) in err and '[checks] bootstrap' in err
    else:
        assert 'warning' not in err


def test_worktree_add_starts_at_the_fetched_origin_head(tmp_path, monkeypatch, capsys):
    # #681: local main is one commit behind origin; the new worktree starts at origin's head.
    root, repo = hooked_workspace(tmp_path, monkeypatch)
    origin, other = root / 'origin.git', root / 'other'
    subprocess.run(['git', 'clone', '-q', str(origin), str(other)], check=True)
    assert git(other, '-c', 'user.name=O', '-c', 'user.email=o@example.test',
               'commit', '-q', '--allow-empty', '-m', 'merged').returncode == 0
    assert git(other, 'push', '-q', 'origin', 'main').returncode == 0
    ahead = git(other, 'rev-parse', 'HEAD').stdout.strip()
    assert git(repo, 'rev-parse', 'main').stdout.strip() != ahead
    assert main(['worktree', 'add', 'X']) == 0, capsys.readouterr().err
    tree = root / 'worktrees/X'
    assert json.loads(capsys.readouterr().out)['start'] == ahead
    assert git(tree, 'rev-parse', 'HEAD').stdout.strip() == ahead
    git(repo, 'fetch', '-q', 'origin')
    assert git(tree, 'merge-base', 'HEAD', 'origin/main').stdout.strip() == ahead
    created = [row['payload'] for row in day_events(root) if row['kind'] == 'worktree.created']
    assert created == [{'item': 'X', 'worktree': str(tree), 'branch': 'x', 'base': 'origin/main', 'start': ahead}]


def test_worktree_add_refuses_when_the_fetch_fails(tmp_path, monkeypatch, capsys):
    root, repo = hooked_workspace(tmp_path, monkeypatch)
    git(repo, 'remote', 'set-url', 'origin', str(root / 'missing.git'))
    assert main(['worktree', 'add', 'X']) == 2
    err = capsys.readouterr().err
    assert 'could not fetch origin main' in err and 'no worktree was created' in err
    assert not (root / 'worktrees/X').exists()
    assert git(repo, 'branch', '--list', 'x').stdout == ''
    assert len(git(repo, 'worktree', 'list').stdout.splitlines()) == 1


def test_worktree_created_event_is_reserved(fake, capsys):
    assert main(['event', 'worktree.created', '{}']) == 1
    assert 'wuwei worktree add' in capsys.readouterr().err
