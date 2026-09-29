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
    (tmp_path / '.wuwei/config.toml').write_text('')
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
    state.append_event('watch: sweep', {'owed': 1, 'unreadable': 0, 'exit': 1}, root)
    state.append_event('decision.one_way', {'blocking': False}, root)
    state.append_event('work.outside_goals', {}, root)
    assert main(['nudges']) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 3
    assert {row['source'] for row in rows} == {'watch: sweep', 'decision.one_way', 'work.outside_goals'}
    from wuwei.commands.status import snapshot
    assert snapshot(workspace.day_dir(root))['nudges'] == len(rows)
    state.append_event('watch: sweep', {'owed': 0, 'unreadable': 0, 'exit': 0}, root)
    assert main(['nudges']) == 0
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
    state.append_event('pr.action', {'pr': 'x/y#1', 'tier': 'nudge'}, root)
    state.append_event('mcp.finding', {'severity': 'medium'}, root)
    assert len(attention(day)) == 2
    state.append_event('pr.action', {'pr': 'x/y#1'}, root)
    state.append_event('mcp.checked', {'exit': 0}, root)
    assert attention(day) == []


def test_three_sweep_obligations_make_three_nudges(root):
    from wuwei.commands.status import attention, snapshot
    day = workspace.day_dir(root)
    state.append_event('watch: sweep', {'reply_owed': 3, 'visibility_owed': 0,
        'stale_owed': 0, 'watch_dead': 0, 'scanner_owed': 0,
        'integrity_owed': 0, 'unreadable': 0, 'owed': 3, 'exit': 1}, root)
    assert len(attention(day)) == snapshot(day)['nudges'] == 3
    assert all(row['source'] == 'watch: sweep:reply' for row in attention(day))


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
    assert main(['watch', 'uninstall']) == 2
    assert 'service denied' in capsys.readouterr().err
    assert unit.exists()


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
