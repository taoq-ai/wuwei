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


def test_wake_marker_keeps_summaries_while_unseen(case):
    root, _ = case
    ref = 'example/project#7'
    watch.mark_wake(root, prs=[ref], summaries=['PR a: x'], kind='pr.changed', payload={})
    watch.mark_wake(root, prs=[ref], summaries=['PR a: y'], kind='pr.changed', payload={})
    assert watch.saved(root)['wake']['summaries'] == ['PR a: x', 'PR a: y']
    message = watch.wake(root)
    assert message.split('\n')[:2] == ['PR a: x', 'PR a: y']
    assert message.split('\n')[2] == f'planner wake ({watch.saved(root)["wake"]["at"]}): {ref}'
    assert watch.wake(root, consume=True)
    watch.mark_wake(root, prs=[ref], summaries=['PR a: z'], kind='pr.changed', payload={})
    assert watch.saved(root)['wake']['summaries'] == ['PR a: z']
    watch.mark_wake(root, prs=[ref], summaries=[f'PR a: {n}' for n in range(25)],
                    kind='pr.changed', payload={})
    assert watch.saved(root)['wake']['summaries'] == [f'PR a: {n}' for n in range(5, 25)]


def test_summary_only_mark_is_not_already_covered(case):
    root, _ = case
    watch.mark_wake(root, inbox=2, kind='listen: wake', payload={})
    watch.mark_wake(root, summaries=['PR a: shepherd done'], kind='pr.changed', payload={})
    assert watch.wake(root).startswith('PR a: shepherd done\nplanner wake (')


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
    def tick(root, tags=None):
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
    assert main(['nudges', '--json']) == 0
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
        code, message + '\nD-1 answered from the phone: option A, confirm with wuwei decide D-1 A')


def test_session_start_decodes_a_day_without_routes_once(case, monkeypatch):
    # #346: phone answers need decision routes, so a day without them skips status.scan;
    # watch health still decodes the day and still reports a broken events file.
    from wuwei.commands import status
    root, _ = case
    expected = lifecycle.session_start({'cwd': str(root)})
    monkeypatch.setattr(status, 'scan', lambda *args: pytest.fail('second decode of the day'))
    assert lifecycle.session_start({'cwd': str(root)}) == expected
    state.append_event('note', {'detail': 'x'}, root)
    events = workspace.day_dir(root) / 'events.jsonl'
    events.chmod(0o644)
    with events.open('a') as stream:
        stream.write('{"kind": "torn')
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert code == 2 and 'watch health unmeasured: incomplete event line' in message


REF = 'example/project#7'
PR_CONFIG = '[owner]\nname = "Robin Example"\nhandles = ["owner"]\n[[repos]]\nname = "example/project"\npath = "repo"\ndefault_branch = "main"\n'
TAGS = {'pr': '"p"', 'head': 'a' * 40, 'checks': '"c"', 'statuses': '"s"'}


@pytest.fixture
def prs(case, monkeypatch):
    from fakes.code_host import Fake as Host
    from fakes.vcs import Fake as VCS
    root, source = case
    config(root, PR_CONFIG)
    host, vcs = Host(), VCS()
    host.results.update(reviews=Result(0, []), threads=Result(0, {'comments': [], 'threads': []}),
                        checks=Result(0, []), probe=Result(0, {'modified': True, 'tags': TAGS}))
    host.results['pr'].data.update(repo='example/project', number=7)
    load = registry.load
    chat = SimpleNamespace(sent=[], exit=0)

    def send(text, *, root=None):
        if chat.exit:
            return Result(chat.exit, None, 'chat failed')
        chat.sent.append(text)
        return Result(0, {})
    chat.dm = lambda text, *, root=None: pytest.fail('the drafting wrapper must not run')
    chat.dm.__wrapped__ = send
    ports = {'code_host': host, 'vcs': vcs, 'chat': chat}
    monkeypatch.setattr(registry, 'load', lambda kind, settings: ports[kind] if kind in ports
                        else load(kind, settings))
    state._write_state(lambda data: data.update(raised_prs=[REF]), root, reserved=False)
    host.chat = chat
    return root, host


