"""State writer contracts exercised through imports and real CLI processes."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:34:56+02:00'


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    return tmp_path


def day(root):
    return root / '.wuwei/days/2026-09-28'


def cli(*args):
    return subprocess.run(
        [sys.executable, '-S', '-m', 'wuwei', *args],
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')},
        capture_output=True, text=True,
    )


def events(root):
    return [json.loads(line) for line in (day(root) / 'events.jsonl').read_text().splitlines()]


def test_get_set_defaults_and_audit(workspace):
    result = cli('state', 'get')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        'items': {}, 'cap': 1, 'seat_policy': {}, 'envelope': {},
        'claimed_prs': [], 'raised_prs': [], 'gate_verdicts': {},
    }
    assert not day(workspace).exists()
    for path, value in [('items.A', {}), ('cap', 3), ('seat_policy.builder', {'model': 'x'}),
                        ('envelope', {'approved': True}), ('claimed_prs', [4]),
                        ('raised_prs', [5]), ('gate_verdicts.arch', 'PASS')]:
        result = cli('state', 'set', path, json.dumps(value))
        assert result.returncode == 0, result.stderr
    item = json.loads(cli('state', 'get', 'items.A').stdout)
    assert item == {'lane': 'build', 'status': 'queued', 'phase': 'planned',
                    'flags': dict.fromkeys(['trust_surface', 'boundary_relevant', 'agent_surface'], False),
                    'gates': {}, 'note': ''}
    assert json.loads(cli('state', 'get', 'cap').stdout) == 3
    assert len(events(workspace)) == 7
    assert all(e['ts'] == NOW and e['kind'] == 'state.set' for e in events(workspace))


@pytest.mark.parametrize('path,value', [
    ('cap', True), ('cap', -1), ('items.A', 3),
    ('items.A.status', 'unknown'), ('items.A.phase', 'unknown'),
    ('items.A.flags.trust_surface', 'yes'),
])
def test_invalid_schema_is_finding_without_write(workspace, path, value):
    result = cli('state', 'set', path, json.dumps(value))
    assert result.returncode == 1, result.stderr
    assert path.split('.')[0] in result.stderr
    assert not (day(workspace) / 'state.json').exists()
    assert not (day(workspace) / 'events.jsonl').exists()


@pytest.mark.parametrize('args', [
    ('get', 'missing'), ('set', 'a..b', '1'), ('set', 'cap.x', '1'),
    ('set', 'cap', '{'), ('set', 'extra', 'NaN'), ('set', 'extra', '1e999'),
])
def test_bad_paths_and_json_fail_closed(workspace, args):
    result = cli('state', *args)
    assert result.returncode == 2
    assert 'wuwei state:' in result.stderr
    assert not (day(workspace) / 'state.json').exists()


def test_corrupt_state_is_not_reset(workspace):
    day(workspace).mkdir(parents=True)
    path = day(workspace) / 'state.json'
    path.write_text('{broken')
    for args in [('get',), ('set', 'cap', '2')]:
        result = cli('state', *args)
        assert result.returncode == 2
        assert 'wuwei state:' in result.stderr
        assert path.read_text() == '{broken'


def test_atomic_replace_and_cleanup(workspace, monkeypatch):
    from wuwei import state
    state.write_state(lambda data: data.update(cap=2))
    path = day(workspace) / 'state.json'
    original = path.read_bytes()
    replace = state.os.replace

    def inspect(source, target):
        assert Path(source).parent == path.parent
        assert Path(target) == path
        assert json.loads(Path(source).read_text())['cap'] == 3
        assert path.read_bytes() == original
        replace(source, target)

    monkeypatch.setattr(state.os, 'replace', inspect)
    state.write_state(lambda data: data.update(cap=3))
    assert state.read_state()['cap'] == 3

    def fail(*args):
        raise OSError('replacement failed')

    monkeypatch.setattr(state.os, 'replace', fail)
    with pytest.raises(OSError, match='replacement failed'):
        state.write_state(lambda data: data.update(cap=4))
    assert state.read_state()['cap'] == 3
    assert len(events(workspace)) == 2
    assert sorted(p.name for p in path.parent.iterdir()) == ['events.jsonl', 'state.json', 'state.lock']


def test_parallel_writers_preserve_every_update(workspace):
    count = 20
    processes = [subprocess.Popen(
        [sys.executable, '-S', '-m', 'wuwei', 'state', 'set', f'parallel.k{i}', str(i)],
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ) for i in range(count)]
    while any(p.poll() is None for p in processes):
        path = day(workspace) / 'state.json'
        if path.exists():
            assert isinstance(json.loads(path.read_text()), dict)
    for process in processes:
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
    data = json.loads((day(workspace) / 'state.json').read_text())
    assert data['parallel'] == {f'k{i}': i for i in range(count)}
    recorded = events(workspace)
    assert len(recorded) == count
    assert {e['payload']['path'] for e in recorded} == {f'parallel.k{i}' for i in range(count)}


ACTIVE = ['planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta']


def test_transition_cli_rejects_implement_to_done(workspace):
    assert cli('state', 'set', 'items.A', '{"phase":"implement"}').returncode == 0
    before = (day(workspace) / 'state.json').read_bytes()
    result = cli('state', 'transition', 'A', 'done')
    assert result.returncode == 1, result.stderr
    assert 'legal next phases: gate, parked, escalated' in result.stderr
    assert (day(workspace) / 'state.json').read_bytes() == before
    assert len(events(workspace)) == 1
    result = cli('state', 'transition', 'A', 'gate')
    assert result.returncode == 0, result.stderr
    assert events(workspace)[-1]['kind'] == 'state.transition'
    result = cli('state', 'transition', 'absent', 'spec')
    assert result.returncode == 2


@pytest.mark.parametrize('start', ACTIVE + ['merged'])
def test_all_transition_edges(workspace, start):
    from wuwei import state
    edges = {
        'planned': ['spec', 'implement'], 'spec': ['implement'],
        'implement': ['gate'], 'gate': ['raised', 'fix'], 'fix': ['delta'],
        'delta': ['raised', 'fix'], 'raised': ['fix', 'merged'], 'merged': [],
    }
    targets = ACTIVE + ['parked', 'escalated', 'merged', 'done', 'invalid']
    state.set_state('items', {f'item_{target}': {'phase': start} for target in targets})
    allowed = edges[start] + (['parked', 'escalated'] if start in ACTIVE else [])
    for target in ACTIVE + ['parked', 'escalated', 'merged', 'done', 'invalid']:
        # Separate items keep each attempted edge independent.
        name = 'item_' + target
        if target in allowed:
            state.transition(name, target)
            assert state.get_state(f'items.{name}.phase') == target
        else:
            before = (day(workspace) / 'state.json').read_bytes()
            count = len(events(workspace))
            with pytest.raises(state.StateError, match='legal next phases:'):
                state.transition(name, target)
            assert (day(workspace) / 'state.json').read_bytes() == before
            assert len(events(workspace)) == count


@pytest.mark.parametrize('pause', ['parked', 'escalated'])
@pytest.mark.parametrize('start', ACTIVE)
def test_pause_returns_only_to_previous_phase(workspace, start, pause):
    from wuwei import state
    state.set_state('items.A', {'phase': start})
    state.transition('A', pause)
    assert state.get_state('items.A.resume_phase') == start
    for target in ACTIVE + ['parked', 'escalated', 'merged', 'done']:
        if target != start:
            with pytest.raises(state.StateError, match=f'legal next phases: {start}'):
                state.transition('A', target)
    state.transition('A', start)
    assert 'resume_phase' not in state.get_state('items.A')


@pytest.mark.parametrize('replacement', ['path', 'item', 'items', 'writer'])
def test_set_and_writer_cannot_skip_phases(workspace, replacement):
    from wuwei import state
    state.set_state('items.A', {'phase': 'implement'})
    with pytest.raises(state.StateError, match='legal next phases: gate, parked, escalated'):
        if replacement == 'path':
            state.set_state('items.A.phase', 'done')
        elif replacement == 'item':
            state.set_state('items.A', {'phase': 'done'})
        elif replacement == 'items':
            state.set_state('items', {'A': {'phase': 'done'}})
        else:
            state.write_state(lambda data: data.update(items={'A': {'phase': 'done'}}))
    state.set_state('items.A.status', 'done')
    assert state.get_state('items.A.phase') == 'implement'
    state.set_state('items.A.phase', 'parked')
    assert state.get_state('items.A.resume_phase') == 'implement'
    with pytest.raises(state.StateError, match='resume_phase'):
        state.set_state('items.A.resume_phase', 'spec')
    assert state.get_state('items.A.resume_phase') == 'implement'


@pytest.mark.parametrize('item', [{'phase': 'parked'}, {'phase': 'escalated', 'resume_phase': 'done'},
                                  {'phase': 'planned', 'resume_phase': 'spec'}])
def test_invalid_resume_metadata(workspace, item):
    from wuwei import state
    with pytest.raises(state.StateError, match='resume_phase'):
        state.set_state('items.A', item)


def test_explicit_events_use_shared_clock_and_one_line(workspace, monkeypatch):
    result = cli('event', 'started')
    assert result.returncode == 0, result.stderr
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T13:00:00+02:00')
    result = cli('event', 'note', json.dumps({'ts': 'spoofed', 'text': 'a\nb'}))
    assert result.returncode == 0, result.stderr
    assert events(workspace) == [
        {'kind': 'started', 'payload': {}, 'ts': NOW},
        {'kind': 'note', 'payload': {'ts': 'spoofed', 'text': 'a\nb'},
         'ts': '2026-09-28T13:00:00+02:00'},
    ]
    assert not (day(workspace) / 'state.json').exists()


@pytest.mark.parametrize('kind,payload', [('', '{}'), ('x', '[]'), ('x', '{'), ('x', '{"x":NaN}')])
def test_invalid_event_input(workspace, kind, payload):
    result = cli('event', kind, payload)
    assert result.returncode == 2
    assert 'wuwei event:' in result.stderr
    assert not (day(workspace) / 'events.jsonl').exists()


def test_append_detects_short_write(workspace, monkeypatch):
    from wuwei import state
    monkeypatch.setattr(state.os, 'write', lambda fd, encoded: len(encoded) - 1)
    with pytest.raises(OSError, match='short event write'):
        state.append_event('probe')


def test_invalid_imported_event_prevents_state_change(workspace):
    from wuwei import state
    with pytest.raises(ValueError, match='payload'):
        state.write_state(lambda data: data.update(cap=2), payload=[])
    assert not (day(workspace) / 'state.json').exists()


def test_operation_keeps_one_day_across_midnight(workspace, monkeypatch):
    from datetime import datetime
    from wuwei import state
    state.set_state('preserved', True)
    timestamps = iter([datetime.fromisoformat(NOW),
                       datetime.fromisoformat('2026-09-29T00:00:00+02:00')])
    monkeypatch.setattr(state.workspace, 'now', lambda: next(timestamps, datetime.fromisoformat('2026-09-29T00:00:00+02:00')))
    state.set_state('added', True)
    data = json.loads((day(workspace) / 'state.json').read_text())
    assert data['preserved'] is True
    assert data['added'] is True
    assert len(events(workspace)) == 2
    assert events(workspace)[-1]['ts'] == '2026-09-29T00:00:00+02:00'
    assert not (workspace / '.wuwei/days/2026-09-29').exists()


def test_event_io_failure_is_exit_two(workspace):
    day(workspace).mkdir(parents=True)
    (day(workspace) / 'events.jsonl').mkdir()
    result = cli('state', 'set', 'cap', '2')
    assert result.returncode == 2
    assert 'events.jsonl' in result.stderr
    assert json.loads((day(workspace) / 'state.json').read_text())['cap'] == 2


def test_delete_recreate_cannot_bypass_lifecycle(workspace):
    assert cli('state', 'set', 'items.A', '{}').returncode == 0
    before = (day(workspace) / 'state.json').read_bytes()
    removal = cli('state', 'set', 'items', '{}')
    recreation = cli('state', 'set', 'items.A', '{"phase":"merged"}')
    assert removal.returncode == 1, removal.stderr
    assert recreation.returncode == 1, recreation.stderr
    assert (day(workspace) / 'state.json').read_bytes() == before
    assert len(events(workspace)) == 1


def test_later_items_must_start_planned(workspace):
    assert cli('state', 'set', 'cap', '2').returncode == 0
    result = cli('state', 'set', 'items.A', '{"phase":"merged"}')
    assert result.returncode == 1, result.stderr
    assert 'planned' in result.stderr
    assert cli('state', 'set', 'items.A', '{}').returncode == 0


def test_explicit_event_cannot_forge_state_audit(workspace):
    result = cli('event', 'state.transition', '{"item":"A","phase":"merged"}')
    assert result.returncode == 1, result.stderr
    assert not (day(workspace) / 'events.jsonl').exists()


@pytest.mark.parametrize('directory_supported', [True, False])
def test_state_syncs_file_before_replace_and_directory_after(workspace, monkeypatch, directory_supported):
    import stat
    from wuwei import state
    operations = []
    replace = state.os.replace

    def sync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            operations.append('directory')
            assert (day(workspace) / 'state.json').exists()
            if not directory_supported:
                raise OSError('directory fsync unsupported')
        else:
            operations.append('file')
            temporary, = day(workspace).glob('tmp*')
            assert json.loads(temporary.read_text())['cap'] == 2

    def rename(source, target):
        assert operations == ['file']
        operations.append('replace')
        replace(source, target)

    monkeypatch.setattr(state.os, 'fsync', sync)
    monkeypatch.setattr(state.os, 'replace', rename)
    state.set_state('cap', 2)
    assert operations == ['file', 'replace', 'directory']


@pytest.mark.parametrize('writer', [False, True])
def test_event_timestamp_and_append_hold_state_lock(workspace, monkeypatch, writer):
    from wuwei import state
    directory = day(workspace)
    directory.mkdir(parents=True)
    now, write = state.workspace.now, state.os.write
    checked = []

    def assert_locked():
        with (directory / 'state.lock').open('a') as probe:
            with pytest.raises(BlockingIOError):
                state.fcntl.flock(probe, state.fcntl.LOCK_EX | state.fcntl.LOCK_NB)

    def clock():
        assert_locked()
        checked.append('timestamp')
        return now()

    def append(fd, data):
        assert_locked()
        checked.append('append')
        return write(fd, data)

    monkeypatch.setattr(state.workspace, 'day_dir', lambda root=None: directory)
    monkeypatch.setattr(state.workspace, 'now', clock)
    monkeypatch.setattr(state.os, 'write', append)
    if writer:
        state.set_state('cap', 2)
    else:
        state.append_event('probe')
    assert checked == ['timestamp', 'append']


def test_retry_transition_reports_state_may_already_be_at_target(workspace):
    assert cli('state', 'set', 'items.A', '{}').returncode == 0
    assert cli('state', 'transition', 'A', 'implement').returncode == 0
    result = cli('state', 'transition', 'A', 'implement')
    assert result.returncode == 1
    assert 'state may already be at implement' in result.stderr
    assert len(events(workspace)) == 2


def test_state_and_events_are_readonly_after_every_write(workspace, monkeypatch):
    from wuwei import state
    replace = state.os.replace

    def readonly_replace(source, target):
        assert Path(source).stat().st_mode & 0o777 == 0o444
        replace(source, target)

    monkeypatch.setattr(state.os, 'replace', readonly_replace)
    state.append_event('started')
    event_path = day(workspace) / 'events.jsonl'
    assert event_path.stat().st_mode & 0o777 == 0o444
    inode = event_path.stat().st_ino
    for cap in (2, 3):
        before = event_path.read_bytes()
        state.set_state('cap', cap)
        assert (day(workspace) / 'state.json').stat().st_mode & 0o777 == 0o444
        assert event_path.stat().st_mode & 0o777 == 0o444
        assert event_path.stat().st_ino == inode
        assert event_path.read_bytes().startswith(before)
    state.append_event('finished')
    assert event_path.stat().st_mode & 0o777 == 0o444
    assert len(events(workspace)) == 4


@pytest.mark.skipif(os.geteuid() == 0, reason='root bypasses file mode permissions')
@pytest.mark.parametrize('name', ['state.json', 'events.jsonl'])
def test_plain_open_cannot_overwrite_state_as_nonroot(workspace, name):
    from wuwei import state
    state.set_state('cap', 2)
    path = day(workspace) / name
    before = path.read_bytes()
    with pytest.raises(PermissionError):
        with open(path, 'w'):
            pass
    assert path.read_bytes() == before


@pytest.mark.parametrize('failure', ['open', 'write'])
def test_event_failure_restores_readonly_mode(workspace, monkeypatch, failure):
    from wuwei import state
    state.append_event('started')
    path = day(workspace) / 'events.jsonl'
    path.chmod(0o444)
    original_open = os.open

    def fail_open(target, flags, mode=0o777):
        if Path(target) == path:
            raise OSError('event open failed')
        return original_open(target, flags, mode)

    def fail_write(fd, data):
        assert os.fstat(fd).st_mode & 0o777 == 0o444
        raise OSError('event write failed')

    monkeypatch.setattr(state.os, failure, fail_open if failure == 'open' else fail_write)
    with pytest.raises(OSError, match='event .* failed'):
        state.append_event('failed')
    assert path.stat().st_mode & 0o777 == 0o444
