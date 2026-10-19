import json
import subprocess

import pytest

from wuwei import sync, ws


def git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / 'remote.git'
    git(tmp_path, 'init', '-q', '--bare', '-b', 'main', str(bare))
    seed = tmp_path / 'seed'
    git(tmp_path, 'clone', '-q', str(bare), str(seed))
    (seed / 'README.md').write_text('app\n')
    git(seed, 'add', '.')
    git(seed, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init')
    git(seed, 'push', '-q', 'origin', 'main')
    return bare


def clone(remote, path):
    git(remote.parent, 'clone', '-q', str(remote), str(path))
    git(path, 'config', 'user.name', 'Owner')
    git(path, 'config', 'user.email', 'owner@example.com')
    return path


def workspace(path):
    (path / ws.DIR).mkdir()
    ws.write_config(path, {**ws.DEFAULTS, 'repos': ['acme/app']})
    return path


def test_a_fresh_clone_starts_where_the_last_session_stopped(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    (a / ws.DIR / 'plan.json').write_text('{"items": ["I-1"]}\n')
    ws.record(a, 'plan.approved', {})
    ws.trace(a, {'tool': 'Bash'})
    assert sync.push(a).startswith('pushed')
    b = clone(remote, tmp_path / 'b')
    assert sync.restore(b) == b
    assert (b / ws.DIR / 'plan.json').read_text() == '{"items": ["I-1"]}\n'
    assert [r['kind'] for r in ws.ledger(b)] == ['plan.approved']
    assert not (b / ws.DIR / 'traces.jsonl').exists()
    assert git(b, 'log', '--format=%s', 'main') == 'init'  # the working branch never carries the state


def test_two_clones_never_lose_each_others_ledger_rows(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    ws.record(a, 'from-a', {})
    sync.push(a)
    b = clone(remote, tmp_path / 'b')
    sync.restore(b)
    ws.record(b, 'from-b', {})
    sync.push(b)
    ws.record(a, 'from-a-again', {})
    sync.push(a)  # a never pulled b's row; it must not drop it
    c = clone(remote, tmp_path / 'c')
    sync.restore(c)
    assert sorted(r['kind'] for r in ws.ledger(c)) == ['from-a', 'from-a-again', 'from-b']
    assert ws.verify(c) == []


def test_a_file_changed_here_and_there_keeps_the_local_copy(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    (a / ws.DIR / 'plan.json').write_text('v1')
    sync.push(a)
    b = clone(remote, tmp_path / 'b')
    sync.restore(b)
    (a / ws.DIR / 'plan.json').write_text('v2')
    sync.push(a)
    assert 'plan.json' not in sync.pull(b) and (b / ws.DIR / 'plan.json').read_text() == 'v2'
    (a / ws.DIR / 'plan.json').write_text('v3')
    sync.push(a)
    (b / ws.DIR / 'plan.json').write_text('mine')
    assert 'kept local plan.json' in sync.pull(b)
    assert (b / ws.DIR / 'plan.json').read_text() == 'mine'


def test_nothing_new_pushes_nothing(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    sync.push(a)
    assert sync.push(a) == 'state already pushed'


def test_outside_git_the_state_stays_local(root):
    assert 'state stays local' in sync.push(root)
    assert sync.restore(root) == root


def test_a_change_after_the_first_push_reaches_the_branch(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    (a / ws.DIR / 'plan.json').write_text('v1')
    sync.push(a)
    (a / ws.DIR / 'plan.json').write_text('v2')
    assert 'plan.json' not in sync.pull(a) and (a / ws.DIR / 'plan.json').read_text() == 'v2'
    assert sync.push(a).startswith('pushed')
    assert git(a, 'show', 'origin/wuwei/state:plan.json') == 'v2'


def test_a_kept_local_copy_is_pushed(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    (a / ws.DIR / 'plan.json').write_text('v1')
    sync.push(a)
    b = clone(remote, tmp_path / 'b')
    sync.restore(b)
    (a / ws.DIR / 'plan.json').write_text('theirs')
    sync.push(a)
    (b / ws.DIR / 'plan.json').write_text('mine')
    assert 'kept local plan.json' in sync.pull(b)
    assert sync.push(b).startswith('pushed')
    assert git(b, 'show', 'origin/wuwei/state:plan.json') == 'mine'


def test_a_pull_never_writes_through_a_link_planted_under_the_workspace(remote, tmp_path, monkeypatch, capsys):
    from wuwei import __main__ as cli
    a = workspace(clone(remote, tmp_path / 'a'))
    (a / ws.DIR / 'verdicts' / 'x').mkdir(parents=True)
    (a / ws.DIR / 'verdicts' / 'x' / 'quality-abc1234.md').write_text('verdict\n')
    sync.push(a)
    b = workspace(clone(remote, tmp_path / 'b'))
    ws.record(b, 'from-b', {})
    (b / ws.DIR / 'verdicts').mkdir()
    (b / ws.DIR / 'verdicts' / 'x').symlink_to(b / ws.DIR / 'ledger')
    monkeypatch.chdir(b)
    assert cli.main(['sync']) == 1  # the pull stops at the link and names the file it was writing, with no traceback
    assert (err := capsys.readouterr().err).startswith('wuwei sync: ') and '.wuwei/verdicts/x/quality-abc1234.md' in err
    assert sorted(p.name for p in (b / ws.DIR / 'ledger').iterdir()) == [f'{ws.clone(b)}.jsonl']
