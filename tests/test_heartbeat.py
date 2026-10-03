"""The watch heartbeat: probes in process through a faked adapter, then through the real launcher."""

import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import time

import pytest

from fakes.host import Fake as Host
from wuwei import heartbeat, integrity, registry, state, watch, workspace
from wuwei.__main__ import main
from wuwei.registry import Result

BEAT = heartbeat.beat  # the real one; tests/conftest.py replaces it for every other test
ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:00:00+00:00'
OK = [(0, '', 40), (2, 'refused', 60), (0, '', 50), (2, 'refused', 45), (0, '', 50)]  # status, refused, allowed, state_write, read_loop


class Service:
    def __init__(self, results=None):
        self.results, self.calls, self.pings = list(results or OK), [], []
        self.error = self.ping_error = None

    def probe(self, calls, cwd, during=lambda: None, timeout=10):
        self.calls.append((calls, cwd))
        if self.error:
            raise self.error
        return self.results, during()

    def ping(self, url, timeout=5):
        self.pings.append(url)
        if self.ping_error:
            raise self.ping_error


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from fakes.integrity import seed
    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    (plugin / 'x.py').write_text('x = 1\n')
    os.utime(plugin / 'x.py', (1_000_000, 1_000_000))
    monkeypatch.setattr(integrity, 'PLUGIN', plugin)
    seed(root)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    host = Host()
    previous = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'host' else previous(kind, config))
    service = Service()
    monkeypatch.setattr(registry, 'watch_service', lambda: service)
    return root, service, host, monkeypatch


def config(root, text):
    (root / '.wuwei/config.toml').write_text(text)