def files(root):
    return {name: (workspace.day_dir(root) / name).read_bytes() for name in ('events.jsonl', 'state.json')}


def test_listener_probes_and_reads_fully_only_on_change(prs, monkeypatch):
    root, host = prs
    tags = {}
    assert listen().tick(root, tags) == 0
    assert tags == {REF: TAGS}
    assert watch.saved(root)['poll_at'] == workspace.now().isoformat()
    assert host.calls[0][:2] == ('probe', (REF, {}))
    host.results['probe'] = Result(0, {'modified': False, 'tags': TAGS})
    later(monkeypatch, 30)
    before = files(root)
    monkeypatch.setattr(watch, 'poll', lambda root: pytest.fail('full read without a change'))
    assert listen().tick(root, tags) == 0
    assert files(root) == before
    assert ('probe', (REF, TAGS), root) in host.calls


@pytest.mark.parametrize('probe', [Result(2, None, 'gh failed'), Result(0, {'modified': 'yes', 'tags': {}}),
                                   Result(0, {'modified': False})])
def test_failed_or_malformed_probe_reads_fully(prs, monkeypatch, probe):
    root, host = prs
    tags = {}
    assert listen().tick(root, tags) == 0
    host.results['probe'] = probe
    later(monkeypatch, 30)
    polled = []
    monkeypatch.setattr(watch, 'poll_prs', lambda root: polled.append(root) or 0)
    assert listen().tick(root, tags) == 0
    assert polled == [root] and REF not in tags


def test_backstop_reads_fully_when_poll_at_is_old(prs, monkeypatch):
    root, host = prs
    tags = {}
    listen().tick(root, tags)
    host.results['probe'] = Result(0, {'modified': False, 'tags': TAGS})
    later(monkeypatch, 120)
    polled = []
    monkeypatch.setattr(watch, 'poll_prs', lambda root: polled.append(root) or 0)
    listen().tick(root, tags)
    assert polled == [root]


def test_failed_full_read_forgets_the_tags(prs, monkeypatch):
    root, host = prs
    tags = {'other/repo#1': TAGS}
    monkeypatch.setattr(watch, 'poll_prs', lambda root: 2)
    assert listen().tick(root, tags) == 2
    assert tags == {}


def test_new_review_comment_reaches_wake_and_nudges_in_one_tick(prs, monkeypatch):
    from wuwei.commands import status
    root, host = prs
    tags = {}
    listen().tick(root, tags)
    assert main(['plan', 'session', 'planner']) == 0
    host.results['threads'].data['comments'] = [{'id': 5, 'author': 'alice', 'is_bot': False,
        'body': 'private text', 'created_at': workspace.now().isoformat()}]
    later(monkeypatch, 30)
    assert listen().tick(root, tags) == 0
    summary = f'PR {REF}: 1 new comment by alice'
    assert kinds(root, 'pr.changed')[-1]['payload']['summary'] == summary
    assert status.attention(workspace.day_dir(root))[0]['reason'] == summary
    code, message = lifecycle.stop({'cwd': str(root), 'session_id': 'planner'})
    assert code == 1 and message.split('\n')[0] == summary


def change(host, monkeypatch, **pr):
    host.results['pr'].data.update(pr)
    later(monkeypatch, 30)


@pytest.fixture
def owner_dm(prs, monkeypatch):
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D1')
    root, host = prs
    listen().tick(root, {})
    return root, host


def test_pr_change_reaches_the_owner_dm_once(owner_dm, monkeypatch):
    root, host = owner_dm
    change(host, monkeypatch, head='b' * 40)
    assert listen().tick(root, {}) == 0
    summary = f'PR {REF}: new commits pushed (head bbbbbbb)'
    assert host.chat.sent == [summary]
    row, = kinds(root, 'pr.notified')
    assert row['payload']['pr'] == REF and row['payload']['at'] == kinds(root, 'pr.changed')[-1]['ts']
    later(monkeypatch, 30)
    assert listen().tick(root, {}) == 0
    assert host.chat.sent == [summary]


