"""Operator regressions for quiet sweeps and open attention."""

import json
from pathlib import Path
from datetime import timedelta

import pytest

from wuwei import registry, scanner, state, watch, workspace
from wuwei.__main__ import main


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[nudges]\nmode = "all"\n')  # #742: the raw classification
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    state._write_state(lambda data: None, tmp_path, reserved=False)
    return tmp_path


def test_none_scanner_with_traces_is_quiet(root, capsys):
    day = workspace.day_dir(root)
    (day / 'traces.jsonl').write_text('{}\n')
    config = workspace.load_config(root)
    assert scanner.trace_sweep(root, config) == {
        'scanner': 'not configured', 'scanner_owed': 0, 'unreadable': 0}
    state.append_event('watch: sweep', {'scanner': 'not configured'}, root)
    assert scanner.trace_sweep(root, config)['unreadable'] == 0
    assert capsys.readouterr().out.count('not configured') <= 1


def test_watch_dead_seconds_is_configurable(root, monkeypatch):
    (root / '.wuwei/config.toml').write_text('[watch]\ndead_seconds=30\n')
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=31)).isoformat())
    assert watch.health(root)[0] == 1


def test_nudges_show_current_conditions(root, capsys):
    state.append_event('watch: clock', {}, root)
    state.append_event('watch: sweep', {'owed': 1, 'unreadable': 0, 'exit': 1}, root)
    state.append_event('decision.one_way', {'blocking': False}, root)
    state.append_event('work.outside_goals', {}, root)
    assert main(['nudges', '--json']) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 3
    assert {row['source'] for row in rows} == {'watch: sweep', 'decision.one_way', 'work.outside_goals'}
    from wuwei.commands.status import snapshot
    assert snapshot(workspace.day_dir(root))['nudges'] == len(rows)
    state.append_event('watch: sweep', {'owed': 0, 'unreadable': 0, 'exit': 0}, root)
    assert main(['nudges', '--json']) == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_discovery_explains_unavailable_sources(root):
    from wuwei import discovery
    found = discovery.discover(root)
    assert all(value != 'unmeasured' for value in found['sources'].values())
    assert 'not configured' in found['sources']['scanner']
    assert 'not configured' in found['sources']['tracker']


def test_sweep_with_none_scanner_and_no_live_watch_is_finding(root, monkeypatch):
    from fakes.integrity import measured
    measured(monkeypatch)
    day = workspace.day_dir(root)
    (day / 'traces.jsonl').write_text('{}\n')
    monkeypatch.setattr(watch, 'activity', lambda _root: (0, {'stale': [], 'unreadable': 0}))
    monkeypatch.setattr('wuwei.dispatch.discovery', lambda *args: None)
    monkeypatch.setattr('wuwei.steward.run', lambda *args, **kwargs: 0)
    assert watch.sweep(root, watch_health=(0, '')) == 0
    row = json.loads((day / 'events.jsonl').read_text().splitlines()[-1])
    assert row['payload']['scanner'] == 'not configured'
    assert row['payload']['unreadable'] == 0


def test_repeated_sweep_does_not_launch_duplicate_steward(root, monkeypatch):
    from fakes.integrity import measured
    measured(monkeypatch)
    monkeypatch.setattr(watch, 'activity', lambda _root: (0, {'stale': [], 'unreadable': 0}))
    monkeypatch.setattr('wuwei.dispatch.discovery', lambda *args: None)
    calls = []
    monkeypatch.setattr('wuwei.steward.run', lambda *args, **kwargs: calls.append(1) or 0)
    state.append_event('watch: clock', {}, root)
    watch.sweep(root)
    watch.sweep(root)
    assert len(calls) == 1


