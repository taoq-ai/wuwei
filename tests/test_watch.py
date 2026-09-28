"""Watch behavior through fake ports, with no real tools or sleeping."""

import importlib
import io
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from fakes.code_host import Fake as Host
from fakes.vcs import Fake as VCS
from wuwei import registry, state, workspace
from wuwei.__main__ import main
from wuwei.registry import Result

REF = 'example/project#7'


@pytest.fixture
def case(tmp_path, monkeypatch):
    (tmp_path / '.wuwei/memory/notes').mkdir(parents=True)
    from wuwei import memory
    if not hasattr(memory, 'lint'):
        # Until rebased onto the memory-lint feature, match its list[str] contract.
        def lint(root):
            if not (root / '.wuwei/memory/notes').is_dir():
                raise ValueError('memory notes directory missing')
            return []
        monkeypatch.setattr(memory, 'lint', lint, raising=False)
    (tmp_path / '.wuwei/memory/spine.md').write_text('Memory spine\n')
    (tmp_path / '.wuwei/memory/index.md').write_text('Index\n')
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nhandles=["owner"]\n'
        '[[repos]]\nname="example/project"\npath="repo"\ndefault_branch="main"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    host, vcs = Host(), VCS()
    host.results['reviews'] = Result(0, [])
    host.results['threads'] = Result(0, {'comments': [], 'threads': []})
    host.results['checks'] = Result(0, [])
    host.results['pr'].data.update(repo='example/project', number=7)
    scanner = SimpleNamespace(traces=lambda file, root=None: Result(0, {}))
    ports = {'code_host': host, 'vcs': vcs, 'scanner': scanner}
    monkeypatch.setattr(registry, 'load', lambda kind, config: ports[kind])
    state.write_state(lambda data: data.update(raised_prs=[REF]), tmp_path)
    return tmp_path, host, vcs, monkeypatch


def watch_module():
    import wuwei
    assert (Path(wuwei.__file__).parent / 'watch.py').exists(), 'watch core is missing'
    return importlib.import_module('wuwei.watch')


def events(root, kind):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row for line in path.read_text().splitlines()
            if (row := json.loads(line))['kind'] == kind]


def advance(case, seconds):
    case[3].setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=seconds)).isoformat())


@pytest.mark.parametrize('seconds,expected', [(1199, 0), (1200, 1), (1201, 1)])
def test_health_clock_boundary(case, seconds, expected):
    root, _, _, _ = case
    watch = watch_module()
    assert watch.health(root)[0] == 1
    state.append_event('watch: clock', {}, root)
    advance(case, seconds)
    code, reason = watch.health(root)
    assert code == expected
    if code:
        assert 'dead' in reason


def test_heartbeat_persists_and_staleness_uses_commit_or_report(case):
    root, _, vcs, _ = case
    watch = watch_module()
    state.set_state('items.work', {'status': 'running', 'worktree': 'repo'}, root)
    assert watch.activity(root)[0] == 0
    assert not events(root, 'watch: heartbeat')
    advance(case, 900)
    assert watch.activity(root)[0] == 1
    state.set_state('items.work.report_at', workspace.now().isoformat(), root)
    assert watch.activity(root)[0] == 0
    advance(case, 900)
    vcs.results['head'].data['sha'] = 'b' * 40
    assert watch.activity(root)[0] == 0
    assert len(events(root, 'watch: heartbeat')) == 1
    assert watch.activity(root)[0] == 0
    assert len(events(root, 'watch: heartbeat')) == 1
    vcs.results['head'] = Result(2, None, 'cannot read HEAD')
    assert watch.activity(root)[0] == 2


@pytest.mark.parametrize('scanner,expected', [('none', 2), ('measured', 1), ('failed', 2)])
def test_sweep_one_summary_with_counts_and_dead_watch(case, scanner, expected, capsys):
    root, _, _, monkeypatch = case
    watch = watch_module()
    if scanner != 'none':
        known = registry.known
        monkeypatch.setattr(registry, 'known', lambda kind: ['none', 'ziran']
                            if kind == 'scanner' else known(kind))
        with (root / '.wuwei/config.toml').open('a') as stream:
            stream.write('\n[adapters]\nscanner="ziran"\n')
        (workspace.day_dir(root) / 'traces.jsonl').write_text('')
    if scanner == 'failed':
        original = registry.load
        monkeypatch.setattr(registry, 'load', lambda kind, config:
            SimpleNamespace(traces=lambda file, root=None: Result(2, None, 'scanner failed'))
            if kind == 'scanner' else original(kind, config))
    assert watch.sweep(root) == expected
    row, = events(root, 'watch: sweep')
    assert row['payload']['visibility_owed'] == 2
    assert row['payload']['watch_dead'] == 1
    assert row['payload']['reply_owed'] == 0
    assert row['payload']['scanner'] == ('unmeasured' if scanner == 'none' else
                                        'unreadable' if scanner == 'failed' else 'measured')
    assert 'watch dead' in capsys.readouterr().out


