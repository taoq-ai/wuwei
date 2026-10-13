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
    assert {'unplanned': 'plan add D', 'other-repo': 'acme/web', 'other-worktree': 'different repositories',
            'parked': 'plan resume A'}[case] in err, err
    assert (workspace.day_dir(root) / 'state.json').read_bytes() == before


def running_seat(root, item='A'):
    state._write_state(lambda data: data['seats'].update({'b-a': {
        'id': 'b-a', 'role': 'builder', 'item': item, 'brief': 'x', 'status': 'running',
        'started_at': '2026-10-12T11:00:00+00:00'}}), root)


def test_a_running_builder_seat_with_no_build_record_refuses_reconcile(ws, capsys):
    # review F1: a seat still committing must stop before its work is verified
    root, trees, checks = ws
    running_seat(root)
    before = (workspace.day_dir(root) / 'state.json').read_bytes()
    assert reconcile('A', '--worktree', trees['A']) == 1
    assert 'builder seat b-a is running on A' in capsys.readouterr().err
    assert (workspace.day_dir(root) / 'state.json').read_bytes() == before and checks == []


@pytest.mark.parametrize('flag', ['--repo', '--pr'])
def test_another_repository_never_overrides_the_items(ws, capsys, flag):
    # review F2: the item's recorded repository needs an explicit resolution to change
    root, trees, _ = ws
    args = ['--worktree', trees['B'], '--repo', 'acme/web'] if flag == '--repo' else ['--pr', 'acme/web#7']
    before = (workspace.day_dir(root) / 'state.json').read_bytes()
    assert reconcile('A', *args) == 1
    assert 'A is for acme/widget' in capsys.readouterr().err
    assert (workspace.day_dir(root) / 'state.json').read_bytes() == before


def test_a_hand_commit_after_the_checks_never_reaches_the_gates_unchecked(ws, capsys):
    # review residual: a gate reviews the head the fast checks passed on, on every path
    from wuwei import brief
    root, trees, checks = ws
    assert reconcile('A', '--worktree', trees['A']) == 0
    assert state.read_state(root)['builds']['A']['checked'] == git(trees['A'], 'rev-parse', 'HEAD')
    (trees['A'] / 'secret.txt').write_text('unchecked\n')
    git(trees['A'], 'add', '.')
    git(trees['A'], 'commit', '-q', '-m', 'by hand')
    head = git(trees['A'], 'rev-parse', 'HEAD')
    with pytest.raises(brief.Refused, match='fast checks passed on'):
        brief.gate_ready(state.read_state(root), 'A', head)
    action = dispatch.next_step('A', root)
    assert action['action'] == 'check' and action['command'] == 'wuwei build check A'
    with pytest.raises(dispatch.Refused, match='A build is check, not done'):
        dispatch.next_step('A', root)
    assert main(['build', 'check', 'A']) == 0 and checks == ['A', 'A']
    assert state.read_state(root)['builds']['A']['checked'] == head
    assert dispatch.next_step('A', root)['action'] == 'gates'