def events(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_measure_every_probe_ok(ws):
    root, service, _, _ = ws
    probes = heartbeat.measure(root)
    assert list(probes) == [name for name, _ in heartbeat.PROBES]
    assert all(row['result'] == 'ok' for row in probes.values()), probes
    assert [probes[name]['value'] for name in ('refused', 'allowed', 'state_write')] == ['exit 2', 'exit 0', 'exit 2']
    assert probes['status_line']['value'] == '40 ms'
    assert probes['state']['value'].endswith(' ms')
    assert probes['memory']['value'] == '8192 MiB'
    assert probes['planner']['value'] == 'no planner'
    (calls, cwd), = service.calls
    assert cwd == root / '.wuwei'
    assert [argv for argv, _ in calls] == [('status', '--line')] + [('hook', 'PreToolUse')] * 4
    payloads = [json.loads(text) for _, text in calls[1:]]
    assert {p['session_id'] for p in payloads} == {'wuwei-heartbeat'}
    assert {p['cwd'] for p in payloads} == {str(root / '.wuwei')}
    assert [p['tool_input'].get('command') for p in payloads[:2]] == ['git push --force origin main', 'ls -la']
    assert payloads[2]['tool_name'] == 'Write'
    assert payloads[2]['tool_input']['file_path'] == str(workspace.day_dir(root) / 'state.json')
    assert payloads[3]['tool_input']['command'] == heartbeat.READ_LOOP


@pytest.mark.parametrize('index, result, probe, expected', [
    (1, (0, '', 50), 'refused', ('failed', 'exit 0')),
    (2, (2, 'git: refused', 50), 'allowed', ('failed', 'exit 2: git: refused')),
    (3, (None, 'timeout', 10000), 'state_write', ('unmeasured', 'timeout')),
    (4, (2, 'refused', 50), 'read_loop', ('failed', 'exit 2: refused')),
    (0, (0, '', heartbeat.STATUS_LINE_BUDGET_MS + 1), 'status_line',
     ('failed', f'{heartbeat.STATUS_LINE_BUDGET_MS + 1} ms over {heartbeat.STATUS_LINE_BUDGET_MS} ms')),
    (0, (2, 'boom', 40), 'status_line', ('failed', 'exit 2: boom')),
])
def test_launcher_probe_outcomes(ws, index, result, probe, expected):
    root, service, _, _ = ws
    service.results[index] = result
    row = heartbeat.measure(root)[probe]
    assert (row['result'], row['value']) == expected


def test_adapter_failure_leaves_in_process_probes_measured(ws):
    root, service, _, _ = ws
    service.error = OSError('no launcher')
    probes = heartbeat.measure(root)
    for name in ('refused', 'allowed', 'state_write', 'status_line', 'read_loop'):
        assert probes[name] == {'result': 'unmeasured', 'value': 'no launcher'}
    assert probes['state']['result'] == probes['memory']['result'] == 'ok'


def test_stuck_state_lock_fails_the_state_probe(ws):
    root = ws[0]
    directory = workspace.day_dir(root)
    directory.mkdir(parents=True)
    with (directory / 'state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        start = time.monotonic()
        row = heartbeat.measure(root)['state']
    assert time.monotonic() - start < 3
    assert row['result'] == 'failed' and 'state.lock' in row['value']


def test_tampered_plugin_fails_integrity(ws):
    root = ws[0]
    later = time.time() + 10
    os.utime(integrity.PLUGIN / 'x.py', (later, later))
    row = heartbeat.measure(root)['integrity']
    assert row['result'] == 'failed' and 'x.py' in row['value']


def test_missing_credential_fails_config(ws):
    root, _, _, monkeypatch = ws
    monkeypatch.delenv('LINEAR_API_KEY', raising=False)
    config(root, '[adapters]\ntracker = "linear"\n')
    assert heartbeat.measure(root)['config'] == {'result': 'failed', 'value': 'missing LINEAR_API_KEY'}


def test_dead_listener_fails_clocks(ws):
    root = ws[0]
    state.append_event('listen: clock', {}, root)
    row = heartbeat.measure(root)['clocks']
    assert row['result'] == 'ok' and row['value'] == 'watch off, listen alive'
    ws[3].setenv('WUWEI_NOW', '2026-09-28T13:00:00+00:00')
    row = heartbeat.measure(root)['clocks']
    assert row['result'] == 'failed' and 'listen dead' in row['value']


def test_planner_probe(ws):
    from wuwei import plan
    root, _, _, monkeypatch = ws
    plan.session('planner-1', root)
    assert heartbeat.measure(root)['planner'] == {'result': 'ok', 'value': 'idle 0s'}
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T14:00:00+00:00')
    assert heartbeat.measure(root)['planner'] == {'result': 'failed', 'value': 'idle 7200s'}


def test_memory_probe(ws):
    root, _, host, _ = ws
    host.results['free_memory'] = Result(0, 512 * 2**20)
    assert heartbeat.measure(root)['memory'] == {'result': 'failed', 'value': '512 MiB'}
    config(root, '[adapters]\nhost = "none"\n')
    before = len(events(root))
    assert heartbeat.measure(root)['memory'] == {'result': 'unmeasured', 'value': 'host adapter none'}
    assert not any(row['kind'] == 'adapter: none' for row in events(root)[before:])


@pytest.mark.parametrize('results, expected', [
    (['ok', 'ok'], 'ok'), (['ok', 'unmeasured'], 'unmeasured'),
    (['unmeasured', 'failed'], 'degraded'), (['failed', 'ok'], 'degraded'),
])
def test_health(results, expected):
    probes = {str(index): {'result': result, 'value': ''} for index, result in enumerate(results)}
    assert heartbeat.health(probes) == expected


def beats(root, monkeypatch):
    monkeypatch.setattr(heartbeat, 'beat', BEAT)
    return heartbeat.beat(root)


def test_beat_records_one_heartbeat(ws, capsys):
    root, _, _, monkeypatch = ws
    assert beats(root, monkeypatch) == 0
    rows = [row for row in events(root) if row['kind'] == 'heartbeat: clock']
    assert len(rows) == 1
    record = watch.saved(root)['heartbeat']
    assert {key: rows[0]['payload'][key] for key in record} == record
    assert record['health'] == 'ok' and record['drift'] == [] and record['page'] == ''
    assert record['ping'] == 'off'
    assert list(record['probes']) == [name for name, _ in heartbeat.PROBES]


@pytest.mark.parametrize('result, code', [((0, '', 50), 1), ((None, 'timeout', 10000), 2)])
def test_beat_code_follows_health(ws, result, code):
    root, service, _, monkeypatch = ws
    service.results[1] = result
    assert beats(root, monkeypatch) == code


def test_flip_from_ok_is_behaviour_drift(ws, capsys):
    root, service, _, monkeypatch = ws
    beats(root, monkeypatch)
    service.results[1] = (0, '', 50)
    assert beats(root, monkeypatch) == 1
    record = watch.saved(root)['heartbeat']
    assert record['drift'] == ['refused']
    assert record['page'] == 'behaviour drift: heartbeat refused failed: exit 0'
    assert 'heartbeat: behaviour drift: refused' in capsys.readouterr().out


def test_failure_without_prior_ok_names_the_first_failed_probe(ws):
    root, service, host, monkeypatch = ws
    host.results['free_memory'] = Result(0, 0)
    service.results[2] = (2, 'refused', 50)
    beats(root, monkeypatch)
    record = watch.saved(root)['heartbeat']
    assert record['drift'] == []
    assert record['page'] == 'heartbeat allowed failed: exit 2: refused'


def test_beat_never_raises(ws, capsys):
    root, _, _, monkeypatch = ws
    monkeypatch.setattr(heartbeat, 'measure', lambda root: (_ for _ in ()).throw(ValueError('broken')))
    assert beats(root, monkeypatch) == 2
    assert 'heartbeat unmeasured: broken' in capsys.readouterr().out


SECRET = 'https://hc.example.test/ping/SECRET-TOKEN?k=QUERYVALUE'


def test_ping_only_when_healthy(ws):
    root, service, _, monkeypatch = ws
    config(root, f'[watch]\nping_url = "{SECRET}"\n')
    beats(root, monkeypatch)
    assert service.pings == [SECRET]
    assert watch.saved(root)['heartbeat']['ping'] == 'sent'
    service.results[1] = (0, '', 50)
    beats(root, monkeypatch)
    service.results[1] = (None, 'timeout', 10000)
    beats(root, monkeypatch)
    assert service.pings == [SECRET]
    assert watch.saved(root)['heartbeat']['ping'] == 'withheld'


def test_ping_failure_is_logged_by_host_only(ws, capsys):
    root, service, _, monkeypatch = ws
    config(root, f'[watch]\nping_url = "{SECRET}"\n')
    service.ping_error = OSError('refused ' + SECRET)
    assert beats(root, monkeypatch) == 0
    assert watch.saved(root)['heartbeat']['ping'] == 'failed'
    out = capsys.readouterr().out
    assert 'heartbeat ping failed: hc.example.test: OSError' in out
    directory = workspace.day_dir(root)
    for text in (out, (directory / 'events.jsonl').read_text(), (directory / 'state.json').read_text()):
        assert 'SECRET-TOKEN' not in text and 'QUERYVALUE' not in text


def test_watch_tick_runs_the_heartbeat_after_the_clock(ws):
    from wuwei import merge
    root, service, _, monkeypatch = ws
    for module, name in ((watch, 'poll'), (watch, 'pending_discovery'), (merge, 'poll')):
        monkeypatch.setattr(module, name, lambda root: 0)
    monkeypatch.setattr(watch, 'sweep', lambda root, watch_health=None: 0)
    monkeypatch.setattr(heartbeat, 'beat', BEAT)
    service.results[1] = (0, '', 50)
    assert watch.tick(root) == 1
    kinds = [row['kind'] for row in events(root) if row['kind'].endswith(': clock')]
    assert kinds == ['watch: clock', 'heartbeat: clock']
    assert len(service.calls) == 1


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    """A copied plugin driven through its real bin/wuwei; only the ping is faked."""
    from fakes.integrity import seed
    from types import SimpleNamespace

    def build(mutate=False):
        plugin = tmp_path / 'plugin'
        for directory in ('cli', 'bin', '.claude-plugin', 'adapters'):
            shutil.copytree(ROOT / directory, plugin / directory,
                            ignore=shutil.ignore_patterns('__pycache__'))
        if mutate:  # the mutation harness: the hook discovers no guards, so it allows everything
            with (plugin / 'cli/wuwei/commands/hook.py').open('a') as stream:
                stream.write('\ndiscover = lambda: []\n')
        path = tmp_path / 'path'
        path.mkdir()
        (path / 'python3').symlink_to(sys.executable)
        monkeypatch.setenv('PATH', str(path) + os.pathsep + os.environ['PATH'])
        root = tmp_path / 'ws'
        (root / '.wuwei').mkdir(parents=True)
        (root / '.wuwei/config.toml').write_text(
            '[host]\nfree_memory_mb = 0\n[watch]\nping_url = "https://hc.example.test/ping"\n')
        monkeypatch.setattr(integrity, 'PLUGIN', plugin)
        seed(root)
        monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
        monkeypatch.setenv('WUWEI_NOW', NOW)
        monkeypatch.setattr(heartbeat, 'STATUS_LINE_BUDGET_MS', 10000)  # a slow runner; the budget has its own test
        module = registry.watch_service()
        module.LAUNCHER = plugin / 'bin/wuwei'
        pings = []
        monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(probe=module.probe, ping=pings.append))
        monkeypatch.setattr(heartbeat, 'beat', BEAT)
        state.append_event('note', {'detail': 'start'}, root)
        return root, plugin, pings
    return build


def test_healthy_workspace_through_the_real_launcher(launcher, capsys):
    root, _, pings = launcher()
    before = (workspace.day_dir(root) / 'events.jsonl').read_bytes()
    assert main(['heartbeat']) == 0, capsys.readouterr()
    out = capsys.readouterr().out.splitlines()
    assert [line.split(':')[0] for line in out] == [name for name, _ in heartbeat.PROBES]
    assert all(line.split()[1] == 'ok' for line in out), out
    assert (workspace.day_dir(root) / 'events.jsonl').read_bytes() == before
    assert not (workspace.day_dir(root) / 'state.json').exists()
    assert pings == []


def test_tampered_plugin_pages_once_and_withholds_the_ping(launcher, capsys):
    from fakes.integrity import seed
    from wuwei.commands import status
    root, plugin, pings = launcher()
    assert heartbeat.beat(root) == 0, capsys.readouterr().out
    assert len(pings) == 1
    later = time.time() + 10
    os.utime(plugin / 'cli/wuwei/heartbeat.py', (later, later))
    assert heartbeat.beat(root) == 1
    record = watch.saved(root)['heartbeat']
    assert record['probes']['integrity']['result'] == 'failed'
    assert 'cli/wuwei/heartbeat.py' in record['probes']['integrity']['value']
    state.append_event('watch: clock', {}, root)
    directory = workspace.day_dir(root)
    line = status.line(status.snapshot(directory))
    assert 'health degraded' in line and 'pages 1' in line
    pages = [row for row in status.attention(directory) if row['source'] == 'heartbeat']
    assert len(pages) == 1 and 'integrity' in pages[0]['reason']
    assert len(pings) == 1
    seed(root)
    os.utime(root / '.wuwei/integrity/verdict.json', (later + 10, later + 10))
    assert heartbeat.beat(root) == 0
    assert 'health ok' in status.line(status.snapshot(directory))
    assert not [row for row in status.attention(directory) if row['source'] == 'heartbeat']


def test_allow_all_guard_fails_the_refused_probe(launcher, capsys):
    root, _, pings = launcher(mutate=True)
    assert heartbeat.beat(root) == 1
    record = watch.saved(root)['heartbeat']
    assert record['probes']['refused'] == {'result': 'failed', 'value': 'exit 0'}
    assert record['probes']['state_write']['result'] == 'failed'
    assert record['page'] == 'heartbeat refused failed: exit 0'
    assert pings == []


@pytest.mark.parametrize('index, result, code', [(None, None, 0), (1, (0, '', 50), 1), (1, (None, 'timeout', 1), 2)])
def test_heartbeat_command(ws, capsys, index, result, code):
    root, service, _, _ = ws
    if index is not None:
        service.results[index] = result
    assert main(['heartbeat']) == code
    out = capsys.readouterr().out.splitlines()
    assert [line.split(':')[0] for line in out] == [name for name, _ in heartbeat.PROBES]
    assert out[3].startswith('state: ok ') and out[-1] == 'memory: ok 8192 MiB'
    assert not (workspace.day_dir(root) / 'state.json').exists()
    assert events(root) == []
    assert service.pings == []


def test_heartbeat_command_outside_a_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(['heartbeat']) == 2
    assert 'wuwei heartbeat:' in capsys.readouterr().err