def test_sweep_failed_discovery_never_clean(case):
    root, host, _, _ = case
    watch = watch_module()
    host.results['pr'] = Result(2, None, 'read failed')
    assert watch.sweep(root) == 2
    row, = events(root, 'watch: sweep')
    assert row['payload']['unreadable'] > 0


@pytest.mark.parametrize('field', ['head', 'mergeable', 'updated_at', 'checks', 'reviews', 'threads'])
def test_pr_poll_persisted_diff_wakes_once(case, field, capsys):
    root, host, _, _ = case
    watch = watch_module()
    assert hasattr(watch, 'poll'), 'persistent PR polling is missing'
    assert watch.poll(root) == 0
    assert not events(root, 'pr.changed')
    if field == 'checks':
        host.results['checks'] = Result(0, [{'name': 'ci', 'state': 'completed',
            'conclusion': 'failure', 'sha': 'a' * 40, 'url': None}])
    elif field == 'reviews':
        host.results['reviews'] = Result(0, [{'id': 1, 'author': 'reviewer', 'is_bot': False,
            'state': 'changes_requested', 'body': 'private text', 'submitted_at': workspace.now().isoformat()}])
    elif field == 'threads':
        host.results['threads'].data['comments'] = [{'id': 1, 'author': 'reviewer',
            'is_bot': False, 'body': 'private text', 'created_at': workspace.now().isoformat()}]
    else:
        host.results['pr'].data[field] = {'head': 'b' * 40, 'mergeable': False,
                                        'updated_at': '2026-09-28T12:01:00Z'}[field]
    assert watch.poll(root) == 1
    row, = events(root, 'pr.changed')
    assert field in row['payload']['fields']
    marker = state.read_state(root)['watch']['wake']
    assert marker['prs'] == [REF]
    assert 'private text' not in json.dumps(state.read_state(root))
    assert 'private text' not in json.dumps(row)
    assert 'planner wake' in capsys.readouterr().out
    assert watch.poll(root) == 0
    assert len(events(root, 'pr.changed')) == 1


def test_poll_read_failure_preserves_baseline_and_resets_streak(case):
    root, host, _, _ = case
    watch = watch_module()
    assert hasattr(watch, 'poll')
    assert watch.poll(root) == 0
    before = state.read_state(root)['watch']['prs']
    host.results['checks'] = Result(2, None, 'timeout')
    for count in range(1, 6):
        assert watch.poll(root) == 2
        current = state.read_state(root)['watch']
        assert current['prs'] == before
        assert current['failures'] == 0
        assert events(root, 'watch: read-failed')[-1]['payload']['pr'] == REF
    host.results['checks'] = Result(0, [])
    assert watch.poll(root) == 0
    assert state.read_state(root)['watch']['failures'] == 0


def test_poll_new_gone_and_midnight(case):
    root, host, _, monkeypatch = case
    watch = watch_module()
    assert hasattr(watch, 'poll')
    assert watch.poll(root) == 0
    state.set_state('claimed_prs', ['example/project#8'], root)
    # Fake PR identity must match each reference.
    original = host.pr
    def read_pr(ref, root=None):
        result = original(ref, root=root)
        result.data['number'] = int(ref.split('#')[1])
        return result
    monkeypatch.setattr(host, 'pr', read_pr)
    assert watch.poll(root) == 1
    advance(case, 86400)
    state.write_state(lambda data: data.update(raised_prs=[REF]), root)
    host.results['pr'].data['head'] = 'b' * 40
    assert watch.poll(root) == 1
    assert len(events(root, 'pr.changed')) == 2
    assert events(root, 'pr.changed')[-1]['payload']['fields'] == ['gone']


@pytest.mark.parametrize('kind', ['pr.changed', 'watch: clock', 'watch: heartbeat',
                                  'watch: read-failed', 'session: compact', 'session: wake-seen'])