def test_watch_install_uninstall_renders_and_loads(root, tmp_path, monkeypatch):
    from wuwei.commands import watch as watch_command
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(
        call=lambda argv: calls.append(argv)))
    monkeypatch.setattr(watch_command, 'service_platform', lambda: 'linux')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    search_path = f'{tmp_path / "tools"}:{tmp_path / "bin"}'
    monkeypatch.setenv('PATH', search_path)
    assert main(['watch', 'install']) == 0
    unit, = (tmp_path / 'config/systemd/user').glob('wuwei-*.service')
    content = unit.read_text()
    assert f'WorkingDirectory={root}\n' in content and search_path in content
    assert any(argv[:3] == ['systemctl', '--user', 'enable'] for argv in calls)
    assert main(['watch', 'uninstall']) == 0
    assert not unit.exists()
    assert any(argv[:3] == ['systemctl', '--user', 'disable'] for argv in calls)


def test_nudges_clear_pr_action_and_mcp_finding(root):
    from wuwei.commands.status import attention
    day = workspace.day_dir(root)
    state.append_event('watch: clock', {}, root)
    state.append_event('pr.action', {'pr': 'x/y#1', 'tier': 'nudge'}, root)
    state.append_event('mcp.finding', {'severity': 'medium'}, root)
    assert len(attention(day)) == 2
    state.append_event('pr.action', {'pr': 'x/y#1'}, root)
    state.append_event('mcp.checked', {'exit': 0}, root)
    assert attention(day) == []


def test_draft_nudges_clear_when_draft_is_decided(root):
    from wuwei.commands.status import attention
    day = workspace.day_dir(root)
    for ident in ('d1', 'd2'):
        state.append_event('draft.created', {'id': ident, 'channel': 'chat'}, root)
    assert len(attention(day)) == 2
    state.append_event('draft.sent', {'id': 'd1'}, root)
    state.append_event('draft.dropped', {'id': 'd2'}, root)
    assert attention(day) == []
    state.append_event('draft.created', {'id': 'd3', 'channel': 'chat'}, root)
    state.append_event('draft.failed', {'id': 'd3'}, root)
    assert [row['source'] for row in attention(day)] == ['draft.failed']


def test_merge_policy_nudge_is_per_pr_and_clears_on_merge(root):
    from wuwei.commands.status import attention
    day = workspace.day_dir(root)
    for _ in range(2):
        state.append_event('merge.policy_blocked', {'pr': 'x/y#1'}, root)
    assert len(attention(day)) == 1
    state.append_event('pr.action', {'pr': 'x/y#1', 'tier': 'silent', 'state': 'approved'}, root)
    assert len(attention(day)) == 1
    state.append_event('pr.action', {'pr': 'x/y#1', 'tier': 'silent', 'state': 'merged'}, root)
    assert attention(day) == []


def test_three_sweep_obligations_make_three_nudges(root):
    from wuwei.commands.status import attention, snapshot
    day = workspace.day_dir(root)
    state.append_event('watch: clock', {}, root)
    state.append_event('watch: sweep', {'reply_owed': 3, 'visibility_owed': 0,
        'stale_owed': 0, 'watch_dead': 0, 'scanner_owed': 0,
        'integrity_owed': 0, 'unreadable': 0, 'owed': 3, 'exit': 1}, root)
    assert len(attention(day)) == snapshot(day)['nudges'] == 3
    assert all(row['source'] == 'watch: sweep:reply' for row in attention(day))


@pytest.mark.parametrize('counts,expected', [
    ({'unreadable': 1, 'owed': 1, 'exit': 2}, [('unmeasured', 'watch: sweep:unmeasured')]),
    ({'unreadable': 0, 'owed': 0, 'exit': 0}, []),
    ({'unreadable': 'x', 'owed': 1, 'exit': 2}, [('watch: sweep', 'watch: sweep')]),
])
def test_obligations_sweep_is_itemised_by_source(root, counts, expected):
    from wuwei.commands.status import attention
    state.append_event('watch: clock', {}, root)
    state.append_event('watch: sweep', {'reply_owed': 0, 'visibility_owed': 0,
                                        'integrity_owed': 0, **counts}, root)
    rows = attention(workspace.day_dir(root))
    assert [(row['reason'], row['source']) for row in rows] == expected