def test_full_nudges_name_the_changed_fields(owner_dm, monkeypatch):
    root, host = owner_dm
    config(root, PR_CONFIG + '[owner.verbosity]\nnudges = "full"\n')
    change(host, monkeypatch, head='b' * 40)
    assert listen().tick(root, {}) == 0
    assert host.chat.sent == [f'PR {REF}: new commits pushed (head bbbbbbb) (fields: head)']
    later(monkeypatch, 30)
    state.append_event('pr.changed', {'pr': REF, 'fields': 'head', 'summary': 'PR x: y'}, root)
    assert listen().notify(root, workspace.load_config(root), []) == 0
    assert host.chat.sent[-1] == 'PR x: y'

def test_dm_says_autostart_is_off_for_a_mechanical_action(owner_dm, monkeypatch):
    root, host = owner_dm
    change(host, monkeypatch, mergeable=False)
    assert listen().tick(root, {}) == 0
    assert host.chat.sent == [f'PR {REF}: conflicts with its base. Shepherd autostart is off; nothing started.']


def test_content_none_sends_the_fixed_line(owner_dm, monkeypatch):
    root, host = owner_dm
    config(root, PR_CONFIG + '[control_plane]\ncontent = "none"\n')
    change(host, monkeypatch, head='b' * 40)
    listen().tick(root, {})
    assert host.chat.sent == ['An update is waiting in the workspace.']


def test_lint_refusal_sends_the_fallback_line(owner_dm, monkeypatch):
    root, host = owner_dm
    host.results['threads'].data['threads'] = [{'id': 'T', 'resolved': False, 'outdated': False,
        'path': 'cli/wuwei/guards/deploy.py', 'comments': [{'id': 3, 'author': 'alice', 'is_bot': False,
        'body': 'x', 'created_at': workspace.now().isoformat()}]}]
    change(host, monkeypatch)
    listen().tick(root, {})
    assert host.chat.sent == ['PR #7 changed; details are on the host.']
    assert len(kinds(root, 'pr.notified')) == 1


def test_failed_transport_records_nothing_and_retries(owner_dm, monkeypatch):
    root, host = owner_dm
    host.chat.exit = 2
    change(host, monkeypatch, head='b' * 40)
    assert listen().tick(root, {}) == 2
    assert not kinds(root, 'pr.notified')
    host.chat.exit = 0
    later(monkeypatch, 30)
    assert listen().tick(root, {}) == 0
    assert len(host.chat.sent) == 1


LOOP_REASON = ('alpha is going back and forth: 2 records, 3 reviews, 1 restarts and 1 fix requests '
               'in 4 hours, 1 fix rounds today; last: 11:00 arch review FIX; 11:00 fix requested')


def loop_event(root, reason=LOOP_REASON):
    state.append_event('negotiation.loop', {'item': 'alpha', 'reason': reason, 'past_goal': False}, root)


def test_negotiation_loop_reaches_the_owner_dm_once(owner_dm, monkeypatch):
    root, host = owner_dm
    loop_event(root)
    assert listen().tick(root, {}) == 0
    assert host.chat.sent == [LOOP_REASON]
    row, = kinds(root, 'negotiation.notified')
    assert row['payload']['item'] == 'alpha'
    later(monkeypatch, 30)
    assert listen().tick(root, {}) == 0
    assert host.chat.sent == [LOOP_REASON]


@pytest.mark.parametrize('content,reason,expected', [
    ('none', LOOP_REASON, 'An update is waiting in the workspace.'),
    ('summary', 'the seat keeps asking', 'Item alpha is going back and forth; details are on the host.')])
def test_negotiation_loop_dm_fallbacks(owner_dm, content, reason, expected):
    root, host = owner_dm
    config(root, PR_CONFIG + f'[control_plane]\ncontent = "{content}"\n')
    loop_event(root, reason)
    listen().tick(root, {})
    assert host.chat.sent == [expected]
    assert len(kinds(root, 'negotiation.notified')) == 1


def test_negotiation_loop_failed_transport_records_nothing(owner_dm):
    root, host = owner_dm
    host.chat.exit = 2
    loop_event(root)
    assert listen().tick(root, {}) == 2
    assert not kinds(root, 'negotiation.notified')