def test_producer_events_reserved(case, kind):
    assert main(['event', kind]) == 1


def test_watch_state_reserved(case):
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('watch.wake', {'prs': [REF]}, case[0])


def test_tick_timing_and_restart(case):
    root, host, _, _ = case
    watch = watch_module()
    assert hasattr(watch, 'tick')
    assert watch.tick(root) == 2  # Missing scanner is unmeasured.
    assert len(events(root, 'watch: clock')) == len(events(root, 'watch: sweep')) == 1
    first_calls = len(host.calls)
    assert watch.tick(root) == 0
    assert len(host.calls) == first_calls
    advance(case, 120)
    watch.tick(root)
    assert len(host.calls) > first_calls
    assert len(events(root, 'watch: clock')) == 1
    advance(case, 480)
    watch.tick(root)
    assert len(events(root, 'watch: clock')) == 2
    advance(case, 6600)
    watch.tick(root)
    assert len(events(root, 'watch: sweep')) == 2
    assert events(root, 'watch: sweep')[-1]['payload']['watch_dead'] == 1


def test_loop_first_failure_and_retry_limit(case):
    root, _, _, monkeypatch = case
    watch = watch_module()
    original = watch.owned
    def failed(*args):
        raise ValueError('discovery failed')
    monkeypatch.setattr(watch, 'owned', failed)
    assert watch.run(root, sleep=lambda seconds: pytest.fail('initial failure must exit')) == 2
    monkeypatch.setattr(watch, 'owned', original)
    assert watch.poll(root) == 0
    monkeypatch.setattr(watch, 'owned', failed)
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        assert len(sleeps) < 20
        advance(case, seconds)
    assert watch.run(root, sleep=sleep) == 2
    assert state.read_state(root)['watch']['failures'] == 5


def test_watch_cli_once(case):
    assert main(['watch', '--once']) == 2
    assert len(events(case[0], 'watch: clock')) == 1


def lifecycle_module():
    import wuwei
    assert (Path(wuwei.__file__).parent / 'guards/lifecycle.py').exists(), 'lifecycle guards missing'
    return importlib.import_module('wuwei.guards.lifecycle')


@pytest.mark.parametrize('condition,expected', [('clean', 0), ('dead', 1), ('corrupt', 2)])
def test_session_start_table(case, condition, expected):
    root, _, _, _ = case
    lifecycle = lifecycle_module()
    if condition != 'dead':
        state.append_event('watch: clock', {}, root)
    if condition == 'corrupt':
        path = workspace.day_dir(root) / 'state.json'
        path.chmod(0o600)
        path.write_text('{')
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert code == expected
    if condition != 'corrupt':
        assert 'Memory spine' in message and 'Size:' in message
    if condition == 'dead':
        assert 'watch dead' in message


def test_session_orphans_and_wake(case):
    root, host, _, _ = case
    lifecycle = lifecycle_module()
    prior = workspace.day_dir(root).parent / '2026-09-27'
    state._write_state(lambda data: data.update(seats={
        'old-builder': {'status': 'running'}, 'finished': {'status': 'stopped'}}),
        directory=prior, reserved=False)
    state.append_event('watch: clock', {}, root)
    watch = watch_module()
    watch.poll(root)
    host.results['pr'].data['head'] = 'b' * 40
    watch.poll(root)
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert code == 1
    assert 'orphan' in message and 'old-builder' in message and 'finished' not in message
    assert 'planner wake' in message
    notice = watch.wake(root)
    assert lifecycle.stop({'cwd': str(root)}) == (1, notice)
    assert lifecycle.stop({'cwd': str(root)}) == (0, '')


@pytest.mark.parametrize('event', ['session_start', 'pre_compact', 'stop'])
def test_lifecycle_outside_scope(case, event):
    root, _, _, _ = case
    lifecycle = lifecycle_module()
    assert getattr(lifecycle, event)({'cwd': str(root.parent / 'unrelated')}) == (0, '')


@pytest.mark.parametrize('condition,expected', [('clean', 0), ('corrupt_state', 2),
                                               ('corrupt_events', 2), ('partial_event', 2)])
def test_compact_table(case, condition, expected):
    root, _, _, _ = case
    lifecycle = lifecycle_module()
    directory = workspace.day_dir(root)
    if condition == 'corrupt_state':
        path = directory / 'state.json'
        path.chmod(0o600)
        path.write_text('{')
    if condition in ('corrupt_events', 'partial_event'):
        path = directory / 'events.jsonl'
        path.chmod(0o600)
        with path.open('a') as stream:
            stream.write('{' if condition == 'corrupt_events' else '{}')
    code, message = lifecycle.pre_compact({'cwd': str(root)})
    assert code == expected
    if code:
        assert message
    else:
        row, = events(root, 'session: compact')
        assert row['payload']['events_checked'] > 0


