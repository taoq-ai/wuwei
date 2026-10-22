import json
import subprocess

import pytest

from wuwei import plan, sync, ws


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


SCORES = {'value': 1, 'time': 1, 'risk': 1, 'size': 1}


def test_two_clones_that_each_add_an_item_both_keep_both(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    plan.add(a, 'I-1', 'first', 'G-1', 'acme/app', 'light', SCORES)
    sync.push(a)
    b = clone(remote, tmp_path / 'b')
    sync.restore(b)
    plan.add(a, 'A-2', 'from a', 'G-1', 'acme/app', 'light', SCORES)
    plan.add(b, 'B-2', 'from b', 'G-1', 'acme/app', 'light', SCORES)
    plan.mark(b, 'I-1', 'parked', 'b parks it')
    sync.push(a)
    assert sync.push(b).startswith('pushed')  # b never pulled a's item: the push merges it in, never drops it
    assert {i['id'] for i in plan.items(b)} == {'I-1', 'A-2', 'B-2'}
    assert sync.pull(a).startswith('pulled') and {i['id'] for i in plan.items(a)} == {'I-1', 'A-2', 'B-2'}
    assert plan.find(a, 'I-1')['status'] == 'parked'
    shown = json.loads(git(a, 'show', 'origin/' + sync.BRANCH + ':plan.json'))['items']
    assert {i['id'] for i in shown} == {'I-1', 'A-2', 'B-2'}


def test_the_newest_change_to_an_item_wins_whichever_clone_syncs_last(remote, tmp_path):
    a = workspace(clone(remote, tmp_path / 'a'))
    plan.add(a, 'I-1', 'first', 'G-1', 'acme/app', 'light', SCORES)
    sync.push(a)
    b = clone(remote, tmp_path / 'b')
    sync.restore(b)
    plan.mark(b, 'I-1', 'parked', 'older change')
    plan.mark(a, 'I-1', 'dropped', 'newer change')
    sync.push(a)
    assert 'kept local' not in sync.pull(b)  # changed here and there: merged by item, the newer change wins
    assert plan.find(b, 'I-1')['reason'] == 'newer change'
    sync.push(b)
    assert json.loads(git(b, 'show', 'origin/' + sync.BRANCH + ':plan.json'))['items'][0]['reason'] == 'newer change'


def test_a_plan_change_stamps_only_the_items_it_changed(root, monkeypatch):
    import datetime
    plan.add(root, 'I-1', 'one', 'G-1', 'acme/app', 'light', SCORES)
    plan.add(root, 'I-2', 'two', 'G-1', 'acme/app', 'light', SCORES)
    first = {i['id']: i['changed'] for i in plan.items(root)}
    later = ws.now() + datetime.timedelta(minutes=5)
    monkeypatch.setattr(ws, 'now', lambda: later)
    plan.mark(root, 'I-2', 'parked', 'later')
    assert {i['id']: i['changed'] for i in plan.items(root)} == {'I-1': first['I-1'], 'I-2': later.isoformat()}
    newer = (later + datetime.timedelta(minutes=1)).isoformat()
    monkeypatch.setattr(ws, 'now', lambda: later + datetime.timedelta(minutes=9))
    assert plan.merge(root, json.dumps({'items': [{'id': 'I-1', 'title': 'theirs', 'changed': newer}]}))
    assert (plan.find(root, 'I-1')['title'], plan.find(root, 'I-1')['changed']) == ('theirs', newer)  # merged in, never stamped again


def test_on_a_tie_this_clones_item_stays(root):
    from conftest import write_plan
    write_plan(root, [{'id': 'I-1', 'title': 'mine', 'status': 'open'}])  # an item from before the stamps
    assert plan.merge(root, json.dumps({'items': [{'id': 'I-1', 'title': 'theirs', 'status': 'open'}, {'id': 'I-9', 'title': 'new'}]}))
    assert [(i['id'], i['title']) for i in plan.items(root)] == [('I-1', 'mine'), ('I-9', 'new')]


@pytest.mark.parametrize('theirs', [b'not json', b'{"items": ["I-1"]}', b'{"items": [{"title": "no id"}]}', b'[]',
                                    b'{"items": [{"id": "I-1", "changed": 5}]}', b'{"items": {"id": "I-1"}}'])
def test_a_plan_that_is_not_a_plan_is_never_merged(root, theirs):
    plan.add(root, 'I-1', 'one', 'G-1', 'acme/app', 'light', SCORES)
    before = (root / ws.DIR / 'plan.json').read_bytes()
    assert not plan.merge(root, theirs) and (root / ws.DIR / 'plan.json').read_bytes() == before