@pytest.mark.parametrize('setting', ['no channel', 'kill switch'])
def test_no_dm_without_channel_or_with_the_kill_switch(owner_dm, monkeypatch, setting):
    root, host = owner_dm
    if setting == 'no channel':
        monkeypatch.delenv('SLACK_OWNER_DM_CHANNEL')
    else:
        config(root, PR_CONFIG + '[responder]\nenabled = false\n')
    change(host, monkeypatch, head='b' * 40)
    listen().tick(root, {})
    assert host.chat.sent == [] and not kinds(root, 'pr.notified')


def test_fixed_dm_lines_pass_the_owner_lint(case):
    from wuwei import outward
    root, _ = case
    module = listen()
    settings = workspace.load_config(root)
    from wuwei import shepherd
    from wuwei.pr_actions import ACTIONS
    starts = [f'Shepherd starts: {ACTIONS[name][0]}.' for name in shepherd.HEADLESS]
    for text in (module.AUTOSTART_OFF, module.FALLBACK.format(number=7),
                 module.LOOP_FALLBACK.format(item='alpha'), LOOP_REASON, *starts):
        assert outward.lint(text, 'D1', settings, to_owner=True)[0] == 0, text


SID = '0f8f5c1e-1111-4222-8333-444455556666'


class Seat:
    """A fake Claude runtime: the real launch prompt, a recorded headless turn."""

    def __init__(self, result=None):
        self.calls, self.result = [], result or Result(0, {'session_id': SID, 'result': 'done', 'denials': []})

    def dispatch(self, role, brief_path, worktree, write, *, root=None):
        from wuwei import brief, security
        self.calls.append(('dispatch', role))
        return Result(0, {'prompt': brief.launch_prompt(brief_path, security.agent_path(root, role), root=root)})

    def headless(self, prompt, session, tools, *, root=None, variables=None):
        self.calls.append(('headless', prompt, session, tools, variables))
        return self.result


@pytest.fixture
def seat(prs, monkeypatch):
    from wuwei import mcp
    from wuwei.guards import agent_launch
    root, host = prs
    monkeypatch.setattr(mcp, 'cached', lambda root: Result(0))
    monkeypatch.setattr(mcp, 'launch', lambda root=None, path=None: Result(0))
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 2**40)
    tree = root / 'repo'
    tree.mkdir()
    def link(data):
        data['items']['A'] = {**state.ITEM_DEFAULTS, 'worktree': str(tree), 'pr': REF}
        data['approved_items'] = ['A']
    state._write_state(link, root, reserved=False)
    registry.load('vcs', None).results['branches'] = Result(0, [])
    host.results['pr'].data['mergeable'] = False
    watch.poll(root)
    return root, host, Seat()


def briefs(root):
    return [row['payload'] for row in kinds(root, 'brief written') if row['payload']['role'] == 'shepherd']


def test_pending_lists_mechanical_episodes_once(seat):
    from wuwei import shepherd
    root, host, runtime = seat
    (ref, episode), = shepherd.pending(root)
    assert ref == REF and episode['state'] == 'conflicted'
    state.append_event('shepherd.dispatched', {'pr': REF, 'state': 'conflicted',
                                               'episode': episode['created_at']}, root)
    assert shepherd.pending(root) == []


@pytest.mark.parametrize('mergeable,parked', [(True, False), (False, True)])
def test_pending_skips_waiting_and_parked(seat, mergeable, parked):
    from wuwei import shepherd
    root, host, _ = seat
    host.results['pr'].data['mergeable'] = mergeable
    watch.poll(root)
    if parked:
        state._write_state(lambda data: data.update(pr_dispositions={REF: {'kind': 'parked'}}),
                           root, reserved=False)
    assert shepherd.pending(root) == []