def test_mac_watch_installer_escapes_values_and_reports_service_failure(root, monkeypatch, capsys):
    from wuwei.commands import watch as watch_command
    from types import SimpleNamespace
    monkeypatch.setattr(watch_command, 'service_platform', lambda: 'darwin')
    search_path = str(root / 'a&b')
    monkeypatch.setenv('PATH', search_path)
    calls = []
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(
        call=lambda argv: calls.append(argv)))
    assert main(['watch', 'install']) == 0
    unit, = (Path.home() / 'Library/LaunchAgents').glob('wuwei-*.plist')
    assert search_path.replace('&', '&amp;') in unit.read_text()
    assert calls[0][:2] == ['launchctl', 'bootstrap']
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(
        call=lambda argv: (_ for _ in ()).throw(OSError('service denied'))))
    capsys.readouterr()
    assert main(['watch', 'uninstall']) == 0
    assert 'warning: service denied' in capsys.readouterr().err
    assert not unit.exists()
    assert main(['watch', 'uninstall']) == 0


def service(monkeypatch, tmp_path, platform, fail=None):
    from wuwei.commands import watch as watch_command
    from types import SimpleNamespace
    calls = []

    def call(argv):
        calls.append(argv)
        if fail and argv[:len(fail)] == fail:
            raise OSError('load refused')
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(call=call))
    monkeypatch.setattr(watch_command, 'service_platform', lambda: platform)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    folder = (Path.home() / 'Library/LaunchAgents' if platform == 'darwin'
              else tmp_path / 'config/systemd/user')
    return calls, folder


@pytest.mark.parametrize('platform,argv', [('darwin', 'launchctl bootstrap'),
                                           ('linux', 'systemctl --user enable --now')])
def test_watch_install_dry_run_writes_and_calls_nothing(root, tmp_path, monkeypatch, capsys,
                                                        platform, argv):
    calls, folder = service(monkeypatch, tmp_path, platform)
    assert main(['watch', 'install', '--dry-run']) == 0
    out = capsys.readouterr().out
    assert f'unit: {folder}' in out and str(root) in out and f'$ {argv}' in out
    assert not calls and not folder.exists()


@pytest.mark.parametrize('platform,fail', [('darwin', ['launchctl', 'bootstrap']),
                                           ('linux', ['systemctl', '--user', 'enable'])])
def test_failed_watch_load_removes_unit_so_retry_works(root, tmp_path, monkeypatch, capsys,
                                                       platform, fail):
    calls, folder = service(monkeypatch, tmp_path, platform, fail)
    assert main(['watch', 'install']) == 2
    assert 'load refused' in capsys.readouterr().err
    assert not list(folder.glob('wuwei-*'))
    service(monkeypatch, tmp_path, platform)
    assert main(['watch', 'install']) == 0
    assert len(list(folder.glob('wuwei-*'))) == 1


def test_mac_watch_reinstall_refuses_before_overwriting_plist(root, monkeypatch, capsys):
    from wuwei.commands import watch as watch_command
    from types import SimpleNamespace

    monkeypatch.setattr(watch_command, 'service_platform', lambda: 'darwin')
    calls = []
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(
        call=lambda argv: calls.append(argv)))
    monkeypatch.setenv('PATH', '/first/bin')
    assert main(['watch', 'install']) == 0
    unit, = (Path.home() / 'Library/LaunchAgents').glob('wuwei-*.plist')
    original = unit.read_text()
    monkeypatch.setenv('PATH', '/second/bin')
    assert main(['watch', 'install']) == 2
    assert 'already installed' in capsys.readouterr().err
    assert unit.read_text() == original
    assert len(calls) == 1


