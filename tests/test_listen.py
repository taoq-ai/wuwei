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
    assert listen().tick(root) == 0
    assert listen().tick(root) == 0
    # A successful poll moves the cursor to the poll start, events or not.
    assert source.since == ['', NOW]
    assert json.loads((root / '.wuwei/inbox/cursor.json').read_text())['cursors'] == {'fake': NOW}
    source.results = [Result(0, [event('b', '2')])]
    assert listen().tick(root) == 0
    assert source.since[-1] == NOW and ids(root) == ['a', 'b']
    source.results = [Result(0, [event('c', '1790769700.000100')])]
    assert listen().tick(root) == 0
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
    assert listen().tick(root) == 0
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
    assert listen().tick(root) == 0
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
    assert listen().tick(root) == 0
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
    assert main(['listen', '--once']) == 0
    assert main(['listen', '--once']) == 0


def test_refused_command_is_a_normal_poll_and_unrun_is_2(case, handler, monkeypatch):
    from wuwei import remote
    root, source = case
    codes = [1, 2]
    monkeypatch.setattr(remote, 'handle', lambda root, row: codes.pop(0))
    source.results = [Result(0, [event('a', '1')]), Result(0, [event('b', '2')])]
    assert listen().tick(root) == 0
    assert listen().tick(root) == 2


def test_unset_owner_name_is_logged_once(case, capsys):
    from wuwei import outward
    root, source = case
    source.results = [Result(0, [event('a', '1'), event('b', '2')])]
    assert main(['listen', '--once']) == 0
    assert capsys.readouterr().out.count(outward.OWNER_UNSET) == 1
    config(root, '[owner]\nname = "Robin Example"\n')
    assert main(['listen', '--once']) == 0
    assert outward.OWNER_UNSET not in capsys.readouterr().out


def test_no_inbound_source_refuses_to_run(case, capsys):
    root, _ = case
    (root / '.wuwei/config.toml').write_text('')
    assert main(['listen', '--once']) == 2
    assert 'adapters.inbound is "none"' in capsys.readouterr().err
    assert main(['listen', 'install', '--dry-run']) == 2
    assert main(['listen', 'uninstall']) == 0


@pytest.mark.parametrize('kind', ['listen: clock', 'listen: wake', 'decision.escalated'])
def test_listener_kinds_are_reserved_and_silent(case, kind, capsys):
    from wuwei import signal
    assert main(['event', kind]) == 1
    assert 'wuwei listen' in capsys.readouterr().err
    assert kind in signal.SILENT


@pytest.fixture
def handler(case, monkeypatch):
    from wuwei import remote
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D1')
    seen = []

    def handle(root, row):
        seen.append(row['id'])
        return 0
    monkeypatch.setattr(remote, 'handle', handle)
    return seen


def test_new_lines_are_handed_to_the_command_handler_once(case, handler):
    root, source = case
    source.results = [Result(0, [event('a', '1'), event('b', '2')])]
    assert listen().tick(root) == 0
    assert listen().tick(root) == 0
    assert handler == ['a', 'b'] and listen().cursor(root)['handled'] == 2


def test_handler_crash_never_runs_a_command_twice(case, handler, monkeypatch):
    from wuwei import remote
    root, source = case

    def crash(root, row):
        raise OSError('disk full')
    monkeypatch.setattr(remote, 'handle', crash)
    source.results = [Result(0, [event('a', '1'), event('b', '2')])]
    with pytest.raises(OSError):
        listen().tick(root)
    assert listen().cursor(root)['handled'] == 1
    monkeypatch.setattr(remote, 'handle', lambda root, row: handler.append(row['id']) or 0)
    assert listen().tick(root) == 0
    assert handler == ['b']


def test_kill_switch_holds_commands_until_it_is_back_on(case, handler):
    root, source = case
    config(root, '[responder]\nenabled = false\n')
    source.results = [Result(0, [event('a', '1')])]
    assert listen().tick(root) == 0
    assert handler == [] and 'handled' not in listen().cursor(root)
    config(root, '')
    listen().tick(root)
    assert handler == ['a']


def test_lines_the_last_wake_covered_are_not_replayed(case, handler):
    root, source = case
    inbox.store(root, workspace.load_config(root), [event(n, str(i)) for i, n in enumerate('abcd', 1)])
    path = root / '.wuwei/inbox/cursor.json'
    path.write_text('{"cursors": {}, "woken": 3}\n')
    listen().tick(root)
    assert handler == ['d']


@pytest.mark.parametrize('value', ['-1', '"1"'])
def test_invalid_handled_count_fails(case, value):
    root, _ = case
    path = root / '.wuwei/inbox/cursor.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"cursors": {}, "woken": 0, "handled": ' + value + '}\n')
    with pytest.raises(ValueError):
        listen().cursor(root)