def test_hook_payload_survives_health_findings(case, monkeypatch, capsys):
    root, _, _, _ = case
    lifecycle_module()
    from wuwei.commands import hook
    payload = {'session_id': 'test', 'transcript_path': str(root / 'trace'),
               'cwd': str(root), 'hook_event_name': 'SessionStart'}
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps(payload)))
    assert hook.run(SimpleNamespace(event='SessionStart')) == 0
    output = json.loads(capsys.readouterr().out)
    context = output['hookSpecificOutput']['additionalContext']
    assert 'Size:' in context and 'watch dead' in context
    assert 'decision' not in output


def test_explicit_watch_sweep(case):
    assert main(['sweep', 'watch']) == 2
    row, = events(case[0], 'watch: sweep')
    assert row['payload']['watch_dead'] == 1


def test_singleton_and_graceful_shutdown(case):
    import fcntl
    root, _, _, _ = case
    watch = watch_module()
    with (root / '.wuwei/watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert watch.run(root, once=True) == 2
    def stop(seconds):
        raise KeyboardInterrupt
    assert watch.run(root, sleep=stop) == 0


@pytest.mark.parametrize('field,value', [('clock_seconds', 0), ('stale_seconds', -1),
                                         ('sweep_seconds', True)])
def test_watch_config_invalid(case, field, value):
    root, _, _, _ = case
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'\n[watch]\n{field}={json.dumps(value)}\n')
    assert main(['watch', '--once']) == 2


def test_memory_lint_when_available(case, monkeypatch):
    from wuwei import memory
    root, _, _, _ = case
    state.append_event('watch: clock', {}, root)
    monkeypatch.setattr(memory, 'lint', lambda root: ['memory lint finding'], raising=False)
    code, message = lifecycle_module().session_start({'cwd': str(root)})
    assert code == 1 and 'memory lint finding' in message


def test_poll_in_place_edit_and_unordered_evidence(case):
    root, host, _, _ = case
    watch = watch_module()
    comments = [{'id': n, 'author': 'reviewer', 'is_bot': False,
                 'body': 'text', 'created_at': workspace.now().isoformat()} for n in (1, 2)]
    host.results['threads'].data['comments'] = comments
    assert watch.poll(root) == 0
    comments.reverse()
    assert watch.poll(root) == 0
    comments[0]['body'] = 'edited text'
    assert watch.poll(root) == 1


def test_flush_rejects_complete_record_without_newline(case):
    root, _, _, _ = case
    path = workspace.day_dir(root) / 'events.jsonl'
    contents = path.read_text().rstrip('\n')
    path.chmod(0o600)
    path.write_text(contents)
    assert lifecycle_module().pre_compact({'cwd': str(root)})[0] == 2


def test_activity_tracks_launched_seat_worktree_from_brief(case):
    root, _, vcs, _ = case
    watch = watch_module()
    state.set_state('items.work', {}, root)
    state.append_event('brief written', {'name': 'builder', 'item': 'work',
        'path': 'briefs/builder.md', 'worktree': 'repo'}, root)
    state._write_state(lambda data: data['seats'].update(builder={
        'role': 'builder', 'item': 'work', 'status': 'running',
        'brief': 'briefs/builder.md'}), root, reserved=False)
    assert watch.activity(root)[0] == 0
    vcs.results['head'].data['sha'] = 'b' * 40
    assert watch.activity(root)[0] == 0
    row, = events(root, 'watch: heartbeat')
    assert row['payload']['item'] == 'work'


def test_sweep_clean_with_measured_scanner(case, monkeypatch):
    root, host, _, _ = case
    watch = watch_module()
    known = registry.known
    monkeypatch.setattr(registry, 'known', lambda kind: ['none', 'ziran']
                        if kind == 'scanner' else known(kind))
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[adapters]\nscanner="ziran"\n')
    (workspace.day_dir(root) / 'traces.jsonl').write_text('')
    state.append_event('watch: clock', {}, root)
    host.results['pr'].data['state'] = 'closed'
    assert watch.sweep(root) == 0
    row, = events(root, 'watch: sweep')
    assert row['payload']['owed'] == 0


