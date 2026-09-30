"""The listener: inbound events land in the inbox once, wake the planner, report a clock."""

from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from wuwei import inbox, registry, state, watch, workspace
from wuwei.__main__ import main
from wuwei.guards import lifecycle
from wuwei.registry import Result


class Source:
    def __init__(self):
        self.results, self.since = [], []

    def poll(self, since, *, root=None):
        self.since.append(since)
        return self.results.pop(0) if self.results else Result(0, [])


@pytest.fixture
def case(tmp_path, monkeypatch):
    (tmp_path / '.wuwei/memory/notes').mkdir(parents=True)
    (tmp_path / '.wuwei/memory/spine.md').write_text('Memory spine\n')
    (tmp_path / '.wuwei/memory/index.md').write_text('Index\n')
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\ninbound = "fake"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00+00:00')
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    source = Source()
    real_validate, real_load = registry.validate, registry.load
    monkeypatch.setattr(registry, 'validate', lambda kind, name, **kw: None if (
        kind, name) == ('inbound', 'fake') else real_validate(kind, name, **kw))
    monkeypatch.setattr(registry, 'load', lambda kind, config: source if kind == 'inbound'
                        else real_load(kind, config))
    return tmp_path, source


NOW = '1790769600'  # WUWEI_NOW in epoch seconds


def event(ident, ts, text='hello'):
    return {'id': ident, 'source': 'slack', 'channel': 'D1', 'thread': '', 'sender': 'U1',
            'text': text, 'ts': ts}


def config(root, text):
    (root / '.wuwei/config.toml').write_text('[adapters]\ninbound = "fake"\n' + text)


def ids(root):
    return [row['id'] for row in inbox.read(root)]


def kinds(root, kind):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row for row in map(json.loads, path.read_text().splitlines()) if row['kind'] == kind]


def later(monkeypatch, seconds):
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=seconds)).isoformat())


def listen():
    from wuwei import listen
    return listen


def test_store_drops_events_already_stored_or_repeated(case):
    root, _ = case
    settings = workspace.load_config(root)
    assert inbox.store(root, settings, [event('a', '1')]) == Result(0, 1)
    result = inbox.store(root, settings, [event('a', '1'), event('b', '2'), event('b', '2')])
    assert result == Result(0, 1)
    assert ids(root) == ['a', 'b']
    assert inbox.store(root, settings, [event('a', '1')]) == Result(0, 0)


def test_store_fails_closed_on_a_corrupt_inbox(case):
    root, _ = case
    path = root / '.wuwei/inbox/inbox.jsonl'
    path.parent.mkdir(parents=True)
    path.write_text('{not json\n')
    assert inbox.store(root, workspace.load_config(root), [event('a', '1')]).exit == 2
    assert path.read_text() == '{not json\n'


def test_config_defaults(case):
    root, _ = case
    settings = workspace.load_config(root)
    assert settings['listen'] == {'poll_seconds': 60, 'dead_seconds': 300}
    assert settings['responder'] == {'enabled': True}


def test_cursor_moves_after_each_stored_batch(case):
    root, source = case
    source.results = [Result(0, [event('a', '1'), event('b', '2')]), Result(0, [])]
    assert listen().tick(root) == 1
    assert listen().tick(root) == 0
    # A successful poll moves the cursor to the poll start, events or not.
    assert source.since == ['', NOW]
    assert json.loads((root / '.wuwei/inbox/cursor.json').read_text())['cursors'] == {'fake': NOW}
    source.results = [Result(0, [event('b', '2')])]
    assert listen().tick(root) == 0
    assert source.since[-1] == NOW and ids(root) == ['a', 'b']
    source.results = [Result(0, [event('c', '1790769700.000100')])]
    assert listen().tick(root) == 1
    assert listen().cursor(root)['cursors'] == {'fake': '1790769700.000100'}


def test_failing_source_or_store_leaves_the_cursor(case, monkeypatch, capsys):
    root, source = case
    source.results = [Result(2, None, 'down')]
    assert listen().tick(root) == 2
    assert 'down' in capsys.readouterr().out
    monkeypatch.setattr(inbox, 'store', lambda *args: Result(2, None, 'disk full'))
    source.results = [Result(0, [event('a', '1')])]
    assert listen().tick(root) == 2
    assert 'disk full' in capsys.readouterr().out
    assert listen().cursor(root)['cursors'] == {}


def test_corrupt_cursor_fails(case):
    root, _ = case
    path = root / '.wuwei/inbox/cursor.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"cursors": [], "woken": 0}\n')
    with pytest.raises(ValueError):
        listen().tick(root)


