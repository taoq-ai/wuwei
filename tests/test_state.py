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
            state._write_state(lambda data: data.update(cap=2), root)
    assert list(tmp_path.iterdir()) == []


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
        state._write_state(update)
    assert not (day(workspace) / 'state.json').exists()
    assert not (day(workspace) / 'events.jsonl').exists()


def test_corrupt_state_is_not_reset(workspace):
    day(workspace).mkdir(parents=True)
    path = day(workspace) / 'state.json'
    path.write_text('{broken')
    from wuwei import state
    for read in (state.read_state, lambda: state._write_state(lambda data: data.update(cap=2))):
        with pytest.raises(ValueError):
            read()
        assert path.read_text() == '{broken'


def test_atomic_replace_and_cleanup(workspace, monkeypatch):
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
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
    state._write_state(lambda data: data.update(cap=3))
    assert state.read_state()['cap'] == 3

    def fail(*args):
        raise OSError('replacement failed')

    monkeypatch.setattr(state.os, 'replace', fail)
    with pytest.raises(OSError, match='replacement failed'):
        state._write_state(lambda data: data.update(cap=4))
    assert state.read_state()['cap'] == 4  # #844: the event is the record; the cache follows the log
    assert len(events(workspace)) == 3
    assert sorted(p.name for p in path.parent.iterdir()) == ['events.jsonl', 'state.json', 'state.lock']


