"""#901: `build reconcile` brings work done outside the record back in, in real repositories."""

import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from wuwei import dispatch, registry, state, workspace
from wuwei.__main__ import main
from wuwei.guards import agent_launch

REPOS = {'A': 'acme/widget', 'B': 'acme/web', 'C': 'acme/api'}


def git(tree, *args):
    found = subprocess.run(['git', '-C', str(tree), *args], capture_output=True, text=True)
    assert found.returncode == 0, found.stderr
    return found.stdout.strip()


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """Three configured repositories with bare origins; items A (planned), B (implement, no build
    record) and C (planned), one per repository, each with a worktree of outside commits."""
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    root = tmp_path.resolve()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-12T12:00:00+00:00')
    monkeypatch.chdir(root)
    config, trees = '', {}
    for item, name in REPOS.items():
        repo, origin = root / name.split('/')[1], root / (name.split('/')[1] + '.git')
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(origin)], check=True)
        git(repo, 'remote', 'add', 'origin', str(origin))
        git(repo, 'config', 'user.name', 'Builder')
        git(repo, 'config', 'user.email', 'builder@example.test')
        git(repo, 'commit', '-q', '--allow-empty', '-m', 'start')
        git(repo, 'push', '-q', 'origin', 'main')
        git(repo, 'fetch', '-q', 'origin')
        tree = trees[item] = root / 'house' / item
        git(repo, 'worktree', 'add', '-q', '-b', 'feature-' + item.lower(), str(tree))
        (tree / 'work.txt').write_text(f'{item}\n')
        git(tree, 'add', 'work.txt')
        git(tree, 'commit', '-q', '-m', f'outside work on {item}')
        config += (f'[[repos]]\nname = "{name}"\npath = "{repo.name}"\ndefault_branch = "main"\n'
                   'fast_checks = ["check"]\n')
    (trees['C'] / 'loose.txt').write_text('not committed\n')
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text(config + '[spec]\nengine = "none"\n')
    checks = []
    load = registry.load
    runner = SimpleNamespace(run=lambda path, command, **kw: checks.append(Path(path).name) or registry.Result(0))
    monkeypatch.setattr(registry, 'load', lambda kind, config: runner if kind == 'checks' else load(kind, config))
    monkeypatch.setattr(agent_launch, 'free_memory', lambda *a: 8 * 1024**3)

    def admit(data):
        data.update(gate_approved=True, goals=['G-1'], approved_items=list(REPOS))
        data['items'] = {item: {'phase': 'implement' if item == 'B' else 'planned', 'goal': 'G-1',
                                'repo': name} for item, name in REPOS.items()}
    state._write_state(admit, root)
    return root, trees, checks


def reconcile(*args):
    return main(['build', 'reconcile', *map(str, args)])


def written(root, item):
    return [row for row in state_events(root) if row['kind'] == 'brief written' and row['payload']['item'] == item]


def state_events(root):
    return [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]


def test_reconcile_brings_outside_work_back_in_three_repositories(ws, capsys):
    root, trees, checks = ws
    heads = {item: git(tree, 'rev-parse', 'HEAD') for item, tree in trees.items()}
    assert main(['build', 'check', 'B']) == 2  # no build record: the check names the re-entry
    assert 'bin/wuwei build reconcile B --worktree' in capsys.readouterr().err
    for _ in range(2):  # the repeat finds everything recorded and writes nothing
        for item, tree in trees.items():
            assert reconcile(item, '--worktree', tree) == 0, capsys.readouterr()
            out = json.loads(capsys.readouterr().out.splitlines()[-1])
            assert out['item'] == item and out['head'] == heads[item]
            assert 'gates' in ' '.join(out['unmeasured']) and 'owner approval' in ' '.join(out['unmeasured'])
    data = state.read_state(root)
    assert sorted(data['items']) == ['A', 'B', 'C'] and sorted(data['builds']) == ['A', 'B', 'C']
    assert checks == ['A', 'B', 'C']  # one fast-check run each, none on the repeat
    for item, tree in trees.items():
        assert data['items'][item]['worktree'] == str(tree)
        assert git(tree, 'rev-parse', 'HEAD') == heads[item]  # the work is preserved
        assert len(written(root, item)) == 1
        assert not data['seats']  # no builder seat is invented
    assert (trees['C'] / 'loose.txt').read_text() == 'not committed\n'
    assert len([row for row in state_events(root) if row['kind'] == 'build.reconciled']) == 3
    for item in ('A', 'B'):  # clean, committed work: verified, then the gates
        assert data['items'][item]['phase'] == 'gate' and data['builds'][item]['status'] == 'done'
        assert data['builds'][item]['start'] == git(trees[item], 'rev-parse', 'origin/main')
        assert dispatch.next_step(item, root)['action'] == 'gates'
    # dirty work is registered; the gates stay blocked; the builder commits it, and its launch registers
    build = data['builds']['C']
    assert data['items']['C']['phase'] == 'implement' and build['status'] == 'ready'
    assert build['action']['action'] == 'continue' and 'loose.txt' in build['action']['feedback']
    with pytest.raises(dispatch.Refused):
        dispatch.next_step('C', root)
    assert main(['build', 'next', 'C']) == 0
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'continue'
    code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build C', 'prompt': action['prompt']}})
    assert code == 0, reason
    assert state.read_state(root)['builds']['C']['status'] == 'running'


