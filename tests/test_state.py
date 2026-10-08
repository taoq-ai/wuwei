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
        [sys.executable, '-P', '-S', '-m', 'wuwei', *args],
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')},
        capture_output=True, text=True,
    )


def events(root):
    return [json.loads(line) for line in (day(root) / 'events.jsonl').read_text().splitlines()]


@pytest.mark.parametrize('operation', ['event', 'event_directory', 'state', 'jsonl'])
@pytest.mark.parametrize('missing_root', [False, True])
def test_writes_require_existing_workspace(tmp_path, operation, missing_root):
    from wuwei import state
    root = tmp_path / 'missing' if missing_root else tmp_path
    with pytest.raises(FileNotFoundError):
        if operation == 'event':
            state.append_event('probe', root=root)
        elif operation == 'event_directory':
            state.append_event('probe', directory=day(root))
        elif operation == 'jsonl':
            state.append_jsonl(day(root) / 'traces.jsonl', {'probe': True})
        else:
            state.set_state('cap', 2, root=root)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('args', [('event', 'note'), ('state', 'set', 'cap', '2')])
def test_cli_writes_without_workspace_exit_two(tmp_path, monkeypatch, args):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    assert cli(*args).returncode == 2
    assert list(tmp_path.iterdir()) == []


def test_get_set_defaults_and_audit(workspace):
    result = cli('state', 'get')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        'items': {}, 'cap': 1, 'cap_bound': '', 'seat_policy': {}, 'envelope': {},
        'claimed_prs': [], 'raised_prs': [], 'gate_verdicts': {}, 'seats': {},
        'gate_approved': False, 'approved_items': [], 'goals': [],
    }
    assert not day(workspace).exists()
    from wuwei import state
    state._write_state(lambda data: data['items'].update(A={}), reserved=False)
    for path, value in [('items.A.note', 'progress'), ('cap', 3),
                        ('seat_policy.builder', {'model': 'x'})]:
        result = cli('state', 'set', path, json.dumps(value))
        assert result.returncode == 0, result.stderr
    item = json.loads(cli('state', 'get', 'items.A').stdout)
    assert item == {'lane': 'build', 'status': 'queued', 'phase': 'planned',
                    'flags': dict.fromkeys(['trust_surface', 'boundary_relevant', 'agent_surface'], False),
                    'gates': {}, 'note': 'progress'}
    assert json.loads(cli('state', 'get', 'cap').stdout) == 3
    assert len(events(workspace)) == 4
    assert all(e['ts'] == NOW and e['kind'] == 'state.set' for e in events(workspace)[1:])


@pytest.mark.parametrize('path,value', [
    ('cap', True), ('cap', -1), ('items.A', 3),
    ('items.A.status', 'unknown'), ('items.A.phase', 'unknown'),
    ('items.A.flags.trust_surface', 'yes'),
])
def test_invalid_schema_is_finding_without_write(workspace, path, value):
    from wuwei import state
    def update(data):
        parent = data
        parts = path.split('.')
        for key in parts[:-1]:
            parent = parent.setdefault(key, {})
        parent[parts[-1]] = value
    with pytest.raises(state.StateError, match=path.split('.')[0]):
        state._write_state(update, reserved=False)
    assert not (day(workspace) / 'state.json').exists()
    assert not (day(workspace) / 'events.jsonl').exists()