def test_restart_mid_batch_loses_nothing_and_stores_nothing_twice(case, monkeypatch):
    root, source = case
    batch = [event('a', '1'), event('b', '2'), event('c', '3')]
    real, lines = state.append_jsonl, []
    def crash(path, record):
        if path.name == 'inbox.jsonl':
            lines.append(record)
            if len(lines) == 2:
                raise KeyboardInterrupt
        return real(path, record)
    monkeypatch.setattr(state, 'append_jsonl', crash)
    source.results = [Result(0, batch)]
    with pytest.raises(KeyboardInterrupt):
        listen().tick(root)
    monkeypatch.setattr(state, 'append_jsonl', real)
    assert ids(root) == ['a'] and listen().cursor(root)['cursors'] == {}
    source.results = [Result(0, batch)]
    assert listen().tick(root) == 1
    assert ids(root) == ['a', 'b', 'c']
    assert source.since == ['', '']
    assert listen().cursor(root)['cursors'] == {'fake': NOW}


def test_wake_marker_merges_prs_and_inbox(case):
    root, _ = case
    watch.mark_wake(root, prs=['example/project#7'], kind='pr.changed', payload={})
    watch.mark_wake(root, inbox=3, kind='listen: wake', payload={})
    marker = watch.saved(root)['wake']
    assert (marker['prs'], marker['inbox']) == (['example/project#7'], 3)
    watch.mark_wake(root, prs=['example/project#8'], kind='pr.changed', payload={})
    marker = watch.saved(root)['wake']
    assert (marker['prs'], marker['inbox']) == (['example/project#7', 'example/project#8'], 3)
    watch.mark_wake(root, inbox=3, kind='listen: wake', payload={})
    assert watch.saved(root)['wake'] == marker
    assert watch.wake(root).endswith('example/project#7, example/project#8, inbox to line 3')


def test_wake_renders_inbox_only_and_rejects_bad_counts(case):
    root, _ = case
    watch.mark_wake(root, inbox=2, kind='listen: wake', payload={})
    assert watch.wake(root).endswith('): inbox to line 2')
    for bad in (-1, '2'):
        watch.save(root, {'wake': {'at': workspace.now().isoformat(), 'prs': [], 'inbox': bad}})
        with pytest.raises(ValueError):
            watch.wake(root)


def test_pr_only_marker_is_unchanged(case):
    root, _ = case
    watch.mark_wake(root, prs=['example/project#7'], kind='pr.changed', payload={})
    assert watch.saved(root)['wake'] == {'at': workspace.now().isoformat(), 'prs': ['example/project#7']}
    assert watch.wake(root) == f'planner wake ({workspace.now().isoformat()}): example/project#7'


def test_new_events_wake_the_planner_once(case, capsys):
    root, source = case
    source.results = [Result(0, [event('a', '1'), event('b', '2')])]
    assert listen().tick(root) == 1
    assert len(kinds(root, 'listen: wake')) == 1
    assert watch.saved(root)['wake']['inbox'] == 2
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert 'planner wake' in message and 'inbox to line 2' in message
    assert main(['plan', 'session', 'planner']) == 0
    assert lifecycle.stop({'cwd': str(root), 'session_id': 'planner'})[0] == 1
    assert lifecycle.stop({'cwd': str(root), 'session_id': 'planner'}) == (0, '')
    assert listen().tick(root) == 0
    assert len(kinds(root, 'listen: wake')) == 1


def test_kill_switch_stores_but_does_not_wake(case):
    root, source = case
    config(root, '[responder]\nenabled = false\n')
    source.results = [Result(0, [event('a', '1')])]
    assert listen().tick(root) == 1
    assert ids(root) == ['a']
    assert not kinds(root, 'listen: wake')
    assert watch.wake(root) == ''
    assert listen().cursor(root)['woken'] == 0
    config(root, '')
    assert listen().tick(root) == 0
    assert listen().tick(root) == 0
    assert len(kinds(root, 'listen: wake')) == 1
    assert 'inbox to line 1' in watch.wake(root)


def test_crash_after_wake_does_not_wake_twice(case, monkeypatch):
    root, source = case
    module = listen()
    real = module._save
    def crash(root, data):
        if data['woken']:
            raise OSError('disk full')
        return real(root, data)
    monkeypatch.setattr(module, '_save', crash)
    source.results = [Result(0, [event('a', '1')])]
    with pytest.raises(OSError):
        module.tick(root)
    monkeypatch.setattr(module, '_save', real)
    marker = watch.saved(root)['wake']
    assert main(['plan', 'session', 'planner']) == 0
    assert lifecycle.stop({'cwd': str(root), 'session_id': 'planner'})[0] == 1
    assert module.tick(root) == 0
    assert watch.saved(root)['wake'] == marker
    assert module.cursor(root)['woken'] == 1
    assert lifecycle.stop({'cwd': str(root), 'session_id': 'planner'}) == (0, '')