def test_an_unlaunched_build_record_keeps_its_start_and_takes_the_outside_work(ws, capsys):
    root, trees, checks = ws
    tree = trees['A']
    git(tree, 'reset', '-q', '--hard', 'origin/main')
    assert main(['seat', 'brief', 'builder', 'A', 'builder-a', '--worktree', str(tree), '--body', 'Build A']) == 0
    assert main(['build', 'next', 'A']) == 0
    record = state.read_state(root)['builds']['A']
    assert record['action']['action'] == 'launch'
    (tree / 'work.txt').write_text('done outside\n')
    git(tree, 'add', 'work.txt')
    git(tree, 'commit', '-q', '-m', 'outside')
    capsys.readouterr()
    assert reconcile('A', '--worktree', tree) == 0, capsys.readouterr()
    after = state.read_state(root)
    assert after['builds']['A']['start'] == record['start'] and after['builds']['A']['status'] == 'done'
    assert after['builds']['A']['brief'] != record['brief'] and after['items']['A']['phase'] == 'gate'


def test_an_interrupted_reconcile_finishes_on_the_rerun(ws, capsys, monkeypatch):
    root, trees, checks = ws
    from wuwei import fast_checks
    record = fast_checks.record

    def interrupted(path):
        raise OSError('interrupted')
    monkeypatch.setattr(fast_checks, 'record', interrupted)
    assert reconcile('B', '--worktree', trees['B']) == 2
    assert state.read_state(root)['builds']['B']['status'] == 'check'
    monkeypatch.setattr(fast_checks, 'record', record)
    assert reconcile('B', '--worktree', trees['B']) == 0, capsys.readouterr()
    data = state.read_state(root)
    assert data['items']['B']['phase'] == 'gate' and data['builds']['B']['status'] == 'done'
    assert len(written(root, 'B')) == 1 and checks == ['B']
    assert len([row for row in state_events(root) if row['kind'] == 'build.reconciled']) == 1


def test_reconcile_checks_out_an_existing_branch(ws, capsys):
    root, trees, checks = ws
    repo = root / 'widget'
    git(repo, 'worktree', 'remove', str(trees['A']))
    for _ in range(2):
        assert reconcile('A', '--repo', 'acme/widget', '--branch', 'feature-a') == 0, capsys.readouterr()
    tree = root / 'worktrees/A'
    assert git(tree, 'branch', '--show-current') == 'feature-a'
    data = state.read_state(root)
    assert data['items']['A']['worktree'] == str(tree) and data['items']['A']['phase'] == 'gate'
    assert checks == ['A']


def test_reconcile_with_a_pr_goes_through_checks_and_gates(ws, capsys, monkeypatch):
    from fakes.code_host import Fake as Host
    root, trees, checks = ws
    host = Host()
    host.results['pr'].data.update(branch='feature-a', head=git(trees['A'], 'rev-parse', 'HEAD'))
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'code_host' else load(kind, config))
    ref = 'acme/widget#7'
    for _ in range(2):
        assert reconcile('A', '--worktree', trees['A'], '--pr', ref) == 0, capsys.readouterr()
    data = state.read_state(root)
    assert sorted(data['items']) == ['A', 'B', 'C'] and data['claimed_prs'] == [ref]
    assert data['items']['A']['pr'] == ref and data['items']['A']['phase'] == 'gate'  # not raised
    assert dispatch.next_step('A', root)['action'] == 'gates'


@pytest.mark.parametrize('case', ['unplanned', 'other-repo', 'other-worktree', 'parked'])
def test_reconcile_refuses_what_needs_an_explicit_resolution(ws, capsys, case):
    root, trees, _ = ws
    item, args = 'A', ['--worktree', trees['A']]
    if case == 'unplanned':
        item = 'D'
    elif case == 'other-repo':
        args = ['--worktree', trees['B']]
    elif case == 'other-worktree':
        state._write_state(lambda data: data['items']['A'].update(worktree=str(trees['B'])), root)
    else:
        state._write_state(lambda data: data['items']['A'].update(phase='parked'), root)
    before = (workspace.day_dir(root) / 'state.json').read_bytes()
    assert reconcile(item, *args) == 1
    err = capsys.readouterr().err
    assert {'unplanned': 'plan add D', 'other-repo': 'acme/web', 'other-worktree': 'another worktree',
            'parked': 'plan resume A'}[case] in err, err
    assert (workspace.day_dir(root) / 'state.json').read_bytes() == before