def test_parallel_writers_preserve_every_update(workspace):
    count = 20
    processes = [subprocess.Popen(
        [sys.executable, '-P', '-S', '-c', 'from wuwei import state; state._write_state(lambda data: '
         f'data["seat_policy"].update(k{i}={i}), payload={{"path": "seat_policy.k{i}"}})'],
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


@pytest.mark.parametrize('item', [{'phase': 'parked'}, {'phase': 'escalated', 'resume_phase': 'done'},
                                  {'phase': 'planned', 'resume_phase': 'spec'}])
def test_invalid_resume_metadata(workspace, item):
    from wuwei import state
    with pytest.raises(state.StateError, match='resume_phase'):
        state._write_state(lambda data: data['items'].update(A=item))


def test_append_detects_short_write(workspace, monkeypatch):
    from wuwei import state
    monkeypatch.setattr(state.os, 'write', lambda fd, encoded: len(encoded) - 1)
    with pytest.raises(OSError, match='short event write'):
        state.append_event('probe')


def test_invalid_imported_event_prevents_state_change(workspace):
    from wuwei import state
    with pytest.raises(ValueError, match='payload'):
        state._write_state(lambda data: data.update(cap=2), payload=[])
    assert not (day(workspace) / 'state.json').exists()


def test_operation_keeps_one_day_across_midnight(workspace, monkeypatch):
    from datetime import datetime
    from wuwei import state
    state._write_state(lambda data: data['seat_policy'].update(preserved=True))
    timestamps = iter([datetime.fromisoformat(NOW),
                       datetime.fromisoformat('2026-09-29T00:00:00+02:00')])
    monkeypatch.setattr(state.workspace, 'now', lambda: next(timestamps, datetime.fromisoformat('2026-09-29T00:00:00+02:00')))
    state._write_state(lambda data: data['seat_policy'].update(added=True))
    data = json.loads((day(workspace) / 'state.json').read_text())
    assert data['seat_policy']['preserved'] is True
    assert data['seat_policy']['added'] is True
    assert len(events(workspace)) == 2
    assert events(workspace)[-1]['ts'] == '2026-09-29T00:00:00+02:00'
    assert not (workspace / '.wuwei/days/2026-09-29').exists()


def test_event_io_failure_is_exit_two(workspace):
    day(workspace).mkdir(parents=True)
    (day(workspace) / 'events.jsonl').mkdir()
    from wuwei import state
    with pytest.raises(OSError, match='events.jsonl'):
        state._write_state(lambda data: data.update(cap=2))
    assert not (day(workspace) / 'state.json').exists()  # #844: no record without its event


def test_later_items_must_start_planned(workspace):
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
    with pytest.raises(state.StateError, match='planned'):
        state._write_state(lambda data: data['items'].update(A={'phase': 'merged'}))
    state._write_state(lambda data: data['items'].update(A={}))


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
    state._write_state(lambda data: data.update(cap=2))
    # The state file synced before the rename, then the directory (#516).
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
        state._write_state(lambda data: data.update(cap=2))
    else:
        state.append_event('probe')
    assert checked == ['timestamp', 'append']


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
        state._write_state(lambda data: data.update(cap=cap))
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
    state._write_state(lambda data: data.update(cap=2))
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


@pytest.mark.parametrize('field', ['raised_prs', 'claimed_prs'])
@pytest.mark.parametrize('writer', ['replace', 'remove'])
def test_pr_lists_cannot_remove_entries(workspace, field, writer):
    from wuwei import state
    refs = ['acme/widget#7', 'acme/widget#8']
    state._write_state(lambda data: data.update({field: refs}), workspace)
    before = (day(workspace) / 'state.json').read_bytes()
    before_events = events(workspace)
    with pytest.raises(state.StateError, match='removing'):
        if writer == 'replace':
            state._write_state(lambda data: data.update({field: refs[1:]}), workspace)
        else:
            state._write_state(lambda data: data.pop(field), workspace)
    assert (day(workspace) / 'state.json').read_bytes() == before
    assert events(workspace) == before_events
    state._write_state(lambda data: data.update({field: refs + ['acme/widget#9']}), workspace)


def test_a_torn_cache_reads_the_log_and_an_old_torn_day_names_doctor(workspace):
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
    state._write_state(lambda data: data.update(cap=3))
    path = day(workspace) / 'state.json'
    path.chmod(0o644)
    path.write_text(path.read_text()[:10])
    assert state.read_state()['cap'] == 3  # #844 F4: the log holds the records
    corrupt(workspace)  # an old day without patches: nothing to fold
    with pytest.raises(ValueError, match='bin/wuwei doctor'):
        state.read_state()


def corrupt(root):
    """An old day (its log carries no patch, written before #844) whose state.json is torn."""
    from wuwei import state
    state._write_state(lambda data: data.update(cap=3))
    log = day(root) / 'events.jsonl'
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    log.chmod(0o644)
    log.write_text(''.join(json.dumps({key: value for key, value in row.items() if key != 'patch'}) + '\n'
                           for row in rows))
    path = day(root) / 'state.json'
    path.chmod(0o644)
    path.write_text('{"cap": 3, "ite')
    return path


def test_a_missing_state_json_is_rebuilt_from_the_log(workspace):
    from wuwei import state
    state._write_state(lambda data: data.update(cap=3))
    path = day(workspace) / 'state.json'
    path.chmod(0o644)
    path.unlink()
    assert state.read_state()['cap'] == 3  # #844: state.json is a cache of the log


def _approved(root, phase):
    from wuwei import state
    state._write_state(lambda data: data.update(
        items={'A': {'phase': phase}}, approved_items=['A'], builds={'A': {'fix_rounds': 2}}),
        root)


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
    state._write_state(lambda data: data['items'].update(B={}), workspace)
    with pytest.raises(state.StateError, match='approved plan'):
        state.record_worktree(workspace, 'B', path, 'a' * 40)


def test_stop_seat_records_when_it_stopped(workspace, monkeypatch):
    from wuwei import state
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:05:00+00:00')
    state._write_state(lambda data: data['seats'].update(s1={
        'item': 'A', 'role': 'sentinel-quality', 'status': 'running'}), workspace)
    state.stop_seat('s1', workspace)
    seat = state.read_state(workspace)['seats']['s1']
    assert seat['status'] == 'stopped' and seat['stopped_at'] == '2026-09-28T12:05:00+00:00'


# #844: the event log is the truth; state.json is its cache.

def test_a_write_carries_its_patch_and_the_fold_equals_the_cache(workspace):
    from wuwei import state
    state._write_state(lambda data: data['items'].update(A={}, B={}))
    state._write_state(lambda data: data['items']['A'].update(note='x'))
    state.append_event('next.action', {'state': 'x'})
    assert events(workspace)[1]['patch'] == {'merge': {'items': {'A': {
        **state.read_state()['items']['A']}}}}
    cached = state.read_state()
    path = day(workspace) / 'state.json'
    path.chmod(0o644)
    path.unlink()
    assert state.read_state() == cached
    assert state.day_started(day(workspace))


def test_a_stale_cache_folds_the_log_tail(workspace):
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
    path = day(workspace) / 'state.json'
    stale = path.read_text()
    state._write_state(lambda data: data.update(cap=3))
    path.chmod(0o644)
    path.write_text(stale)  # a cache whose log size is behind the log
    assert state.read_state()['cap'] == 3


def test_an_old_day_without_patches_moves_into_the_log_on_its_next_write(workspace):
    from wuwei import state
    day(workspace).mkdir(parents=True)
    (day(workspace) / 'state.json').write_text(json.dumps({'cap': 2, 'items': {'A': {}}}))
    assert state.read_state()['cap'] == 2
    state._write_state(lambda data: data.update(gate_approved=True))
    path = day(workspace) / 'state.json'
    path.chmod(0o644)
    path.unlink()
    data = state.read_state()
    assert (data['cap'], data['gate_approved'], list(data['items'])) == (2, True, ['A'])


def test_a_torn_last_line_never_reached_the_cache_and_is_skipped(workspace):
    # F4: a write that died mid-line recorded nothing; reads and writes go on.
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
    log = day(workspace) / 'events.jsonl'
    log.chmod(0o644)
    with log.open('ab') as stream:
        stream.write(b'{"kind": "state.write", "patch": {"set": {"cap": ')
    assert state.read_state()['cap'] == 2
    assert state._write_state(lambda data: data.update(cap=3))['cap'] == 3
    (day(workspace) / 'state.json').chmod(0o644)
    (day(workspace) / 'state.json').unlink()
    assert state.read_state()['cap'] == 3


def test_a_hand_edited_cache_loses_to_the_log(workspace):
    # F6, F7: an edit to state.json, with or without its log size, never changes the records.
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
    path = day(workspace) / 'state.json'
    for drop in (False, True):
        data = json.loads(path.read_text())
        data.update(cap=9, gate_approved=True)
        if drop:
            data.pop('log_size')
        path.chmod(0o644)
        path.write_text(json.dumps(data))
        assert (state.read_state()['cap'], state.read_state()['gate_approved']) == (2, False)


def test_a_replaced_log_never_takes_the_old_cache(workspace):
    # F8: a new log that grew past the old size is folded alone, never under the old cache.
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
    state._write_state(lambda data: data.update(seat_policy={'x': 1}))
    log = day(workspace) / 'events.jsonl'
    size = log.stat().st_size
    log.chmod(0o644)
    log.unlink()
    while not log.is_file() or log.stat().st_size <= size:
        state.append_event('next.action', {'state': 'x', 'pad': 'y' * 50})
    assert state.read_state()['cap'] == 1


def _case_part_23_writes_no_snapshot_and_takes_no_reserved(workspace):
    """#847: state.json is the cache; no snapshot is written and no writer is reserved."""
    import inspect
    from wuwei import state
    state._write_state(lambda data: data.update(cap=2))
    assert (day(workspace) / 'state.json').is_file()
    assert not (day(workspace) / 'state.snapshot.json').exists()
    assert 'reserved' not in inspect.signature(state._write_state).parameters
    for name in ('SNAPSHOT', 'recover', 'write_state', 'set_state', 'get_state', 'STATE_PRODUCERS',
                 'OWNER_FIELDS', '_check_transition', '_producer_error'):
        assert not hasattr(state, name), name


def _case_part_23_damaged_day_names_doctor(workspace):
    from wuwei import state
    day(workspace).mkdir(parents=True)
    (day(workspace) / 'state.json').write_text('{broken')
    with pytest.raises(ValueError) as caught:
        state.read_state(workspace)
    assert 'bin/wuwei doctor' in str(caught.value) and 'state recover' not in str(caught.value)


@pytest.mark.parametrize("scenario_fn", [
    _case_part_23_writes_no_snapshot_and_takes_no_reserved,
    _case_part_23_damaged_day_names_doctor,
])
def test_part_23_cases_521(workspace, scenario_fn):
    scenario_fn(workspace)


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', '1e999', '-1e999'])
def test_records_reject_values_json_cannot_write(tmp_path, value):
    # moved from test_watch.py (#847)
    from wuwei import watch
    path = tmp_path / 'events.jsonl'
    good = '{"kind": "note", "payload": {"n": 1.5, "m": 10}, "ts": "2026-09-28T12:00:00+00:00"}\n'
    path.write_text(good)
    assert watch.records(path) == [json.loads(good)]
    path.write_text(good + good.replace('1.5', value))
    with pytest.raises(ValueError):
        watch.records(path)