def test_issue_acceptance_stop_all_stops_every_session_in_one_tick(case, monkeypatch):
    from wuwei import remote
    root, source = case
    config(root, '[control_plane]\nowner = "T1/U1"\n')
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D1')
    sent = []
    monkeypatch.setattr(remote.TRANSPORT, 'dm', lambda text, *, root=None: sent.append(text) or Result(0, {}))

    def rows(data):
        for session in ('S1', 'S2'):
            data.setdefault('sessions', {})[session] = {'role': 'remote', 'thread': 'D1/0.1', 'command': 'plan'}
    state._write_state(rows, root, reserved=False)
    source.results.append(Result(0, [{**event('D1/1790769590.000100', '1790769590.000100', 'stop all'),
                                      'sender': 'T1/U1'}]))
    listen().tick(root)
    assert all('stopped' in row for row in state.read_state(root)['sessions'].values())
    assert sent == ['Stopped 2 sessions.'] and kinds(root, 'remote.pending') == []


def status_of(capsys):
    capsys.readouterr()
    assert main(['status', '--line']) == 0
    text = capsys.readouterr().out
    assert main(['status', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert main(['nudges']) == 0
    rows = [row for row in json.loads(capsys.readouterr().out) if row['source'] == 'listen: health']
    return text, data['listen'], rows


def test_issue_acceptance_dead_listener_shows_in_the_status_line(case, monkeypatch, capsys):
    root, _ = case
    state.append_event('listen: clock', {}, root)
    later(monkeypatch, 300)
    text, listening, rows = status_of(capsys)
    assert 'listen dead' in text and listening == 'dead'
    assert rows == [{'tier': 'page', 'source': 'listen: health', 'lane': 'Work',
                     'reason': 'listen dead: no clock line within deadline'}]


@pytest.mark.parametrize('setup, part, listening, tier', [
    ('fresh', None, 'alive', None),
    ('unit', 'listen dead', 'dead', 'page'),
    ('nothing', 'listen off', 'off', None),
    ('no inbound', None, 'none', None),
    ('future', 'listen unmeasured', 'unmeasured', 'nudge'),
])
def test_listener_states_in_the_status_line(case, monkeypatch, capsys, setup, part, listening, tier):
    root, _ = case
    state._write_state(lambda data: None, root, reserved=False)
    if setup in ('fresh', 'future'):
        state.append_event('listen: clock', {}, root)
    if setup == 'future':
        later(monkeypatch, -60)
    if setup == 'unit':
        unit = workspace.watch_unit(root, name='listen')[1]
        unit.parent.mkdir(parents=True)
        unit.write_text('')
    if setup == 'no inbound':
        (root / '.wuwei/config.toml').write_text('')
    text, measured, rows = status_of(capsys)
    assert measured == listening
    assert (part in text) if part else ('listen' not in text)
    assert [row['tier'] for row in rows] == ([tier] if tier else [])


def host_decision(root):
    from wuwei import decision, remote
    text = remote.DENIAL.format(session='1a2b3c4d', tool='Bash')
    path = decision.write(text, root)
    decision.route_owner(path.stem, decision.evaluate(text)[0], root)


@pytest.fixture
def dm(case, monkeypatch):
    from wuwei import remote
    root, _ = case
    config(root, '[owner]\nname = "Robin Example"\n[control_plane]\nowner = "T1/U1"\n')
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D1')
    sent = []
    monkeypatch.setattr(remote.TRANSPORT, 'dm', lambda text, *, root=None: sent.append(text) or Result(0, {}))
    host_decision(root)
    return sent


def test_issue_acceptance_host_decision_reaches_the_dm(case, dm):
    root, _ = case
    assert listen().tick(root) == 0
    assert listen().tick(root) == 0
    assert len(dm) == 1 and dm[0].startswith('D-1: ')
    assert [row['payload'] for row in kinds(root, 'decision.escalated')] == [{'id': 'D-1'}]


@pytest.mark.parametrize('off', ['kill switch', 'no channel'])
def test_no_escalation_without_the_responder_or_the_channel(case, dm, monkeypatch, off):
    root, _ = case
    if off == 'kill switch':
        config(root, '[control_plane]\nowner = "T1/U1"\n[responder]\nenabled = false\n')
    else:
        monkeypatch.delenv('SLACK_OWNER_DM_CHANNEL')
    assert listen().tick(root) == 0
    assert dm == [] and kinds(root, 'decision.escalated') == []


def test_an_escalation_that_cannot_run_fails_the_tick(case, dm, monkeypatch, capsys):
    from wuwei import remote
    root, _ = case
    monkeypatch.setattr(remote.TRANSPORT, 'dm', lambda text, *, root=None: Result(2, None, 'down'))
    assert listen().tick(root) == 2
    assert kinds(root, 'decision.escalated') == []
    (workspace.day_dir(root) / 'decisions/D-1.md').write_text('garbage\n')
    assert listen().tick(root) == 2
    assert 'listen escalate unmeasured:' in capsys.readouterr().out


def test_session_start_shows_a_phone_answer_without_changing_its_code(case):
    root, _ = case
    assert lifecycle.session_start({'cwd': str(root)})[0] == 0
    host_decision(root)
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert 'answered from the phone' not in message
    state.append_event('decision.replied', {'id': 'D-1', 'option': 'A'}, root)
    assert lifecycle.session_start({'cwd': str(root)}) == (
        code, message + '\nD-1 answered from the phone: option A, confirm with decision outcome D-1 A')