@pytest.mark.parametrize('args', [
    ('get', 'missing'), ('set', 'a..b', '1'),
    ('set', 'cap', '{'), ('set', 'seat_policy.x', 'NaN'), ('set', 'seat_policy.x', '1e999'),
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
        if Path(target).name == 'state.snapshot.json':
            return replace(source, target)
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
    assert sorted(p.name for p in path.parent.iterdir()) == ['events.jsonl', 'state.json', 'state.lock',
                                                             'state.snapshot.json']


def test_parallel_writers_preserve_every_update(workspace):
    count = 20
    processes = [subprocess.Popen(
        [sys.executable, '-P', '-S', '-m', 'wuwei', 'state', 'set', f'seat_policy.k{i}', str(i)],
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
    assert data['seat_policy'] == {f'k{i}': i for i in range(count)}
    recorded = events(workspace)
    assert len(recorded) == count
    assert {e['payload']['path'] for e in recorded} == {f'seat_policy.k{i}' for i in range(count)}


ACTIVE = ['planned', 'spec', 'implement', 'gate', 'raised', 'fix', 'delta']


def test_transition_cli_rejects_implement_to_done(workspace):
    from wuwei import state
    state._write_state(lambda data: data['items'].update(A={'phase': 'implement'}), reserved=False)
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
        'planned': ['spec', 'implement', 'raised'], 'spec': ['implement'],
        'implement': ['gate'], 'gate': ['raised', 'fix'], 'fix': ['delta', 'merged'],
        'delta': ['raised', 'fix', 'merged'], 'raised': ['fix', 'merged'], 'merged': [],
    }
    targets = ACTIVE + ['parked', 'escalated', 'merged', 'done', 'invalid']
    state._write_state(lambda data: data.update(items={f'item_{target}': {'phase': start} for target in targets}), reserved=False)
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
    state._write_state(lambda data: data['items'].update(A={'phase': start}), reserved=False)
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
    state._write_state(lambda data: data['items'].update(A={'phase': 'implement'}), reserved=False)
    with pytest.raises(state.StateError, match='reserved'):
        if replacement == 'path':
            state.set_state('items.A.phase', 'done')
        elif replacement == 'item':
            state.set_state('items.A', {'phase': 'done'})
        elif replacement == 'items':
            state.set_state('items', {'A': {'phase': 'done'}})
        else:
            state.write_state(lambda data: data.update(items={'A': {'phase': 'done'}}))
    state._write_state(lambda data: data['items']['A'].update(status='done'), reserved=False)
    assert state.get_state('items.A.phase') == 'implement'
    state.transition('A', 'parked')
    assert state.get_state('items.A.resume_phase') == 'implement'
    with pytest.raises(state.StateError, match='resume_phase'):
        state.set_state('items.A.resume_phase', 'spec')
    assert state.get_state('items.A.resume_phase') == 'implement'


@pytest.mark.parametrize('item', [{'phase': 'parked'}, {'phase': 'escalated', 'resume_phase': 'done'},
                                  {'phase': 'planned', 'resume_phase': 'spec'}])
def test_invalid_resume_metadata(workspace, item):
    from wuwei import state
    with pytest.raises(state.StateError, match='resume_phase'):
        state._write_state(lambda data: data['items'].update(A=item), reserved=False)


def test_explicit_events_use_shared_clock_and_one_line(workspace, monkeypatch):
    result = cli('event', 'note')
    assert result.returncode == 0, result.stderr
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T13:00:00+02:00')
    result = cli('event', 'note', json.dumps({'ts': 'spoofed', 'text': 'a\nb'}))
    assert result.returncode == 0, result.stderr
    assert events(workspace) == [
        {'kind': 'note', 'payload': {}, 'ts': NOW},
        {'kind': 'note', 'payload': {'ts': 'spoofed', 'text': 'a\nb'},
         'ts': '2026-09-28T13:00:00+02:00'},
    ]
    assert not (day(workspace) / 'state.json').exists()


@pytest.mark.parametrize('kind,payload', [('', '{}'), ('note', '[]'), ('note', '{'), ('note', '{"x":NaN}')])
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
    state.set_state('seat_policy.preserved', True)
    timestamps = iter([datetime.fromisoformat(NOW),
                       datetime.fromisoformat('2026-09-29T00:00:00+02:00')])
    monkeypatch.setattr(state.workspace, 'now', lambda: next(timestamps, datetime.fromisoformat('2026-09-29T00:00:00+02:00')))
    state.set_state('seat_policy.added', True)
    data = json.loads((day(workspace) / 'state.json').read_text())
    assert data['seat_policy']['preserved'] is True
    assert data['seat_policy']['added'] is True
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
    from wuwei import state
    state._write_state(lambda data: data['items'].update(A={}), reserved=False)
    before = (day(workspace) / 'state.json').read_bytes()
    removal = cli('state', 'set', 'items', '{}')
    recreation = cli('state', 'set', 'items.A', '{"phase":"merged"}')
    assert removal.returncode == 1, removal.stderr
    assert recreation.returncode == 1, recreation.stderr
    assert (day(workspace) / 'state.json').read_bytes() == before
    assert len(events(workspace)) == 1


def test_later_items_must_start_planned(workspace):
    assert cli('state', 'set', 'cap', '2').returncode == 0
    from wuwei import state
    with pytest.raises(state.StateError, match='planned'):
        state._write_state(lambda data: data['items'].update(A={'phase': 'merged'}), reserved=False)
    state._write_state(lambda data: data['items'].update(A={}), reserved=False)


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
        assert operations[-1:] == ['file']
        operations.append('replace')
        replace(source, target)

    monkeypatch.setattr(state.os, 'fsync', sync)
    monkeypatch.setattr(state.os, 'replace', rename)
    state.set_state('cap', 2)
    # The state file, then its snapshot, each synced before the rename; one directory sync
    # after both renames makes both durable (#516).
    assert operations == ['file', 'replace', 'file', 'replace', 'directory']


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
    from wuwei import state
    state._write_state(lambda data: data['items'].update(A={}), reserved=False)
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
@pytest.mark.parametrize('name', ['events.jsonl', 'traces.jsonl'])
def test_event_failure_restores_readonly_mode(workspace, monkeypatch, failure, name):
    from wuwei import state
    state.append_event('started')
    path = day(workspace) / name
    state.append_jsonl(path, {'before': True})
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
        if name == 'events.jsonl':
            state.append_event('failed')
        else:
            state.append_jsonl(path, {'failed': True})
    assert path.stat().st_mode & 0o777 == 0o444


@pytest.mark.parametrize('path,value', [
    ('seats', '{}'), ('seats.b.status', '"done"'),
])
def test_seat_reservations_require_dedicated_writer(workspace, path, value):
    from wuwei import state
    result = cli('state', 'set', path, value)
    assert result.returncode == 1
    assert 'reserved' in result.stderr
    assert state.read_state(workspace)['seats'] == {}


@pytest.mark.parametrize('path,value', [
    ('fast_checks', {'demo': {'unit': {'sha': 'a' * 40, 'exit': 0}}}),
    ('fast_checks.demo.unit.exit', 0),
    ('envelope', {'fast_checks': {'demo': {'unit': {'sha': 'a' * 40, 'exit': 0}}}}),
])
def test_cli_cannot_forge_fast_checks(workspace, path, value):
    result = cli('state', 'set', path, json.dumps(value))
    assert result.returncode == 1, result.stderr
    assert 'reserved' in result.stderr
    assert not (day(workspace) / 'state.json').exists()


@pytest.mark.parametrize('path,value', [
    ('example_records.A', 'PASS'), ('example_records', {}),
    ('items.A.example_records', {'arch': 'PASS'}),
    ('items', {'A': {'example_records': {'arch': 'PASS'}}}),
])
def test_generic_state_denies_unknown_fields(workspace, path, value):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state(path, value, workspace)
    with pytest.raises(state.StateError, match='reserved'):
        state.write_state(lambda data: data.update(example_records=value), workspace)
    assert not (day(workspace) / 'state.json').exists()


@pytest.mark.parametrize('field', ['raised_prs', 'claimed_prs'])
@pytest.mark.parametrize('writer', ['replace', 'remove'])
def test_pr_lists_cannot_remove_entries(workspace, field, writer):
    from wuwei import state
    refs = ['acme/widget#7', 'acme/widget#8']
    state._write_state(lambda data: data.update({field: refs}), workspace, reserved=False)
    before = (day(workspace) / 'state.json').read_bytes()
    before_events = events(workspace)
    with pytest.raises(state.StateError, match='removing'):
        if writer == 'replace':
            state._write_state(lambda data: data.update({field: refs[1:]}), workspace, reserved=False)
        else:
            state._write_state(lambda data: data.pop(field), workspace, reserved=False)
    assert (day(workspace) / 'state.json').read_bytes() == before
    assert events(workspace) == before_events
    state._write_state(lambda data: data.update({field: refs + ['acme/widget#9']}), workspace, reserved=False)


@pytest.mark.parametrize('kind', [
    'watch: sweep', 'reply: acknowledged', 'seat.usage', 'build.iteration',
    'build.parked', 'retro.captured', 'retro.gap', 'verdict.rejected',
    'fast_checks.record', 'worktree.hooks_skipped',
])
def test_dedicated_event_kinds_reserved(workspace, kind):
    result = cli('event', kind, '{"exit":0,"owed":0}')
    assert result.returncode == 1
    assert 'reserved' in result.stderr
    assert not (day(workspace) / 'events.jsonl').exists()


def test_corrupt_state_names_recovery_and_writes_keep_a_snapshot(workspace):
    from wuwei import state
    state.write_state(lambda data: data.update(cap=2))
    state.write_state(lambda data: data.update(cap=3))
    path, snapshot = day(workspace) / 'state.json', day(workspace) / 'state.snapshot.json'
    assert snapshot.read_text() == path.read_text()
    assert json.loads(snapshot.read_text())['cap'] == 3
    assert snapshot.stat().st_mode & 0o777 == 0o444
    path.chmod(0o644)
    path.write_text(path.read_text()[:10])
    with pytest.raises(ValueError, match='wuwei state recover'):
        state.read_state()


def corrupt(root, *, missing=False):
    from wuwei import state
    state.write_state(lambda data: data.update(cap=3))
    path = day(root) / 'state.json'
    path.chmod(0o644)
    if missing:
        path.unlink()
    else:
        path.write_text('{"cap": 3, "ite')
    return path


@pytest.mark.parametrize('missing', [False, True])
def test_recover_restores_last_written_state(workspace, missing):
    from wuwei import state
    corrupt(workspace, missing=missing)
    tokens = []
    digest = state.recover(confirm=lambda token: tokens.append(token) or True)
    assert tokens == [digest[:12]]
    assert state.read_state()['cap'] == 3
    assert (day(workspace) / 'state.json').stat().st_mode & 0o777 == 0o444
    assert events(workspace)[-1]['kind'] == 'state.recovered'
    assert events(workspace)[-1]['payload']['snapshot'] == digest


@pytest.mark.parametrize('case,error', [
    ('readable', 'nothing to recover'), ('declined', 'declined'),
    ('no_terminal', 'no tty'), ('no_snapshot', 'No such file'), ('bad_snapshot', 'unusable'),
    ('changed', 'changed during confirmation'),
])
def test_recover_refusals_change_nothing(workspace, case, error):
    from wuwei import state
    path = day(workspace) / 'state.json'
    if case == 'readable':
        state.write_state(lambda data: data.update(cap=3))
    else:
        corrupt(workspace)
    snapshot = day(workspace) / 'state.snapshot.json'
    if case in ('no_snapshot', 'bad_snapshot'):
        snapshot.chmod(0o644)
        snapshot.unlink() if case == 'no_snapshot' else snapshot.write_text('[]')

    def confirm(token):
        if case == 'no_terminal':
            raise OSError('no tty')
        if case == 'changed':
            snapshot.chmod(0o644)
            snapshot.write_text(snapshot.read_text().replace('"cap": 3', '"cap": 4'))
        return case != 'declined'

    before = path.read_text()
    expected = state.StateError if case in ('readable', 'declined') else (OSError, ValueError)
    with pytest.raises(expected, match=error) as raised:
        state.recover(confirm=confirm)
    if case not in ('readable', 'declined'):
        assert not isinstance(raised.value, state.StateError)
    assert path.read_text() == before
    assert 'state.recovered' not in [row['kind'] for row in events(workspace)]


@pytest.mark.parametrize('case,expected', [('confirmed', 0), ('declined', 1), ('readable', 1),
                                           ('no_snapshot', 2), ('no_terminal', 2)])
def test_recover_command_exits(workspace, monkeypatch, capsys, case, expected):
    from wuwei import integrity, state
    from wuwei.__main__ import main
    if case == 'readable':
        state.write_state(lambda data: data.update(cap=3))
    else:
        corrupt(workspace)
    if case == 'no_snapshot':
        (day(workspace) / 'state.snapshot.json').chmod(0o644)
        (day(workspace) / 'state.snapshot.json').unlink()
    def confirm(token, *, prompt):
        if case == 'no_terminal':
            raise OSError('no terminal')
        return case != 'declined'
    monkeypatch.setattr(integrity, '_host_confirm', confirm)
    assert main(['state', 'recover']) == expected
    if expected == 0:
        assert 'state recovered from snapshot' in capsys.readouterr().out
        assert state.read_state()['cap'] == 3


def test_recover_without_a_terminal_names_the_owner_action(workspace, monkeypatch, capsys):
    import builtins
    from wuwei.__main__ import main
    path = corrupt(workspace)
    real_open = builtins.open
    def fake_open(name, *args, **kwargs):
        if name == '/dev/tty':
            raise OSError(6, 'Device not configured')
        return real_open(name, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', fake_open)
    assert main(['state', 'recover']) == 2
    err = capsys.readouterr().err
    assert 'run it in a host terminal' in err and 'Errno' not in err
    assert path.read_text() == '{"cap": 3, "ite'


def test_hook_names_recovery_then_continues(workspace):
    from wuwei import integrity, state
    from wuwei.guards import stop
    (workspace / '.wuwei/config.toml').write_text('')
    state._write_state(lambda data: data.update(planner_session_id='planner'), workspace, reserved=False)
    corrupt(workspace)
    payload = {'cwd': str(workspace), 'session_id': 'planner', 'stop_hook_active': False}
    code, reason = stop.check(payload)
    assert code == 2 and 'wuwei state recover' in reason
    state.recover(confirm=lambda token: True)
    assert 'recover' not in stop.check(payload)[1]


def test_recovered_event_names_the_recovery(workspace):
    from wuwei import state
    from wuwei.commands.status import attention
    corrupt(workspace)
    digest = state.recover(confirm=lambda token: True)
    payload = events(workspace)[-1]['payload']
    assert payload['reason'] == 'state recovered from snapshot ' + digest[:12]
    assert 'state.json' in payload['error']
    row, = [row for row in attention(day(workspace)) if row['source'] == 'state.recovered']
    assert 'Unterminated' not in row['reason'] and 'recover in a host terminal' not in row['reason']


def _approved(root, phase):
    from wuwei import state
    state._write_state(lambda data: data.update(
        items={'A': {'phase': phase}}, approved_items=['A'], builds={'A': {'fix_rounds': 2}}),
        root, reserved=False)


@pytest.mark.parametrize('phase', ['gate', 'delta'])
def test_raise_moves_the_phase(workspace, phase):
    from wuwei import state
    _approved(workspace, phase)
    state.record_pr(workspace, 'A', 'owner/repo#1', raised=True)
    data = state.read_state(workspace)
    assert data['items']['A']['phase'] == 'raised'
    assert data['builds']['A']['fix_rounds'] == (0 if phase == 'delta' else 2)
    assert events(workspace)[-1]['kind'] == 'pr.raised'
    assert events(workspace)[-1]['payload']['phase_changes'] == {'A': 'raised'}


@pytest.mark.parametrize('phase,raised', [('fix', True), ('delta', False)])
def test_link_without_raise_keeps_the_phase(workspace, phase, raised):
    from wuwei import state
    _approved(workspace, phase)
    state.record_pr(workspace, 'A', 'owner/repo#1', raised=raised)
    data = state.read_state(workspace)
    assert data['items']['A'] == {**data['items']['A'], 'phase': phase, 'pr': 'owner/repo#1'}


def test_claim_moves_a_planned_item_to_raised(workspace):
    from wuwei import state
    _approved(workspace, 'planned')
    count = len(events(workspace))
    state.record_pr(workspace, 'A', 'owner/repo#1', raised=False)
    assert state.read_state(workspace)['items']['A']['phase'] == 'raised'
    assert [e['kind'] for e in events(workspace)[count:]] == ['pr.claimed']
    assert events(workspace)[-1]['payload']['phase_changes'] == {'A': 'raised'}


def test_record_worktree(workspace, tmp_path):
    from wuwei import state
    _approved(workspace, 'raised')
    path = tmp_path / 'wt'
    state.record_worktree(workspace, 'A', path, 'a' * 40)
    assert state.read_state(workspace)['items']['A']['worktree'] == str(path)
    event = events(workspace)[-1]
    assert event['kind'] == 'worktree.adopted'
    assert {k: event['payload'][k] for k in ('item', 'worktree', 'head')} == {
        'item': 'A', 'worktree': str(path), 'head': 'a' * 40}
    state.record_worktree(workspace, 'A', path, 'a' * 40)
    before = (day(workspace) / 'state.json').read_bytes()
    with pytest.raises(state.StateError, match='another worktree'):
        state.record_worktree(workspace, 'A', tmp_path / 'other', 'a' * 40)
    assert (day(workspace) / 'state.json').read_bytes() == before
    state._write_state(lambda data: data['items'].update(B={}), workspace, reserved=False)
    with pytest.raises(state.StateError, match='approved plan'):
        state.record_worktree(workspace, 'B', path, 'a' * 40)
    with pytest.raises(state.StateError, match='wuwei worktree adopt'):
        state.set_state('items.A.worktree', 'x', workspace)


def test_stop_seat_records_when_it_stopped(workspace, monkeypatch):
    from wuwei import state
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:05:00+00:00')
    state._write_state(lambda data: data['seats'].update(s1={
        'item': 'A', 'role': 'sentinel-quality', 'status': 'running'}), workspace, reserved=False)
    state.stop_seat('s1', workspace)
    seat = state.read_state(workspace)['seats']['s1']
    assert seat['status'] == 'stopped' and seat['stopped_at'] == '2026-09-28T12:05:00+00:00'


@pytest.mark.parametrize('kind,producer', [('docs.written', 'wuwei docs or wuwei drafts approve'),
                                           ('docs.exempt', 'wuwei dispatch next'),
                                           ('docs.set', 'wuwei plan set or wuwei docs page')])
def test_docs_events_and_field_are_reserved(workspace, capsys, kind, producer):
    from wuwei import state
    from wuwei.__main__ import main
    assert main(['event', kind, '{}']) == 1
    assert f'written by {producer}' in capsys.readouterr().err
    state._write_state(lambda data: data['items'].update(A={}), reserved=False)
    with pytest.raises(state.StateError, match='written by wuwei plan set or wuwei docs page'):
        state.set_state('items.A.docs', {'value': 'none', 'reason': 'x'}, workspace)