def test_a_failing_outside_loop_still_parks(ws, capsys, monkeypatch):
    # review F3: repeats carry across reconciles at new heads
    root, trees, _ = ws
    load = registry.load
    runner = SimpleNamespace(run=lambda path, command, **kw: registry.Result(1, {'error': 'boom'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: runner if kind == 'checks' else load(kind, config))
    for n in range(3):
        (trees['A'] / f'f{n}.txt').write_text('x\n')
        git(trees['A'], 'add', '.')
        git(trees['A'], 'commit', '-q', '-m', f'round {n}')
        reconcile('A', '--worktree', trees['A'])
    assert state.read_state(root)['items']['A']['phase'] == 'parked'
    capsys.readouterr()


def test_pr_stdout_is_one_json_document_and_verified_lists_passes(ws, capsys, monkeypatch):
    # review F5
    from fakes.code_host import Fake as Host
    root, trees, _ = ws
    host = Host()
    host.results['pr'].data.update(branch='feature-a', head=git(trees['A'], 'rev-parse', 'HEAD'))
    load = registry.load
    runner = SimpleNamespace(run=lambda path, command, **kw: registry.Result(1, {'error': 'boom'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'code_host'
                        else runner if kind == 'checks' else load(kind, config))
    assert reconcile('A', '--worktree', trees['A'], '--pr', 'acme/widget#7') == 0
    out = json.loads(capsys.readouterr().out)
    assert out['verified'] == [] and out['failed'] == ['check: exit 1 at ' + out['head'][:12]]


def test_reconcile_takes_the_track_a_protected_path_needs(ws, capsys):
    # review F7
    root, trees, _ = ws
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write('[brief]\nfull_path_patterns = ["(^|/)guards/"]\n')
    (trees['A'] / 'guards').mkdir()
    (trees['A'] / 'guards/x.py').write_text('x = 1\n')
    git(trees['A'], 'add', '.')
    git(trees['A'], 'commit', '-q', '-m', 'guard')
    assert reconcile('A', '--worktree', trees['A']) == 1
    assert 'rerun bin/wuwei build reconcile A with --track FULL' in capsys.readouterr().err
    assert reconcile('A', '--worktree', trees['A'], '--track', 'FULL') == 0, capsys.readouterr()
    assert state.read_state(root)['items']['A']['track'] == 'FULL'


@pytest.mark.parametrize('case', ['private', 'dirty'])
def test_a_recheck_at_the_gate_runs_every_build_check(ws, capsys, case):
    # review D1, D2: a recheck is a whole build check (private files, uncommitted changes), and
    # checked is the head the checks measured
    root, trees, checks = ws
    tree = trees['A']
    assert reconcile('A', '--worktree', tree) == 0
    if case == 'private':
        (tree / '.env').write_text('TOKEN=x\n')
        git(tree, 'add', '-f', '.env')
        git(tree, 'commit', '-q', '-m', 'secret')
    else:
        (tree / 'work.txt').write_text('broken\n')
        git(tree, 'commit', '-q', '-am', 'broken')
        (tree / 'work.txt').write_text('fixed, not committed\n')
    checked = state.read_state(root)['builds']['A']['checked']
    assert dispatch.next_step('A', root)['action'] == 'check'
    assert main(['build', 'check', 'A']) == 1
    build = state.read_state(root)['builds']['A']
    assert build['status'] == 'ready' and build['checked'] == checked
    assert ('.env' if case == 'private' else 'uncommitted changes') in build['action']['feedback']
    with pytest.raises(dispatch.Refused, match='not done'):
        dispatch.next_step('A', root)


def test_checked_is_the_head_the_checks_measured(ws, capsys, monkeypatch):
    # review D2: a commit after the checks measured HEAD is not the checked head
    from wuwei import fast_checks
    root, trees, _ = ws
    record = fast_checks.record

    def moved(path):
        code = record(path)
        (Path(path) / 'late.txt').write_text('late\n')
        git(path, 'add', 'late.txt')
        git(path, 'commit', '-q', '-m', 'late')
        return code
    measured = git(trees['A'], 'rev-parse', 'HEAD')
    monkeypatch.setattr(fast_checks, 'record', moved)
    assert reconcile('A', '--worktree', trees['A']) == 0
    assert state.read_state(root)['builds']['A']['checked'] == measured
    assert dispatch.next_step('A', root)['action'] == 'check'  # the late commit is checked first


@pytest.mark.parametrize('change', ['none', 'head', 'live', 'foreign', 'missing', 'reappeared'])
def test_reconcile_different_tree_needs_owner_on_both_heads(ws, capsys, change):
    from wuwei import brief, sessions
    from wuwei.commands import build
    root, trees, checks = ws
    old = root / 'house/spec-only'
    git(trees['A'], 'worktree', 'add', '-q', '-b', 'spec-only', str(old), 'origin/main')
    state._write_state(lambda data: data['items']['A'].update(worktree=str(old)), root)
    brief.write('builder', 'A', 'spec-only', 'Finish the spec', worktree=str(old), root=root)
    build.next_action('A', root=root)
    if change in ('missing', 'reappeared'):
        git(trees['A'], 'worktree', 'remove', str(old))
    requested = trees['B'] if change == 'foreign' else trees['A']
    before = state.read_state(root)
    assert reconcile('A', '--worktree', requested) == 1
    reason = capsys.readouterr().err
    if change == 'foreign':
        assert 'not of acme/widget' in reason and 'Owner step' not in reason
        assert state.read_state(root) == before
        return
    assert str(old) in reason and str(requested) in reason
    assert ('missing' if change in ('missing', 'reappeared') else git(old, 'rev-parse', 'HEAD')) in reason
    assert git(requested, 'rev-parse', 'HEAD') in reason
    card = json.loads(reason.split('; card: ', 1)[1])
    assert card['record'] == f'bin/wuwei build reconcile A --worktree {requested}'
    assert state.read_state(root) == before and checks == []
    state.append_event('gate.asked', {'topics': [sessions.owner_topic(card['question']),
                                              sessions.owner_topic(card['question'], 'Yes')]}, root)
    if change == 'head':
        git(requested, 'commit', '-q', '--allow-empty', '-m', 'moved after approval')
    elif change == 'live':
        state._write_state(lambda data: data['seats'].update(builder={
            'item': 'A', 'role': 'builder', 'status': 'running', 'brief': 'brief.md'}), root)
    elif change == 'reappeared':
        git(trees['A'], 'worktree', 'add', '-q', str(old), 'spec-only')
    code = reconcile('A', '--worktree', requested)
    if change not in ('none', 'missing'):
        assert code == 1, capsys.readouterr().err
        assert state.read_state(root)['items']['A']['worktree'] == str(old) and checks == []
        return
    assert code == 0, capsys.readouterr().err
    data = state.read_state(root)
    assert data['items']['A']['worktree'] == str(requested)
    assert data['items']['A']['phase'] == 'gate' and checks == ['A']
    assert data['builds']['A']['checked'] == git(requested, 'rev-parse', 'HEAD')


@pytest.mark.parametrize('completed', [False, True])
def test_explicit_reconcile_requires_completion_after_lost_stop(ws, capsys, completed):
    from wuwei import brief
    from wuwei.commands import build
    root, trees, checks = ws
    tree = trees['A']
    state._write_state(lambda data: data['items']['A'].update(worktree=str(tree)), root)
    relative = brief.write('builder', 'A', 'builder', 'Finish the brief', worktree=str(tree), root=root)
    build.next_action('A', root=root)
    start = git(tree, 'rev-parse', 'origin/main')

    def lost(data):
        data['seats']['builder'] = {'role': 'builder', 'item': 'A', 'brief': relative,
                                    'status': 'unmeasured', 'reason': 'stop payload unreadable'}
        data['builds']['A'].update(status='running', seat='builder', start=start)
    state._write_state(lost, root)
    if not completed:
        before = state.read_state(root)
        assert reconcile('A', '--worktree', tree) == 1
        assert 'wait for' in capsys.readouterr().err
        assert state.read_state(root) == before and checks == []
        return
    from test_handback import HANDBACK
    transcript = root / 'finished.jsonl'
    transcript.write_text(HANDBACK)
    state._write_state(lambda data: data['seats']['builder'].update(transcript=str(transcript)), root)
    for _ in range(2):
        assert reconcile('A', '--worktree', tree) == 0, capsys.readouterr().err
    data = state.read_state(root)
    assert data['items']['A']['phase'] == 'gate' and checks == ['A']
    assert 'result' not in data['builds']['A']
    assert data['seats']['builder']['status'] == 'unmeasured'
    assert dispatch.next_step('A', root)['action'] == 'gates'


@pytest.mark.parametrize("seat_status", ["stopped", "unmeasured"])
def test_reconcile_resultless_build_preserves_business_blocker(ws, capsys, seat_status):
    from wuwei import brief
    from wuwei.commands import build
    root, trees, checks = ws
    tree = trees['A']
    state._write_state(lambda data: data['items']['A'].update(worktree=str(tree)), root)
    relative = brief.write('builder', 'A', 'builder', 'Finish the brief', worktree=str(tree), root=root)
    build.next_action('A', root=root)

    def blocked(data):
        data['seats']['builder'] = {'role': 'builder', 'item': 'A', 'brief': relative,
                                    'status': seat_status, 'agent_id': 'agent-builder'}
        data['builds']['A'].update(seat='builder', status='running' if seat_status == 'unmeasured' else 'ready')
    state._write_state(blocked, root)
    state.append_event('retro.captured', {'agent_id': 'agent-builder', 'fields': {
        'Blocked': 'owner approval required for schema change', 'Gap': 'none', 'Change': 'none'}}, root)
    assert reconcile('A', '--worktree', tree) == 1
    assert 'build next A' in capsys.readouterr().err
    assert checks == [] and state.read_state(root)['items']['A']['phase'] == 'implement'