def test_session_real_cli_boundary(case):
    import os
    import subprocess
    import sys
    root, _, _, _ = case
    project = Path(__file__).resolve().parents[1]
    payload = {'cwd': str(root), 'hook_event_name': 'SessionStart',
               'session_id': 'test', 'transcript_path': str(root / 'transcript')}
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'hook', 'SessionStart'],
        cwd=root, env={**os.environ, 'PYTHONPATH': str(project / 'cli')},
        input=json.dumps(payload), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
    assert 'Memory spine' in context and 'Size:' in context and 'watch dead' in context


def test_activity_baseline_survives_midnight(case):
    root, _, vcs, _ = case
    watch = watch_module()
    state.set_state('items.work', {'status': 'running', 'worktree': 'repo'}, root)
    assert watch.activity(root)[0] == 0
    advance(case, 86400)
    state.set_state('items.work', {'status': 'running', 'worktree': 'repo'}, root)
    vcs.results['head'].data['sha'] = 'b' * 40
    assert watch.activity(root)[0] == 0
    assert len(events(root, 'watch: heartbeat')) == 1


def test_successful_empty_discovery_after_pr_gone_is_measured(case):
    root, host, _, _ = case
    watch = watch_module()
    advance(case, 86400)
    state.write_state(lambda data: None, root)
    state.append_event('watch: clock', {}, root)
    watch.sweep(root)
    watch.sweep(root)
    summary = events(root, 'watch: sweep')[-1]['payload']
    assert summary['prs'] == 0
    assert summary['unreadable'] == 1  # Only the absent scanner is unmeasured.


def test_missing_notes_lint_is_unmeasured(case):
    root, _, _, _ = case
    (root / '.wuwei/memory/notes').rmdir()
    code, message = lifecycle_module().session_start({'cwd': str(root)})
    assert code == 2
    assert 'memory unmeasured:' in message and 'notes directory' in message


def test_session_payload_omits_watch_state(case):
    from wuwei import memory
    root, _, _, _ = case
    watch_module().poll(root)
    content, size, tokens = memory.session_payload(root)
    assert '"watch"' not in content
    assert '"raised_prs"' in content
    assert size == len(content.encode('utf-8'))
    assert tokens == memory.estimated_tokens(content)


def test_restart_dead_watch_swept_before_clock_hides_gap(case):
    root, _, _, _ = case
    watch = watch_module()
    watch.tick(root)
    advance(case, 1800)
    watch.tick(root)
    assert len(events(root, 'watch: sweep')) == 2
    assert events(root, 'watch: sweep')[-1]['payload']['watch_dead'] == 1
    for _ in range(10):
        advance(case, 60)
        watch.tick(root)
    assert len(events(root, 'watch: sweep')) == 2


def test_poll_and_sweep_only_day_prs(case):
    root, host, _, monkeypatch = case
    watch = watch_module()
    state.set_state('claimed_prs', [REF, 'example/project#8'], root)
    original = host.pr
    def read_pr(ref, root=None):
        result = original(ref, root=root)
        result.data['number'] = int(ref.split('#')[1])
        return result
    monkeypatch.setattr(host, 'pr', read_pr)
    watch.poll(root)
    watch.sweep(root)
    assert set(state.read_state(root)['watch']['prs']) == {REF, 'example/project#8'}
    assert events(root, 'watch: sweep')[-1]['payload']['prs'] == 2
    assert {call[0] for call in host.calls} <= {'pr', 'checks', 'reviews', 'threads'}


def test_failed_pr_does_not_hide_other_changes(case):
    from copy import deepcopy
    root, host, _, monkeypatch = case
    watch = watch_module()
    other = 'example/project#8'
    state.set_state('claimed_prs', [other], root)
    broken = False
    original = host.pr
    def read_pr(ref, root=None):
        if broken and ref == REF:
            return Result(2, None, 'cannot read PR')
        data = deepcopy(original(ref, root=root).data)
        data['number'] = int(ref.split('#')[1])
        return Result(0, data)
    monkeypatch.setattr(host, 'pr', read_pr)
    assert watch.poll(root) == 0
    before = state.read_state(root)['watch']['prs'][REF]
    broken = True
    host.results['pr'].data['head'] = 'b' * 40
    for _ in range(6):
        assert watch.poll(root) == 2
    value = state.read_state(root)['watch']
    assert value['prs'][REF] == before
    assert value['failures'] == 0
    row, = events(root, 'pr.changed')
    assert row['payload']['pr'] == other
    assert value['wake']['prs'] == [other]
    assert all(row['payload']['pr'] == REF for row in events(root, 'watch: read-failed'))