def test_headless_shepherd_runs_one_logged_seat(seat):
    from wuwei import shepherd
    root, host, runtime = seat
    (ref, episode), = shepherd.pending(root)
    assert shepherd.headless(root, ref, episode, runtime=runtime) == 0
    logged, = briefs(root)
    text = (root / logged['path']).read_text()
    assert f'wuwei pr act {REF} --run' in text and '--complete' in text and 'Never run wuwei merge' in text
    assert [call[0] for call in runtime.calls] == ['dispatch', 'headless']
    _, prompt, session, tools, variables = runtime.calls[1]
    assert prompt.startswith('WUWEI brief: ') and session is None
    assert tools == ['Read', 'Glob', 'Grep', 'Bash', 'Write']
    assert variables == {'WUWEI_SEAT_ROLE': 'shepherd'}
    data = state.read_state(root)
    assert data['seats'][logged['name']]['status'] == 'stopped'
    assert data['sessions'][SID]['role'] == 'shepherd'
    order = [row['kind'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')]
    assert order.index('shepherd.dispatched') < order.index('brief written') < order.index('shepherd.finished')
    finished, = kinds(root, 'shepherd.finished')
    assert finished['payload']['exit'] == 0 and finished['payload']['session'] == SID
    assert f'PR {REF}: shepherd conflicted: turn ended (exit 0, session {SID[:8]})' in watch.wake(root)


def test_headless_question_without_record_is_flagged(seat):
    from wuwei import shepherd
    root, host, _ = seat
    runtime = Seat(Result(0, {'session_id': SID, 'result': 'Shall I reply to the reviewer?',
                              'denials': []}))
    (ref, episode), = shepherd.pending(root)
    assert shepherd.headless(root, ref, episode, runtime=runtime) == 1
    finished, = kinds(root, 'shepherd.finished')
    assert finished['payload']['exit'] == 1 and 'Cite a decision D-n' in finished['payload']['reason']


def test_low_memory_refuses_before_the_turn(seat, monkeypatch):
    from wuwei import shepherd
    from wuwei.guards import agent_launch
    root, host, runtime = seat
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 1024)
    (ref, episode), = shepherd.pending(root)
    assert shepherd.headless(root, ref, episode, runtime=runtime) == 1
    assert [call[0] for call in runtime.calls] == ['dispatch']
    finished, = kinds(root, 'shepherd.finished')
    assert finished['payload']['exit'] == 1 and 'below floor' in finished['payload']['reason']
    assert shepherd.pending(root) == []


def test_unlinked_pr_is_not_started(seat):
    from wuwei import shepherd
    root, host, runtime = seat
    state._write_state(lambda data: data['items']['A'].update(pr=None), root, reserved=False)
    (ref, episode), = shepherd.pending(root)
    assert shepherd.headless(root, ref, episode, runtime=runtime) == 2
    assert not briefs(root) and not runtime.calls
    assert 'exactly one linked item' in kinds(root, 'shepherd.finished')[0]['payload']['reason']


@pytest.mark.parametrize('name,command', [('ci_red', 'wuwei pr act {ref};'),
                                          ('threads_unanswered', '--reply'),
                                          ('review_stale', 're-requests review')])
def test_headless_briefs_name_their_commands(name, command):
    from wuwei import shepherd
    assert command.format(ref=REF) in shepherd.HEADLESS[name].format(ref=REF)
    assert 'approved' not in shepherd.HEADLESS


def test_listener_dispatches_once_and_the_planner_sees_it(seat, monkeypatch):
    root, host, runtime = seat
    config(root, PR_CONFIG + '[shepherd]\nautostart = true\n')
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, settings: runtime if kind == 'runtime' else load(kind, settings))
    assert main(['plan', 'session', 'planner']) == 0
    assert listen().tick(root, {}) == 0
    later(monkeypatch, 30)
    assert listen().tick(root, {}) == 0
    assert len(kinds(root, 'shepherd.dispatched')) == 1
    assert [call[0] for call in runtime.calls] == ['dispatch', 'headless']
    assert state.read_state(root)['sessions'][SID]['role'] == 'shepherd'
    code, message = lifecycle.stop({'cwd': str(root), 'session_id': 'planner'})
    assert code == 1 and f'PR {REF}: shepherd conflicted: turn ended' in message


@pytest.mark.parametrize('text', ['', '[shepherd]\nautostart = true\n[responder]\nenabled = false\n'])
def test_listener_dispatches_nothing_when_off(seat, monkeypatch, text):
    root, host, runtime = seat
    config(root, PR_CONFIG + text)
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, settings: runtime if kind == 'runtime' else load(kind, settings))
    assert listen().tick(root, {}) == 0
    assert not runtime.calls and not briefs(root) and not kinds(root, 'shepherd.dispatched')