def test_dead_listener_is_reported_at_session_start(case, monkeypatch):
    root, _ = case
    assert watch.health(root, name='listen') == (0, 'listen off: no clock line today')
    assert 'listen' not in lifecycle.session_start({'cwd': str(root)})[1]
    state.append_event('listen: clock', {}, root)
    later(monkeypatch, 299)
    assert watch.health(root, name='listen') == (0, '')
    assert 'listen' not in lifecycle.session_start({'cwd': str(root)})[1]
    later(monkeypatch, 1)
    assert watch.health(root, name='listen') == (1, 'listen dead: no clock line within deadline')
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert code == 1 and 'listen dead' in message


def test_installed_listener_without_clock_is_dead(case):
    root, _ = case
    label, unit = workspace.watch_unit(root, name='listen')
    assert label.startswith('wuwei-listen-')
    assert 'listen' not in workspace.watch_unit(root)[0]
    unit.parent.mkdir(parents=True)
    unit.write_text('')
    assert watch.health(root, name='listen') == (1, 'listen dead: installed but no clock line today')


def test_tick_writes_the_clock_line(case, monkeypatch):
    root, _ = case
    listen().tick(root)
    listen().tick(root)
    assert len(kinds(root, 'listen: clock')) == 1
    later(monkeypatch, 120)
    listen().tick(root)
    assert len(kinds(root, 'listen: clock')) == 2


def test_one_listener_per_workspace(case):
    import fcntl
    root, _ = case
    with (root / '.wuwei/listen.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert listen().run(root, once=True) == 2


def test_interrupted_sleep_stops_cleanly(case):
    root, _ = case
    waits = []
    def sleep(seconds):
        waits.append(seconds)
        raise KeyboardInterrupt
    config(root, '[listen]\npoll_seconds = 30\n')
    assert listen().run(root, sleep=sleep) == 0
    assert waits == [30]


def test_sigterm_finishes_tick_before_stopping(case, monkeypatch):
    import signal
    root, _ = case
    module = listen()
    handlers, finished = {}, []
    monkeypatch.setattr(signal, 'signal', lambda number, handler: handlers.setdefault(number, handler))
    original = module.tick
    def tick(root):
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        result = original(root)
        finished.append(True)
        return result
    monkeypatch.setattr(module, 'tick', tick)
    assert module.run(root, sleep=lambda seconds: pytest.fail('must not sleep after SIGTERM')) == 0
    assert finished == [True]


def test_install_dry_run_renders_a_listen_unit(case, capsys):
    root, _ = case
    assert main(['listen', 'install', '--dry-run']) == 0
    out = capsys.readouterr().out
    assert 'wuwei-listen-' in out and 'listen' in out.split('bin/wuwei', 1)[1].split('\n', 1)[0]
    assert not workspace.watch_unit(root, name='listen')[1].exists()
    assert main(['watch', 'install', '--dry-run']) == 0
    out = capsys.readouterr().out
    assert 'wuwei-listen-' not in out and workspace.watch_unit(root)[0] in out
    assert 'watch' in out.split('bin/wuwei', 1)[1].split('\n', 1)[0]


def test_install_and_uninstall(case, monkeypatch):
    from wuwei.commands import watch as watch_command
    root, _ = case
    calls = []
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(call=calls.append))
    monkeypatch.setattr(watch_command, 'service_platform', lambda: 'linux')
    assert main(['listen', 'install']) == 0
    unit, = (root / 'config/systemd/user').glob('wuwei-listen-*.service')
    assert 'bin/wuwei" listen\n' in unit.read_text()
    assert ['systemctl', '--user', 'enable', '--now', unit.name] in calls
    assert main(['listen', 'uninstall']) == 0
    assert not unit.exists()
    assert ['systemctl', '--user', 'disable', '--now', unit.name] in calls


def test_once_returns_the_tick_code(case):
    _, source = case
    source.results = [Result(0, [event('a', '1')])]
    assert main(['listen', '--once']) == 1
    assert main(['listen', '--once']) == 0


def test_no_inbound_source_refuses_to_run(case, capsys):
    root, _ = case
    (root / '.wuwei/config.toml').write_text('')
    assert main(['listen', '--once']) == 2
    assert 'adapters.inbound is "none"' in capsys.readouterr().err
    assert main(['listen', 'install', '--dry-run']) == 2
    assert main(['listen', 'uninstall']) == 0


@pytest.mark.parametrize('kind', ['listen: clock', 'listen: wake'])
def test_listener_kinds_are_reserved_and_silent(case, kind):
    from wuwei import signal
    assert main(['event', kind]) == 1
    assert kind in signal.SILENT