def test_stop_wake_once_accumulates_until_seen(case, capsys):
    from wuwei.commands import hook
    root, host, _, monkeypatch = case
    watch = watch_module()
    lifecycle_module()
    other = 'example/project#8'
    watch.poll(root)
    host.results['pr'].data['head'] = 'b' * 40
    watch.poll(root)
    state.set_state('claimed_prs', [other], root)
    original = host.pr
    def read_pr(ref, root=None):
        result = original(ref, root=root)
        result.data['number'] = int(ref.split('#')[1])
        return result
    monkeypatch.setattr(host, 'pr', read_pr)
    watch.poll(root)
    assert state.read_state(root)['watch']['wake']['prs'] == [REF, other]
    capsys.readouterr()
    payload = {'session_id': 'planner', 'transcript_path': str(root / 'trace'),
               'cwd': str(root), 'hook_event_name': 'Stop', 'stop_hook_active': False}
    def stop(active=False):
        monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps({**payload, 'stop_hook_active': active})))
        result = hook.run(SimpleNamespace(event='Stop'))
        return result, capsys.readouterr()
    assert stop(True)[0] == 0
    code, output = stop()
    assert code == 2
    result = json.loads(output.out)
    assert result['decision'] == 'block'
    assert REF in result['reason'] and other in result['reason']
    value = state.read_state(root)['watch']
    assert value['wake_seen_at'] == value['wake']['at']
    assert stop()[0] == 0
    assert not watch.wake(root)
    # Even two changes with the same wall clock must have different marker ids.
    host.results['pr'].data['head'] = 'c' * 40
    watch.poll(root)
    assert state.read_state(root)['watch']['wake']['at'] != value['wake']['at']
    capsys.readouterr()
    assert stop()[0] == 2
    advance(case, 86400)
    state.write_state(lambda data: None, root)
    assert stop()[0] == 0


@pytest.mark.parametrize('active', [False, True])
def test_stop_wake_read_failure_never_blocks(case, active):
    root, _, _, _ = case
    watch = watch_module()
    watch.save(root, {'wake': {'at': 'invalid', 'prs': [REF]}})
    code, message = lifecycle_module().stop({'cwd': str(root), 'stop_hook_active': active})
    assert code == 0
    assert ('unmeasured' in message) is (not active)


def test_sigterm_finishes_tick_before_stopping(case, monkeypatch):
    import signal
    root, _, _, _ = case
    watch = watch_module()
    handlers, finished = {}, []
    monkeypatch.setattr(signal, 'signal', lambda number, handler: handlers.setdefault(number, handler))
    original = watch.tick
    def tick(root):
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        result = original(root)
        finished.append(True)
        return result
    monkeypatch.setattr(watch, 'tick', tick)
    assert watch.run(root, sleep=lambda seconds: pytest.fail('must not sleep after SIGTERM')) == 0
    assert finished == [True]
    assert 'sweep_at' in state.read_state(root)['watch']


def test_loop_waits_on_shutdown_event(case, monkeypatch):
    import signal
    import threading
    root, _, _, _ = case
    watch = watch_module()
    waits, handlers = [], {}
    monkeypatch.setattr(signal, 'signal', lambda number, handler: handlers.setdefault(number, handler))
    def wait(event, seconds):
        waits.append(seconds)
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        return True
    monkeypatch.setattr(threading.Event, 'wait', wait)
    assert watch.run(root) == 0
    assert waits == [60]


def test_stop_does_not_overwrite_newer_acknowledgement(case, monkeypatch):
    root, host, _, _ = case
    watch = watch_module()
    watch.poll(root)
    host.results['pr'].data['head'] = 'b' * 40
    watch.poll(root)
    original = state._write_state
    later = (workspace.now() + timedelta(seconds=1)).isoformat()
    def raced(update, *args, **kwargs):
        def newer(data):
            data['watch']['wake']['at'] = later
            data['watch']['wake_seen_at'] = later
        original(newer, root, reserved=False)
        return original(update, *args, **kwargs)
    monkeypatch.setattr(state, '_write_state', raced)
    assert lifecycle_module().stop({'cwd': str(root)}) == (0, '')
    assert state.read_state(root)['watch']['wake_seen_at'] == later