def test_first_tick_sweep_sees_its_clock(root, monkeypatch):
    from fakes.integrity import measured

    measured(monkeypatch)
    monkeypatch.setattr(watch, 'poll', lambda _root: 0)
    monkeypatch.setattr('wuwei.merge.poll', lambda _root: 0)
    monkeypatch.setattr(watch, 'activity', lambda _root: (0, {'stale': [], 'unreadable': 0}))
    monkeypatch.setattr('wuwei.dispatch.discovery', lambda *args: None)
    monkeypatch.setattr('wuwei.steward.run', lambda *args, **kwargs: 0)
    watch.tick(root)
    row = next(row for row in (json.loads(line) for line in
               (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines())
               if row['kind'] == 'watch: sweep')
    assert row['payload']['watch_dead'] == 0


def test_next_sweep_reports_stale_watch_clock(root, monkeypatch):
    from fakes.integrity import measured
    measured(monkeypatch)
    (root / '.wuwei/config.toml').write_text('[watch]\ndead_seconds=30\n')
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=31)).isoformat())
    monkeypatch.setattr(watch, 'activity', lambda _root: (0, {'stale': [], 'unreadable': 0}))
    monkeypatch.setattr('wuwei.dispatch.discovery', lambda *args: None)
    monkeypatch.setattr('wuwei.steward.run', lambda *args, **kwargs: 0)
    assert watch.sweep(root) == 1
    row = json.loads((workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()[-1])
    assert row['payload']['watch_dead'] == 1


def test_nudges_on_a_workspace_without_day_state_lists_nothing(tmp_path, monkeypatch, capsys):
    import json
    from wuwei.__main__ import main
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    assert main(['nudges', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_watch_not_started_today_is_off(root, monkeypatch, capsys):
    from wuwei.commands.status import attention, snapshot
    day = workspace.day_dir(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    state._write_state(lambda data: None, root, reserved=False)
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    assert watch.health(root) == (0, 'watch off: no clock line today')
    assert attention(day) == [] and snapshot(day)['watch'] == 'off'
    assert main(['status']) == 0
    assert 'pages 0 · nudges 0\nwatch off' in capsys.readouterr().out
    assert main(['nudges', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_installed_watch_without_clock_today_is_dead_until_uninstalled(root, tmp_path, monkeypatch,
                                                                        capsys):
    import sys
    from wuwei.commands.status import attention, snapshot
    day = workspace.day_dir(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T23:50:00+00:00')
    state._write_state(lambda data: None, root, reserved=False)
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    service(monkeypatch, tmp_path, sys.platform)
    assert main(['watch', 'install']) == 0
    assert watch.health(root)[0] == 1
    assert [(row['source'], row['tier']) for row in attention(day)] == [('watch: health', 'page')]
    assert snapshot(day)['watch'] == 'dead'
    capsys.readouterr()
    assert main(['status']) == 0
    assert 'pages 1 · nudges 0\nwatch dead' in capsys.readouterr().out
    assert main(['nudges', '--json']) == 0
    assert [row['source'] for row in json.loads(capsys.readouterr().out)] == ['watch: health']
    assert main(['watch', 'uninstall']) == 0
    assert watch.health(root) == (0, 'watch off: no clock line today')
    assert attention(day) == [] and snapshot(day)['watch'] == 'off'


def test_installed_watch_with_fresh_clock_is_alive(root, tmp_path, monkeypatch):
    import sys
    from wuwei.commands.status import attention, snapshot
    service(monkeypatch, tmp_path, sys.platform)
    assert main(['watch', 'install']) == 0
    state.append_event('watch: clock', {}, root)
    assert watch.health(root) == (0, '')
    day = workspace.day_dir(root)
    assert attention(day) == [] and snapshot(day)['watch'] == 'alive'


def test_dead_watch_pages_until_a_fresh_clock(root, monkeypatch, capsys):
    from wuwei.commands.status import attention, snapshot
    day = workspace.day_dir(root)
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=1200)).isoformat())
    assert [row['source'] for row in attention(day)] == ['watch: health']
    assert attention(day)[0]['tier'] == 'page' and snapshot(day)['watch'] == 'dead'
    assert main(['status']) == 0
    assert 'pages 1 · nudges 0\nwatch dead' in capsys.readouterr().out
    assert main(['nudges', '--json']) == 0
    assert [row['source'] for row in json.loads(capsys.readouterr().out)] == ['watch: health']
    state.append_event('watch: sweep', {'reply_owed': 0, 'visibility_owed': 0, 'unreadable': 0,
                                        'owed': 0, 'exit': 0, 'integrity_owed': 0}, root)
    assert [row['source'] for row in attention(day)] == ['watch: health']
    state.append_event('watch: sweep', {'reply_owed': 0, 'visibility_owed': 0,
        'stale_owed': 0, 'watch_dead': 1, 'scanner_owed': 0,
        'integrity_owed': 0, 'unreadable': 0, 'owed': 1, 'exit': 1}, root)
    state.append_event('watch: clock', {}, root)
    assert attention(day) == [] and snapshot(day)['watch'] == 'alive'
    assert main(['status']) == 0
    assert 'watch alive' in capsys.readouterr().out


def test_future_clock_nudges_unmeasured_watch(root, monkeypatch, capsys):
    from wuwei.commands.status import attention, snapshot
    day = workspace.day_dir(root)
    state.append_event('watch: clock', {}, root)
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() - timedelta(minutes=5)).isoformat())
    rows = attention(day)
    assert [(row['source'], row['tier']) for row in rows] == [('watch: health', 'nudge')]
    assert snapshot(day)['watch'] == 'unmeasured'
    assert main(['status']) == 0
    assert 'watch unmeasured' in capsys.readouterr().out


@pytest.mark.parametrize('script,code', [
    ('bin/wuwei watch uninstall', 1),
    ('bin/wuwei listen uninstall', 1),
    ('python3 -P -m wuwei watch uninstall', 1),
    ('python3 -P -mwuwei watch uninstall', 1),
    ('sh -c "bin/wuwei watch uninstall"', 1),
    ('bin/wuwei watch -- uninstall', 1),
    ('bin/wuwei watch --dry-run -- uninstall', 1),
    ('bin/wuwei watch "$A"; echo uninstall', 2),
    ('bin/wuwei watch install; grep uninstall docs/', 0),
    ('bin/wuwei watch install --dry-run', 0),
    ('wuwei watch install --dry-run', 0),
    ('bin/wuwei watch --once', 0),
    ('grep uninstall docs/', 0),
    ('python3 -m pytest -q', 0),
    ('for x in a; do echo "$x"; done', 0),
    ('export X=1', 0),
])
def test_seat_cannot_uninstall_the_watch(root, script, code):
    from wuwei.guards.protect_state import check_bash
    result = check_bash({'cwd': str(root), 'tool_name': 'Bash', 'tool_input': {'command': script}})
    assert result[0] == code
    if code:
        assert ('uninstall in a host terminal' if code == 1 else 'host terminal') in result[1]


def test_watch_uninstall_outside_a_workspace_is_allowed(tmp_path, monkeypatch):
    from wuwei.guards.protect_state import check_bash
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check_bash({'cwd': str(tmp_path), 'tool_name': 'Bash',
                       'tool_input': {'command': 'bin/wuwei watch uninstall'}}) == (0, '')


def test_sweep_steward_waits_for_the_fix_round(root, monkeypatch):
    """#624: no sweep steward while an item is in fix; the next sweep after the round runs it."""
    from fakes.integrity import measured
    from test_next import day
    measured(monkeypatch)
    monkeypatch.setattr(watch, 'activity', lambda _root: (0, {'stale': [], 'unreadable': 0}))
    monkeypatch.setattr('wuwei.dispatch.discovery', lambda *args: None)
    calls = []
    monkeypatch.setattr('wuwei.steward.run', lambda *args, **kwargs: calls.append(kwargs) or 0)
    state.append_event('watch: clock', {}, root)
    day(root, items={'A': {'phase': 'fix', 'status': 'running'}})
    watch.sweep(root)
    assert calls == [] and watch.saved(root).get('steward_at') is None
    day(root, items={'A': {'phase': 'merged', 'status': 'done'}})
    watch.sweep(root)
    assert calls == [{'trigger': 'sweep'}]
