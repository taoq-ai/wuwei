"""Offline S3 registry contracts and launch refusal."""

import importlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from wuwei import registry, workspace


def finding(severity='high', drift='description_changed'):
    return dict(server_name='docs', drift_type=drift, severity=severity,
                tool_name='search', field='description', previous_value='PRIVATE OLD',
                current_value='UNTRUSTED NEW', suspected_canonical=None, message='PRIVATE MESSAGE')


@pytest.fixture
def source(tmp_path):
    path = tmp_path / '.mcp.json'
    path.write_text(json.dumps({'mcpServers': {'docs': {'command': 'fake-server',
        'env': {'TOKEN': 'PRIVATE TOKEN'}, 'headers': {'Authorization': 'PRIVATE HEADER'}}}}))
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    return path


@pytest.mark.parametrize('severity,code', [('high', 1), ('critical', 1), ('medium', 0), ('low', 0), (None, 0)])
def test_adapter_fixed_argv_and_metadata(source, monkeypatch, severity, code):
    ziran = importlib.import_module('adapters.scanner.ziran')
    servers = json.loads(source.read_text())
    servers['mcpServers'].update(one={'command': 'fake'}, two={'command': 'fake'})
    source.write_text(json.dumps(servers))
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['capture_output'] and kwargs['text'] and kwargs['timeout'] == 60
        if argv[1] == '--version':
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0')
        assert argv[:2] == ['ziran', 'watch-registry']
        assert argv[argv.index('--from-claude-config') + 1] == str(source)
        assert '--config' not in argv and argv[-2:] == ['--format', 'json']
        assert 'PRIVATE' not in ' '.join(argv)
        snapshots = Path(argv[argv.index('--snapshot-dir') + 1])
        assert snapshots.is_relative_to(source.parent / '.wuwei/ziran/snapshots')
        out = Path(argv[argv.index('--out') + 1])
        (out / 'registry-watch-report.json').write_text(json.dumps([finding(severity)] if severity else []))
        return SimpleNamespace(returncode=code, stdout='PRIVATE OUTPUT', stderr='PRIVATE ERROR')
    monkeypatch.setattr(ziran.subprocess, 'run', run)
    result = ziran.mcp([str(source)], root=source.parent)
    assert result.exit == code
    assert len(calls) == 2
    assert result.data['findings'] == ([{k: finding(severity)[k] for k in
        ('server_name', 'drift_type', 'severity', 'tool_name')}] if severity else [])
    assert 'PRIVATE' not in json.dumps(result.data) and 'UNTRUSTED' not in json.dumps(result.data)
    assert len(result.data['reports']) == 1
    assert not Path(result.data['reports'][0]).is_absolute()


def test_adapter_timeout_per_server_from_config(source, monkeypatch):
    ziran = importlib.import_module('adapters.scanner.ziran')
    (source.parent / '.wuwei/config.toml').write_text('[scanner.mcp]\ntimeout_seconds = 5\n')
    timeouts = []
    def run(argv, **kwargs):
        if argv[1] == '--version':
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0')
        timeouts.append(kwargs['timeout'])
        (Path(argv[argv.index('--out') + 1]) / 'registry-watch-report.json').write_text('[]')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(ziran.subprocess, 'run', run)
    assert ziran.mcp([source, source], root=source.parent).exit == 0
    assert timeouts == [5, 5]


@pytest.mark.parametrize('failure', ['missing-tool', 'timeout', 'json', 'error', 'missing-report',
    'invalid-row', 'severity', 'drift', 'exit', 'inconsistent', 'partial', 'invalid-config'])
def test_adapter_unmeasured(source, monkeypatch, capsys, failure):
    ziran = importlib.import_module('adapters.scanner.ziran')
    if failure == 'invalid-config':
        source.write_text('{')
    def run(argv, **kwargs):
        if failure == 'missing-tool':
            raise FileNotFoundError('PRIVATE')
        if argv[1] == '--version':
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(argv, 60)
        body = [finding()]
        if failure == 'error':
            body = {'error': 'PRIVATE'}
        if failure == 'invalid-row':
            body = [{}]
        if failure in ('severity', 'drift'):
            body[0]['severity' if failure == 'severity' else 'drift_type'] = 'PRIVATE'
        out = Path(argv[argv.index('--out') + 1])
        if failure != 'missing-report':
            (out / 'registry-watch-report.json').write_text('{' if failure == 'json' else json.dumps(body))
        return SimpleNamespace(returncode=3 if failure == 'exit' else 2 if failure == 'partial' else 0,
                               stdout='PRIVATE', stderr='PRIVATE')
    monkeypatch.setattr(ziran.subprocess, 'run', run)
    result = ziran.mcp([source], root=source.parent)
    assert result.exit == 2 and 'watch-registry: unmeasured' in result.reason
    assert 'PRIVATE' not in result.reason + capsys.readouterr().err


def test_adapter_separate_configs_and_precedence(source, monkeypatch):
    ziran = importlib.import_module('adapters.scanner.ziran')
    other = source.parent / 'plugin.json'
    other.write_text(source.read_text())
    snapshots, outputs = [], []
    def run(argv, **kwargs):
        if argv[1] == '--version':
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0')
        snapshots.append(argv[argv.index('--snapshot-dir') + 1])
        outputs.append(argv[argv.index('--out') + 1])
        (Path(outputs[-1]) / 'registry-watch-report.json').write_text(json.dumps([finding()]))
        return SimpleNamespace(returncode=1 if len(outputs) == 1 else 2, stdout='', stderr='')
    monkeypatch.setattr(ziran.subprocess, 'run', run)
    result = ziran.mcp([source, other], root=source.parent)
    assert result.exit == 2
    assert len(set(snapshots)) == len(set(outputs)) == 2
    assert len(result.data['findings']) == 2


def approve(root, *names, key=None):
    """Claude Code's per-project approval of .mcp.json servers, in the sandboxed user file."""
    user = Path.home() / '.claude.json'
    data = json.loads(user.read_text()) if user.exists() else {}
    data.setdefault('projects', {})[str(key or root)] = {'enabledMcpjsonServers': list(names)}
    user.write_text(json.dumps(data))


def exec_stub(tmp_path, monkeypatch):
    """A ZIRAN stub that starts stdio servers and connects to remote ones."""
    import os
    import sys
    executable = tmp_path / 'ziran'
    executable.write_text('#!' + sys.executable + '\n' + '''
import json
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import urlparse
if sys.argv[1] == '--version':
    print('ziran, version 0.39.0')
    raise SystemExit(0)
assert sys.argv[1] == 'watch-registry'
def arg(key):
    return Path(sys.argv[sys.argv.index(key) + 1])
servers = json.loads(arg('--from-claude-config').read_text())['mcpServers']
with (Path(__file__).parent / 'ziran-calls.jsonl').open('a') as calls:
    calls.write(json.dumps(sorted(servers)) + '\\n')
rows = []
for name, entry in servers.items():
    if 'url' in entry:
        url = urlparse(entry['url'])
        try:
            socket.create_connection((url.hostname, url.port), timeout=5).close()
        except OSError:
            raise SystemExit(2)
    else:
        subprocess.run([entry['command'], *entry.get('args', [])], timeout=5)
    (arg('--snapshot-dir') / (name + '.json')).write_text(json.dumps(entry))
    if entry.get('description') in ('critical', 'high', 'medium', 'low'):
        rows.append(dict(server_name=name, drift_type='tool_poisoning', severity=entry['description'],
                         tool_name='search', message='poisoned'))
(arg('--out') / 'registry-watch-report.json').write_text(json.dumps(rows))
raise SystemExit(int(any(row['severity'] in ('critical', 'high') for row in rows)))
''')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    return tmp_path / 'ziran-calls.jsonl'


@pytest.fixture
def configured(source, monkeypatch):
    root = source.parent
    (root / '.wuwei/config.toml').write_text('[adapters]\nscanner="ziran"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T08:00:00+02:00')
    approve(root, 'docs')
    return root


def core():
    return importlib.import_module('wuwei.mcp')


def fake_scanner(monkeypatch, code=0, rows=None):
    response = registry.Result(code, {'findings': rows or [], 'reports': []},
                               'scanner unavailable' if code == 2 else '')
    calls = []
    original = registry.load
    def mcp(servers, *, root):
        calls.append(servers)
        return response
    monkeypatch.setattr(registry, 'load', lambda kind, config:
        SimpleNamespace(mcp=mcp) if kind == 'scanner' else original(kind, config))
    return calls


def metadata(severity='high'):
    return {k: finding(severity)[k] for k in ('server_name', 'drift_type', 'severity', 'tool_name')}


def test_discovery_repo_plugin_user_defaults_and_overrides(configured):
    root = configured
    repo = root / 'repo'
    repo.mkdir()
    (repo / '.mcp.json').write_text((root / '.mcp.json').read_text())
    plugin = root / 'plugin'
    plugin.mkdir()
    (plugin / '.mcp.json').write_text(json.dumps({'docs': {'command': 'fake'}}))
    user = Path.home() / '.claude.json'
    user.write_text((root / '.mcp.json').read_text())
    installed = Path.home() / '.claude/plugins/installed_plugins.json'
    installed.parent.mkdir(parents=True)
    installed.write_text(json.dumps({'version': 2, 'plugins': {'example@market': [
        {'scope': 'user', 'installPath': str(plugin)},
        {'scope': 'project', 'projectPath': str(root / 'other'), 'installPath': 'missing'},
    ]}}))
    config_path = root / '.wuwei/config.toml'
    config_path.write_text('repos=[{name="example/repo",path="repo",default_branch="main"}]\n')
    assert set(core().discover(root, workspace.load_config(root))) == {
        root / '.mcp.json', repo / '.mcp.json', plugin / '.mcp.json', user}
    config_path.write_text('[scanner.mcp]\nuser_file="user.json"\nplugins_file="plugins.json"\nproject_file="custom.json"\n')
    (root / 'user.json').write_text('{"mcpServers":{}}')
    (root / 'plugins.json').write_text('{"version":2,"plugins":{}}')
    assert core().discover(root, workspace.load_config(root)) == []
    (root / 'user.json').unlink()
    with pytest.raises(OSError):
        core().discover(root, workspace.load_config(root))


@pytest.mark.parametrize('bad', ['{', '[]', '{"error":"PRIVATE"}', '{"mcpServers":[]}'])
def test_bad_config_fail_closed(configured, bad):
    (configured / '.mcp.json').write_text(bad)
    result = core().check(configured)
    assert result.exit == 2 and 'unmeasured' in result.reason
    assert 'PRIVATE' not in result.reason
    assert core().cached(configured).exit == 2


@pytest.mark.parametrize('upgrade', [False, True])
def test_init_registers_and_reports_poisoning(tmp_path, monkeypatch, upgrade, capsys):
    from wuwei.__main__ import main
    root = tmp_path / 'workspace'
    root.mkdir()
    (root / '.mcp.json').write_text('{"mcpServers":{"docs":{"command":"fake"}}}')
    approve(root, 'docs')
    rows = [{**metadata('critical'), 'drift_type': 'tool_poisoning'}]
    calls = fake_scanner(monkeypatch, 1, rows)
    if upgrade:
        (root / '.wuwei').mkdir()
        (root / '.wuwei/config.toml').write_text('')
    args = ['init', str(root), *(['--upgrade'] if upgrade else [])]
    assert main(args) == 1
    [[file]] = calls
    assert file.parent == root.resolve() / '.wuwei/ziran/servers'
    assert json.loads(file.read_text()) == {'mcpServers': {'docs': {'command': 'fake'}}}
    assert 'MCP' in capsys.readouterr().err
    assert core().cached(root).exit == 1
    assert list((root / '.wuwei/days').glob('*/decisions/D-*.md'))


@pytest.mark.parametrize('code', [0, 1, 2])
def test_morning_check_before_launch(configured, monkeypatch, code):
    from test_plan import proposal
    from wuwei import plan, state
    from wuwei.guards.agent_launch import check, check_mcp
    memory = configured / '.wuwei/memory'
    memory.mkdir()
    (memory / 'goals.md').write_text('# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    calls = fake_scanner(monkeypatch, code, [metadata('critical')] if code == 1 else [])
    if code == 1:
        with pytest.raises(state.StateError, match='MCP'):
            plan.propose(proposal(), configured)
    else:
        assert plan.propose(proposal(), configured).is_file()
    assert len(calls) == 1
    result = check({'cwd': str(configured), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build', 'prompt': 'no brief'}})
    assert result[0] == 1
    gate = check_mcp({'cwd': str(configured), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build', 'prompt': 'no brief'}})
    assert gate[0] == (1 if code == 1 else 0)
    if code == 1:
        assert 'MCP' in gate[1]
    assert not state.read_state(configured)['seats']


def test_sticky_findings_owner_confirmation_and_rollover(configured, monkeypatch):
    from wuwei import state
    fake_scanner(monkeypatch, 1, [metadata('critical')])
    assert core().check(configured).exit == 1
    pending = next((configured / '.wuwei/days').glob('*/decisions/D-*.md'))
    fake_scanner(monkeypatch, 0)
    assert core().check(configured).exit == 1
    pending.write_text(pending.read_text().replace('Outcome: pending', 'Outcome: proceed'))
    assert core().cached(configured).exit == 1  # Text alone cannot approve.
    assert core().decide(configured, confirm=lambda digest: False).exit == 1
    assert core().cached(configured).exit == 1
    assert core().decide(configured, confirm=lambda digest: True).exit == 0
    assert core().cached(configured).exit == 0
    events = (workspace.day_dir(configured) / 'events.jsonl').read_text()
    assert 'PRIVATE' not in events and 'UNTRUSTED' not in events
    rows = [json.loads(line) for line in events.splitlines()]
    assert next(row['payload'] for row in rows if row['kind'] == 'mcp.finding') == metadata('critical')
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('mcp', {'exit': 0}, configured)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T08:00:00+02:00')
    assert core().cached(configured).exit == 2
    assert core().check(configured).exit == 0


def test_unmeasured_cannot_be_owner_cleared(configured, monkeypatch):
    fake_scanner(monkeypatch, 1, [metadata()])
    core().check(configured)
    pending = next((configured / '.wuwei/days').glob('*/decisions/D-*.md'))
    pending.write_text(pending.read_text().replace('Outcome: pending', 'Outcome: proceed'))
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=lambda files, root: None))
    assert core().check(configured).exit == 2
    assert core().decide(configured, confirm=lambda digest: True).exit == 2
    fake_scanner(monkeypatch, 0)
    assert core().check(configured).exit == 1


@pytest.mark.parametrize('relative', ['ziran/status.json', 'ziran/snapshots/a.json', 'ziran/accepted.json'])
def test_protect_registry_evidence(configured, relative):
    from wuwei.guards import protect_state
    payload = {'cwd': str(configured), 'tool_name': 'Write', 'tool_input': {
        'file_path': str(configured / '.wuwei' / relative), 'content': '{}'}}
    assert protect_state.check_file(payload)[0] == 1
    payload['tool_input'] = {'command': f'echo clean > .wuwei/{relative}'}
    assert protect_state.check_bash(payload)[0] == 1


@pytest.mark.parametrize('command', ['bin/wuwei mcp decide', 'python3 -P -m wuwei mcp decide',
    'python3 -mwuwei mcp decide', 'bin/wuwei mcp decide proceed-unmeasured aws',
    'eval "bin/wuwei mcp decide"'])
def test_owner_command_not_available_to_seats(configured, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash({'cwd': str(configured), 'tool_input': {'command': command}})[0] == 1


@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'for x in 1; do echo "$x"; done', 'export X=1'])
def test_irrelevant_shell_is_allowed(configured, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash({'cwd': str(configured), 'tool_input': {'command': command}})[0] == 0


def test_scope_outside_workspace(configured, monkeypatch, tmp_path):
    from wuwei.guards.agent_launch import check
    outside = tmp_path / 'outside'
    outside.mkdir()
    # configured is tmp_path, so use a sibling through its temporary parent.
    monkeypatch.setenv('WUWEI_WORKSPACE', str(configured))
    monkeypatch.setattr(workspace, 'scope', lambda path: None)
    assert check({'cwd': str(outside), 'tool_input': {'subagent_type': 'wuwei:builder'}})[0] == 0


@pytest.mark.parametrize('runtime', ['claude', 'codex'])
def test_runtime_port_refuses_before_dispatch(configured, runtime):
    adapter = importlib.import_module('adapters.runtime.' + runtime)
    result = adapter.dispatch('builder', 'missing', str(configured), True, root=configured)
    assert result.exit == 2 and 'MCP' in result.reason
    result = adapter.continue_job({'id': 'job', 'worktree': str(configured)}, 'continue', root=configured)
    assert result.exit == 2 and 'MCP' in result.reason


def test_snapshot_recovery_after_timeout_preserves_drift(configured, monkeypatch):
    from wuwei import mcp
    snapshots = configured / '.wuwei/ziran/snapshots'
    snapshots.mkdir(parents=True)
    snapshot = snapshots / 'docs.json'
    snapshot.write_text('approved')
    def failed(files, *, root):
        snapshot.write_text('unapproved')
        return None  # The check could not run.
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=failed))
    assert mcp.check(configured).exit == 2
    def retry(files, *, root):
        assert snapshot.read_text() == 'approved'
        snapshot.write_text('unapproved')
        return registry.Result(1, {'findings': [metadata()], 'reports': []})
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=retry))
    assert mcp.check(configured).exit == 1
    assert snapshot.read_text() == 'unapproved'


def test_interrupted_scan_recovery_and_accumulated_pending(configured, monkeypatch):
    from wuwei import mcp
    snapshots = configured / '.wuwei/ziran/snapshots'
    snapshots.mkdir(parents=True)
    snapshot = snapshots / 'docs.json'
    snapshot.write_text('approved')
    def interrupted(files, *, root):
        snapshot.write_text('unapproved')
        raise KeyboardInterrupt()
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=interrupted))
    with pytest.raises(KeyboardInterrupt):
        mcp.check(configured)
    assert mcp.cached(configured).exit == 2
    for index in (1, 2):
        def scan(files, *, root):
            assert snapshot.read_text() == 'approved'
            return registry.Result(1, {'findings': [metadata()],
                'reports': [f'.wuwei/ziran/report-{index}/registry-watch-report.json']})
        monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=scan))
        assert mcp.check(configured).exit == 1
    last = sorted((workspace.day_dir(configured) / 'decisions').glob('D-*.md'))[-1].read_text()
    assert 'report-1/' in last and 'report-2/' in last


def test_empty_registry_does_not_create_day_or_mutate_on_upgrade(tmp_path):
    from wuwei import mcp
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    assert mcp.check(tmp_path).exit == 0
    assert not (tmp_path / '.wuwei/days').exists()
    before = {p: p.read_bytes() for p in (tmp_path / '.wuwei').rglob('*') if p.is_file()}
    assert mcp.check(tmp_path).exit == 0
    assert before == {p: p.read_bytes() for p in (tmp_path / '.wuwei').rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind,payload,tier', [('mcp.finding', {'severity': 'high'}, 'page'),
    ('mcp.finding', {'severity': 'medium'}, 'nudge'), ('mcp.checked', {'exit': 0}, 'silent'),
    ('mcp.checked', {'exit': 2}, 'nudge'), ('mcp.decided', {}, 'silent')])
def test_mcp_signal_tiers(kind, payload, tier):
    from wuwei.signal import classify
    assert classify({'kind': kind, 'payload': payload}, {})[0] == tier


def test_nonblocking_findings_visible_in_plan(configured, monkeypatch):
    from test_plan import proposal
    from wuwei import plan
    memory = configured / '.wuwei/memory'
    memory.mkdir()
    (memory / 'goals.md').write_text('# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    fake_scanner(monkeypatch, 0, [metadata('medium')])
    path = plan.propose(proposal(), configured)
    assert 'MCP registry measured: 1 findings' in path.read_text()


def test_server_level_finding_nullable_tool_name():
    ziran = importlib.import_module('adapters.scanner.ziran')
    assert ziran._mcp_report([{**finding(drift='typosquat'), 'tool_name': None}])[0]['tool_name'] is None


@pytest.mark.parametrize('command', ["bin/wuwei mcp $ACTION", "bin/wuwei mcp $'\\x64ecide'"])
def test_obfuscated_owner_action_fails_closed(configured, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash({'cwd': str(configured), 'tool_input': {'command': command}})[0] in (1, 2)


def test_scanner_event_failure_keeps_block_and_recovers(configured, monkeypatch):
    from wuwei import mcp, state
    snapshots = configured / '.wuwei/ziran/snapshots'
    snapshots.mkdir(parents=True)
    snapshot = snapshots / 'docs.json'
    snapshot.write_text('baseline')
    def scan(files, *, root):
        snapshot.write_text('changed')
        return registry.Result(1, {'findings': [metadata()], 'reports': []})
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=scan))
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise OSError('event unavailable')
        patch.setattr(state, 'append_event', fail)
        assert mcp.check(configured).exit == 2
    assert mcp.cached(configured).exit == 2
    def retry(files, *, root):
        assert snapshot.read_text() == 'baseline'
        return registry.Result(1, {'findings': [metadata()], 'reports': []})
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=retry))
    assert mcp.check(configured).exit == 1


def test_first_registration_interruption_discards_partial_snapshot(configured, monkeypatch):
    from wuwei import mcp
    snapshot = configured / '.wuwei/ziran/snapshots/docs.json'
    def interrupted(files, *, root):
        snapshot.parent.mkdir()
        snapshot.write_text('unreviewed baseline')
        raise KeyboardInterrupt()
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=interrupted))
    with pytest.raises(KeyboardInterrupt):
        mcp.check(configured)
    def retry(files, *, root):
        assert not snapshot.exists()
        return registry.Result(0, {'findings': [], 'reports': []})
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=retry))
    assert mcp.check(configured).exit == 0


def test_reserved_mcp_events_cannot_be_forged(configured, monkeypatch):
    from wuwei.__main__ import main
    monkeypatch.chdir(configured)
    for kind in ('mcp.finding', 'mcp.checked', 'mcp.decided'):
        assert main(['event', kind, '{"exit":0}']) == 1
    assert not workspace.day_dir(configured).exists()


def ziran_stub(tmp_path, monkeypatch):
    import os
    import sys
    executable = tmp_path / 'ziran'
    executable.write_text('#!' + sys.executable + '\n' + '''
import json
from pathlib import Path
import sys
if sys.argv[1] == '--version':
    print('ziran, version 0.39.0')
    raise SystemExit(0)
assert sys.argv[1] == 'watch-registry'
def arg(key):
    return Path(sys.argv[sys.argv.index(key) + 1])
config = json.loads(arg('--from-claude-config').read_text())
current = config['mcpServers']['docs']['description']
snapshot = arg('--snapshot-dir') / 'docs.json'
previous = snapshot.read_text() if snapshot.exists() else current
snapshot.write_text(current)
rows = [] if previous == current else [dict(server_name='docs', drift_type='description_changed',
    severity='high', tool_name='search', field='description', previous_value=previous,
    current_value=current, suspected_canonical=None, message='changed')]
(arg('--out') / 'registry-watch-report.json').write_text(json.dumps(rows))
raise SystemExit(int(bool(rows)))
''')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])


def test_path_stub_init_then_description_drift_before_morning_launch(tmp_path, monkeypatch):
    from test_plan import proposal
    from wuwei.__main__ import main
    from wuwei.guards.agent_launch import check
    root = tmp_path / 'workspace'
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T08:00:00+02:00')
    assert main(['init']) == 0
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('scanner = "none"', 'scanner = "ziran"').replace(
        'block = ["critical"]', 'block = ["high", "critical"]'))
    approve(root, 'docs')
    mcp_file = root / '.mcp.json'
    mcp_file.write_text('{"mcpServers":{"docs":{"command":"fake","description":"approved"}}}')
    ziran_stub(tmp_path, monkeypatch)
    assert main(['init', '--upgrade']) == 0
    snapshots = list((root / '.wuwei/ziran/snapshots').glob('*/docs.json'))
    assert len(snapshots) == 1 and snapshots[0].read_text() == 'approved'
    mcp_file.write_text(mcp_file.read_text().replace('approved', 'UNTRUSTED CHANGE'))
    goals = root / '.wuwei/memory/goals.md'
    goals.write_text('# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    source = root / 'lead.json'
    source.write_text(json.dumps(proposal()))
    assert main(['plan', 'propose', str(source)]) == 1
    assert check({'cwd': str(root), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build', 'prompt': 'no brief'}})[0] == 1
    assert 'UNTRUSTED CHANGE' not in (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert 'UNTRUSTED CHANGE' in next(p for p in (root / '.wuwei/ziran').glob('report-*/registry-watch-report.json')
        if 'UNTRUSTED CHANGE' in p.read_text()).read_text()


def test_interrupted_backup_cleanup_never_replays_partial_backup(configured, monkeypatch):
    from wuwei import mcp
    snapshots = configured / '.wuwei/ziran/snapshots'
    snapshots.mkdir(parents=True)
    snapshot = snapshots / 'docs.json'
    snapshot.write_text('approved')
    fake_scanner(monkeypatch, 2)
    remove = mcp.shutil.rmtree
    with monkeypatch.context() as patch:
        def interrupted(path, *args, **kwargs):
            if path.name == 'snapshot-backup':
                remove(path / 'snapshots')
                raise KeyboardInterrupt()
            return remove(path, *args, **kwargs)
        patch.setattr(mcp.shutil, 'rmtree', interrupted)
        with pytest.raises(KeyboardInterrupt):
            mcp.check(configured)
    assert snapshot.read_text() == 'approved'
    def scan(files, *, root):
        assert snapshot.read_text() == 'approved'
        return registry.Result(0, {'findings': [], 'reports': []})
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=scan))
    assert mcp.check(configured).exit == 0


@pytest.mark.parametrize('command', ['rg mcp cli', 'python3 -m pytest -k mcp', 'echo mcp',
    "rg 'wuwei mcp decide' cli", 'c{d,d} ..'])
def test_mcp_mentions_in_unrelated_commands_do_not_block(configured, command):
    from wuwei.guards.protect_state import check_bash
    assert check_bash({'cwd': str(configured), 'tool_input': {'command': command}})[0] == 0


COCKPIT = {'command': '${CLAUDE_PLUGIN_ROOT}/bin/wuwei', 'args': ['board'],
           'env': {'CLAUDE_PROJECT_DIR': '${CLAUDE_PROJECT_DIR}'}}


def own_workspace(tmp_path, monkeypatch, plugin, repo=None):
    root = tmp_path / 'root'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text(
        f'repos=[{{name="taoq-ai/wuwei",path={json.dumps(str(repo))},default_branch="main"}}]\n'
        if repo else '')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T08:00:00+02:00')
    installed = Path.home() / '.claude/plugins/installed_plugins.json'
    installed.parent.mkdir(parents=True)
    installed.write_text(json.dumps({'version': 2, 'plugins': {'wuwei@market': [
        {'scope': 'user', 'installPath': str(plugin)}]}}))
    return root


@pytest.mark.parametrize('scanner', ['none', 'ziran'])
def test_own_server_and_source_checkout_attach_no_discoverable_file(tmp_path, monkeypatch, scanner):
    # The cockpit is declared in the signed plugin.json, so neither the install nor a
    # managed checkout of the WUWEI source carries a project .mcp.json for S3 to measure.
    plugin = Path(__file__).resolve().parents[1]
    repo = tmp_path / 'repo'
    repo.mkdir()
    for path in plugin.iterdir():
        if path.is_file():
            (repo / path.name).write_bytes(path.read_bytes())
    root = own_workspace(tmp_path, monkeypatch, plugin, repo)
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write(f'[adapters]\nscanner="{scanner}"\n')
    assert core().discover(root, workspace.load_config(root)) == []
    assert core().cached(root).exit == 0
    result = core().check(root)
    assert result.exit == 0 and 'covered by plugin integrity' in result.reason


@pytest.mark.parametrize('where,server', [
    ('install', {**COCKPIT, 'args': ['board', '--evil']}),
    ('install', {**COCKPIT, 'command': '/bin/sh'}),
    ('install', COCKPIT),
    ('project', COCKPIT),
    ('project', {**COCKPIT, 'args': ['dashboard']}),
])
def test_cockpit_lookalike_file_stays_unmeasured_and_refused(tmp_path, monkeypatch, where, server):
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    root = own_workspace(tmp_path, monkeypatch, plugin)
    strict(root)
    monkeypatch.setattr(core(), 'PLUGIN', plugin, raising=False)
    path = (plugin if where == 'install' else root) / '.mcp.json'
    path.write_text(json.dumps({'mcpServers': {'cockpit': server}}))
    approve(root, 'cockpit')
    assert core().discover(root, workspace.load_config(root)) == [path]
    assert core().cached(root).exit == 2
    result = core().check(root)
    assert result.exit == 2 and 'unmeasured' in result.reason
    assert core().launch(root).exit == 2


def strict(root):
    """The pre-#325 posture: an unmeasured server refuses launches."""
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write('[scanner.mcp]\nblock = ["high", "critical", "unmeasured"]\n')


def inline_plugin(tmp_path, servers, name='other'):
    plugin = tmp_path / 'plugin'
    (plugin / '.claude-plugin').mkdir(parents=True)
    manifest = plugin / '.claude-plugin/plugin.json'
    manifest.write_text(json.dumps({'name': name, 'mcpServers': servers}))
    return plugin, manifest


def test_issue_acceptance_inline_plugin_server_registered_expanded_and_drift(tmp_path, monkeypatch):
    plugin, manifest = inline_plugin(tmp_path, {'docs': {
        'command': '${CLAUDE_PLUGIN_ROOT}/server', 'description': 'approved'}})
    root = own_workspace(tmp_path, monkeypatch, plugin)
    (root / '.wuwei/config.toml').write_text('[adapters]\nscanner="ziran"\n')
    ziran_stub(tmp_path, monkeypatch)
    assert core().discover(root, workspace.load_config(root)) == [manifest.resolve()]
    assert core().cached(root).exit == 2
    assert core().check(root).exit == 0
    [copy] = (root / '.wuwei/ziran/servers').glob('*.json')
    assert '${CLAUDE_PLUGIN_ROOT}' not in copy.read_text()
    assert json.loads(copy.read_text())['mcpServers']['docs']['command'] == str(plugin.resolve()) + '/server'
    [snapshot] = (root / '.wuwei/ziran/snapshots').glob('*/docs.json')
    assert snapshot.read_text() == 'approved'
    manifest.write_text(manifest.read_text().replace('approved', 'UNTRUSTED CHANGE'))
    assert core().check(root).exit == 1
    assert list((root / '.wuwei/ziran/snapshots').glob('*/docs.json')) == [snapshot]
    assert list((workspace.day_dir(root) / 'decisions').glob('D-*.md'))
    assert core().cached(root).exit == 0  # A high finding is a nudge under the default block.
    assert 'UNTRUSTED CHANGE' not in (workspace.day_dir(root) / 'events.jsonl').read_text()


@pytest.mark.parametrize('servers', ['./servers.json', ['./servers.json'], {'docs': 'fake'}])
def test_inline_plugin_servers_invalid_fail_closed(tmp_path, monkeypatch, servers):
    plugin, _ = inline_plugin(tmp_path, servers)
    root = own_workspace(tmp_path, monkeypatch, plugin)
    (root / '.wuwei/config.toml').write_text('[adapters]\nscanner="ziran"\n')
    result = core().check(root)
    assert result.exit == 2 and 'unmeasured' in result.reason
    assert core().cached(root).exit == 2


@pytest.mark.parametrize('server', [COCKPIT, {**COCKPIT, 'command': '/bin/sh'}])
def test_cockpit_lookalike_inline_in_another_plugin_is_measured(tmp_path, monkeypatch, server):
    plugin, manifest = inline_plugin(tmp_path, {'cockpit': server}, name='wuwei')
    root = own_workspace(tmp_path, monkeypatch, plugin)
    strict(root)
    assert core().discover(root, workspace.load_config(root)) == [manifest.resolve()]
    assert core().cached(root).exit == 2
    result = core().check(root)
    assert result.exit == 2 and 'unmeasured' in result.reason
    assert core().launch(root).exit == 2
    monkeypatch.setattr(core(), 'PLUGIN', plugin.resolve(), raising=False)
    assert core().discover(root, workspace.load_config(root)) == []
    assert 'covered by plugin integrity' in core().check(root).reason


def scanned(root, monkeypatch):
    """Files the configured scanner receives, measured clean."""
    seen = []
    scanner = SimpleNamespace(mcp=lambda files, root: seen.extend(files) or registry.Result(
        0, {'findings': [], 'reports': []}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: scanner)
    assert core().check(root).exit == 0
    return [json.loads(Path(f).read_text())['mcpServers'] for f in seen]


def test_symlinked_signed_manifest_in_another_plugin_is_measured(tmp_path, monkeypatch):
    # Coverage follows the install directory: a plugin whose plugin.json is a symlink to
    # WUWEI's signed manifest still runs its own ${CLAUDE_PLUGIN_ROOT}/bin/wuwei.
    plugin, signed = inline_plugin(tmp_path, {'cockpit': COCKPIT}, name='wuwei')
    evil = tmp_path / 'evil'
    (evil / '.claude-plugin').mkdir(parents=True)
    (evil / '.claude-plugin/plugin.json').symlink_to(signed)
    root = own_workspace(tmp_path, monkeypatch, evil)
    strict(root)
    monkeypatch.setattr(core(), 'PLUGIN', plugin.resolve(), raising=False)
    assert core().discover(root, workspace.load_config(root)) == [evil.resolve() / '.claude-plugin/plugin.json']
    result = core().check(root)
    assert result.exit == 2 and 'covered by plugin integrity' not in result.reason
    assert core().launch(root).exit == 2
    [servers] = scanned(root, monkeypatch)
    assert servers['cockpit']['command'] == str(evil.resolve()) + '/bin/wuwei'


def test_only_plugin_manifest_sources_are_expanded(tmp_path, monkeypatch):
    # A workspace .mcp.json is never expanded, even when it resolves into a plugin.json;
    # a plugin's plugin.json is expanded even when it resolves to another filename.
    plugin, manifest = inline_plugin(tmp_path, {'docs': {'command': '${CLAUDE_PLUGIN_ROOT}/server'}})
    target = tmp_path / 'servers.json'
    manifest.rename(target)
    manifest.symlink_to(target)
    root = own_workspace(tmp_path, monkeypatch, plugin)
    other = inline_plugin(tmp_path / 'p2', {'raw': {'command': '${CLAUDE_PLUGIN_ROOT}/x'}})[1]
    (root / '.mcp.json').symlink_to(other)
    approve(root, 'raw')
    servers = scanned(root, monkeypatch)
    assert {'raw': {'command': '${CLAUDE_PLUGIN_ROOT}/x'}} in servers
    assert {'docs': {'command': str(plugin.resolve()) + '/server'}} in servers


def goals(root):
    memory = root / '.wuwei/memory'
    memory.mkdir(exist_ok=True)
    (memory / 'goals.md').write_text('# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')


def two_servers(root, severity='high'):
    import sys
    (root / '.mcp.json').write_text(json.dumps({'mcpServers': {
        'docs': {'command': sys.executable, 'args': ['-c', 'pass'], 'description': severity},
        'remote': {'type': 'http', 'url': 'http://127.0.0.1:9/mcp'}}}))
    approve(root, 'docs', 'remote')


@pytest.mark.parametrize('severity', ['high', 'critical'])
def test_issue_acceptance_two_server_one_unreachable(configured, tmp_path, monkeypatch, severity):
    from test_plan import proposal
    from wuwei import plan, state
    goals(configured)
    calls = exec_stub(tmp_path, monkeypatch)
    two_servers(configured, severity)
    result = core().check(configured)
    assert result.exit == 2 and 'remote:' in result.reason
    assert sorted(json.loads(line) for line in calls.read_text().splitlines()) == [['docs'], ['remote']]
    rows = [json.loads(line) for line in (workspace.day_dir(configured) / 'events.jsonl').read_text().splitlines()]
    assert any(row['kind'] == 'mcp.finding' and row['payload']['server_name'] == 'docs' for row in rows)
    if severity == 'high':
        text = plan.propose(proposal(), configured).read_text()
        [line] = [line for line in text.splitlines() if line.startswith('- mcp:')]
        assert 'remote' in line and 'D-' in line
        assert core().cached(configured).exit == 0
    else:
        with pytest.raises(state.StateError, match='MCP'):
            plan.propose(proposal(), configured)
        assert core().cached(configured).exit == 1


def legacy(root, **fields):
    path = root / '.wuwei/ziran/status.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'exit': 2, 'day': '2026-09-29', 'generation': 'g', 'pending': None,
                                'reports': [], 'reason': 'MCP registry unmeasured: legacy', **fields}))


@pytest.mark.parametrize('posture', [None, 'strict', 'observe'])
@pytest.mark.parametrize('block,setup,check_exit,cached_exit,strict_exit', [
    (None, 'unmeasured', 2, 0, 2),
    ('["unmeasured"]', 'unmeasured', 2, 2, 2),
    ('[]', 'critical', 1, 0, 1),
    ('["high", "critical"]', 'high', 1, 1, 1),
    ('[]', 'invalid', 2, 2, 2),
    ('[]', 'stale', None, 2, 2),
    ('[]', 'legacy', None, 2, 2),
    (None, 'legacy-pending', None, 1, 1),
])
def test_posture_block_table(configured, monkeypatch, posture, block, setup, check_exit, cached_exit,
                             strict_exit):
    # #331: guarded (the default) is #336's table, strict the pre-#325 list, observe never blocks.
    with (configured / '.wuwei/config.toml').open('a') as config:
        if posture:
            config.write(f'[security]\nposture = "{posture}"\n')
        if block is not None:
            config.write(f'[scanner.mcp]\nblock = {block}\n')
    cached_exit = {None: cached_exit, 'strict': strict_exit, 'observe': 0}[posture]
    if setup == 'unmeasured':
        fake_scanner(monkeypatch, 2)
    elif setup in ('critical', 'high'):
        fake_scanner(monkeypatch, 1, [metadata(setup)])
    elif setup == 'invalid':
        monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=lambda files, root: None))
    elif setup == 'stale':
        fake_scanner(monkeypatch, 0)
        assert core().check(configured).exit == 0
        monkeypatch.setenv('WUWEI_NOW', '2026-09-30T08:00:00+02:00')
    elif setup == 'legacy':
        legacy(configured)
    else:
        legacy(configured, exit=0, reason='', pending='.wuwei/days/2026-09-29/decisions/D-1.md')
    if check_exit is not None:
        assert core().check(configured).exit == check_exit
    result = core().cached(configured)
    assert result.exit == cached_exit
    if result.exit:
        assert 'mcp: ' in result.reason
        assert 'floor: scanner.mcp.block' in result.reason or 'security.areas.mcp' in result.reason


OFF = 'MCP registry: not checked (security.areas.mcp = "off")'


def test_mcp_off_is_not_checked(configured, monkeypatch):
    from wuwei.commands import status
    with (configured / '.wuwei/config.toml').open('a') as config:
        config.write('[security.areas]\nmcp = "off"\n')
    calls = fake_scanner(monkeypatch, 1, [metadata('critical')])
    assert core().check(configured) == registry.Result(0, reason=OFF)
    assert core().cached(configured) == registry.Result(0, reason=OFF)
    assert calls == []
    assert not (configured / '.wuwei/ziran/status.json').exists()
    events = workspace.day_dir(configured) / 'events.jsonl'
    assert not events.exists() or '"mcp.' not in events.read_text()
    from test_plan import proposal
    from wuwei import plan
    goals(configured)
    text = plan.propose(proposal(), configured).read_text()
    assert any(line.startswith('- mcp:') and 'not checked' in line for line in text.splitlines())
    assert not [row for row in status.attention(workspace.day_dir(configured))
                if str(row.get('source', '')).startswith('mcp.')]


def test_adapter_failed_run_restores_only_its_snapshot(source, monkeypatch):
    ziran = importlib.import_module('adapters.scanner.ziran')
    outcome = {}
    def run(argv, **kwargs):
        if argv[1] == '--version':
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0')
        snapshots = Path(argv[argv.index('--snapshot-dir') + 1])
        (snapshots / 'docs.json').write_text('changed')
        outcome['dir'] = snapshots
        if outcome.get('fail', True):
            raise subprocess.TimeoutExpired(argv, 60)
        (Path(argv[argv.index('--out') + 1]) / 'registry-watch-report.json').write_text(json.dumps([finding()]))
        return SimpleNamespace(returncode=1, stdout='', stderr='')
    monkeypatch.setattr(ziran.subprocess, 'run', run)
    assert ziran.mcp([source], root=source.parent).exit == 2
    assert not outcome['dir'].exists()
    outcome['dir'].mkdir(parents=True)
    (outcome['dir'] / 'docs.json').write_text('approved')
    assert ziran.mcp([source], root=source.parent).exit == 2
    assert (outcome['dir'] / 'docs.json').read_text() == 'approved'
    outcome['fail'] = False
    assert ziran.mcp([source], root=source.parent).exit == 1
    assert (outcome['dir'] / 'docs.json').read_text() == 'changed'


def test_measured_baseline_kept_while_another_server_unmeasured(configured, tmp_path, monkeypatch):
    exec_stub(tmp_path, monkeypatch)
    two_servers(configured, 'none')
    assert core().check(configured).exit == 2
    assert list((configured / '.wuwei/ziran/snapshots').glob('*/docs.json'))
    assert not list((configured / '.wuwei/ziran/snapshots').glob('*/remote.json'))


@pytest.mark.parametrize('name', ['bad name', '-x', 'a/b'])
def test_invalid_server_name_fail_closed(configured, monkeypatch, name):
    fake_scanner(monkeypatch, 0)
    (configured / '.wuwei/config.toml').write_text('[adapters]\nscanner="ziran"\n[scanner.mcp]\nblock = []\n')
    (configured / '.mcp.json').write_text(json.dumps({'mcpServers': {name: {'command': 'fake'}}}))
    approve(configured, name)
    assert core().check(configured).exit == 2
    assert core().cached(configured).exit == 2


def test_issue_acceptance_unapproved_never_executed(configured, tmp_path, monkeypatch):
    import sys
    calls = exec_stub(tmp_path, monkeypatch)
    sentinel = tmp_path / 'sentinel'
    (configured / '.mcp.json').write_text(json.dumps({'mcpServers': {'writer': {
        'command': sys.executable, 'args': ['-c', f'open({str(sentinel)!r}, "w")']}}}))
    result = core().check(configured)
    assert result.exit == 0 and 'writer: not attached (unapproved)' in result.reason
    assert not sentinel.exists() and not calls.exists()
    approve(configured, 'writer')
    assert core().check(configured).exit == 0
    assert sentinel.exists()


def user_settings(data):
    path = Path.home() / '.claude/settings.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data))


def project_settings(root, name, data):
    (root / '.claude').mkdir(exist_ok=True)
    (root / '.claude' / name).write_text(json.dumps(data))


def worktree(root, repo, item):
    """An item worktree as git worktree add leaves it: a .git file pointing into repo/.git."""
    path = root / 'worktrees' / item
    path.mkdir(parents=True)
    (path / '.git').write_text(f'gitdir: {repo / ".git/worktrees" / item}\n')


def test_worktree_approval_only_counts_for_its_own_repo(configured, tmp_path, monkeypatch):
    import sys
    exec_stub(tmp_path, monkeypatch)
    sentinel = tmp_path / 'sentinel'
    (configured / '.mcp.json').unlink()
    (configured / 'b').mkdir()
    (configured / 'b/.mcp.json').write_text(json.dumps({'mcpServers': {'docs': {
        'command': sys.executable, 'args': ['-c', f'open({str(sentinel)!r}, "w")']}}}))
    (configured / '.wuwei/config.toml').write_text(
        'repos=[{name="example/b",path="b",default_branch="main"}]\n[adapters]\nscanner="ziran"\n')
    (Path.home() / '.claude.json').write_text('{}')
    worktree(configured, configured / 'a', 'ITEM-1')
    approve(configured, 'docs', key=configured / 'worktrees/ITEM-1')
    result = core().check(configured)
    assert 'docs: not attached (unapproved)' in result.reason and not sentinel.exists()
    worktree(configured, configured / 'b', 'ITEM-2')
    approve(configured, 'docs', key=configured / 'worktrees/ITEM-2')
    assert core().check(configured).exit == 0 and sentinel.exists()


def test_user_settings_follow_configured_user_file(configured, monkeypatch):
    calls = fake_scanner(monkeypatch)
    home = configured / 'home'
    (home / '.claude').mkdir(parents=True)
    (home / '.claude.json').write_text('{}')
    (home / '.claude/settings.json').write_text(json.dumps({'enabledMcpjsonServers': ['docs']}))
    (Path.home() / '.claude.json').write_text('{}')
    (configured / '.wuwei/config.toml').write_text(
        '[adapters]\nscanner="ziran"\n[scanner.mcp]\nuser_file="home/.claude.json"\n')
    assert core().check(configured).exit == 0 and len(calls) == 1


@pytest.mark.parametrize('how,scanned', [
    ('user', True), ('user-all', True), ('settings', True), ('project-all', True),
    ('project-local', True), ('repo', True), ('worktree', True), ('user-scope', True),
    ('none', False), ('disabled', False)])
def test_approval_sources(configured, monkeypatch, how, scanned):
    (Path.home() / '.claude.json').write_text('{}')
    calls = fake_scanner(monkeypatch)
    root = configured
    if how == 'user':
        approve(root, 'docs')
    elif how == 'user-all':
        (Path.home() / '.claude.json').write_text(json.dumps(
            {'projects': {str(root): {'enableAllProjectMcpServers': True}}}))
    elif how == 'settings':
        user_settings({'enabledMcpjsonServers': ['docs']})
    elif how == 'project-all':
        project_settings(root, 'settings.json', {'enableAllProjectMcpServers': True})
    elif how == 'project-local':
        project_settings(root, 'settings.local.json', {'enabledMcpjsonServers': ['docs']})
    elif how == 'repo':
        (root / 'repo').mkdir()
        (root / '.mcp.json').rename(root / 'repo/.mcp.json')
        (root / '.wuwei/config.toml').write_text(
            'repos=[{name="example/repo",path="repo",default_branch="main"}]\n[adapters]\nscanner="ziran"\n')
        approve(root, 'docs', key=root / 'repo')
    elif how == 'worktree':
        worktree(root, root, 'ITEM-1')
        approve(root, 'docs', key=root / 'worktrees/ITEM-1')
    elif how == 'user-scope':
        (root / '.mcp.json').unlink()
        (Path.home() / '.claude.json').write_text(json.dumps({'mcpServers': {'docs': {'command': 'fake'}}}))
    elif how == 'disabled':
        project_settings(root, 'settings.json', {'enableAllProjectMcpServers': True,
                                                 'disabledMcpjsonServers': ['docs']})
    result = core().check(root)
    assert result.exit == 0
    assert len(calls) == int(scanned)
    assert ('docs: not attached (unapproved)' in result.reason) is not scanned


@pytest.mark.parametrize('bad', ['local-json', 'list', 'flag', 'projects'])
def test_invalid_approval_state_fail_closed(configured, monkeypatch, bad):
    fake_scanner(monkeypatch)
    (configured / '.wuwei/config.toml').write_text('[adapters]\nscanner="ziran"\n[scanner.mcp]\nblock = []\n')
    user = Path.home() / '.claude.json'
    if bad == 'local-json':
        (configured / '.claude').mkdir()
        (configured / '.claude/settings.local.json').write_text('{')
    elif bad == 'list':
        user.write_text(json.dumps({'projects': {str(configured): {'enabledMcpjsonServers': 'docs'}}}))
    elif bad == 'flag':
        user.write_text(json.dumps({'projects': {str(configured): {'enableAllProjectMcpServers': 'yes'}}}))
    else:
        user.write_text(json.dumps({'projects': []}))
    assert core().check(configured).exit == 2
    assert core().cached(configured).exit == 2


@pytest.mark.parametrize('command,args,pinned', [
    ('npx', ['-y', 'pkg@latest'], False), ('npx', ['-y', 'pkg'], False),
    ('uvx', ['awslabs.example@latest'], False), ('uvx', ['pkg'], False),
    ('pipx', ['run', 'pkg'], False), ('tools/npx', ['pkg@latest'], False),
    ('env', ['npx', '-y', 'pkg@latest'], False), ('env', ['A=1', 'npx', 'pkg@1.2.3'], True),
    ('npx', ['-y', 'pkg@1.2.3'], True), ('npx', ['-y', '@scope/pkg@1.2.3'], True),
    ('uvx', ['pkg==1.2.3'], True), ('pipx', ['run', 'pkg==1.2.3'], True)])
def test_issue_acceptance_unpinned_launcher_never_run(configured, tmp_path, monkeypatch, command, args, pinned):
    import sys
    calls = exec_stub(tmp_path, monkeypatch)
    sentinel = tmp_path / 'launched'
    (configured / 'tools').mkdir()
    for launcher in (tmp_path / 'npx', tmp_path / 'uvx', tmp_path / 'pipx', configured / 'tools/npx'):
        launcher.write_text(f'#!{sys.executable}\nopen({str(sentinel)!r}, "w")\n')
        launcher.chmod(0o755)
    (configured / '.mcp.json').write_text(json.dumps({'mcpServers': {'pkg': {'command': command, 'args': args}}}))
    approve(configured, 'pkg')
    result = core().check(configured)
    if pinned:
        assert calls.read_text().splitlines() == ['["pkg"]']
    else:
        assert result.exit == 2 and 'pkg: unpinned launcher' in result.reason
        assert not calls.exists() and not sentinel.exists()


def aws_server(root, package='awslabs.example@latest'):
    source = root / '.mcp.json'
    data = json.loads(source.read_text())
    data['mcpServers']['aws'] = {'command': 'uvx', 'args': [package]}
    source.write_text(json.dumps(data))
    approve(root, 'docs', 'aws')


def records(root):
    ziran = root / '.wuwei/ziran'
    events = workspace.day_dir(root) / 'events.jsonl'
    return (sorted(p.name for p in ziran.glob('accepted-*.json')),
            sorted(p.name for p in workspace.day_dir(root).glob('decisions/D-*.md')),
            events.read_text().count('mcp.decided') if events.exists() else 0)


def test_issue_acceptance_proceed_unmeasured(configured, monkeypatch):
    fake_scanner(monkeypatch)
    aws_server(configured)
    assert core().check(configured).exit == 2
    before = records(configured)
    assert core().decide(configured, servers=['aws'], confirm=lambda digest: False).exit == 1
    assert core().decide(configured, servers=['nope'], confirm=lambda digest: True).exit == 1
    assert records(configured) == before
    assert core().decide(configured, servers=['aws'], confirm=lambda digest: True).exit == 0
    [decision] = workspace.day_dir(configured).glob('decisions/D-*.md')
    text = decision.read_text()
    assert 'Decided-by: owner' in text and 'Outcome: proceed-unmeasured' in text and 'aws' in text
    rows = [json.loads(line) for line in (workspace.day_dir(configured) / 'events.jsonl').read_text().splitlines()]
    [event] = [row['payload'] for row in rows if row['kind'] == 'mcp.decided']
    assert event['outcome'] == 'proceed-unmeasured' and event['servers'] == ['aws']
    [accepted] = (configured / '.wuwei/ziran').glob('accepted-*.json')
    [[name, digest]] = json.loads(accepted.read_text())['servers']
    assert name == 'aws' and len(digest) == 64
    result = core().check(configured)
    assert result.exit == 0 and 'aws: proceeding unmeasured by owner decision' in result.reason
    aws_server(configured, 'awslabs.other@latest')
    assert core().check(configured).exit == 2


@pytest.mark.parametrize('failure', ['could-not-run', 'stale'])
def test_proceed_unmeasured_refused_without_a_current_check(configured, monkeypatch, failure):
    fake_scanner(monkeypatch)
    aws_server(configured)
    assert core().check(configured).exit == 2
    if failure == 'stale':
        monkeypatch.setenv('WUWEI_NOW', '2026-09-30T08:00:00+02:00')
    else:
        monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=lambda files, root: None))
        assert core().check(configured).exit == 2
    before = records(configured)
    assert core().decide(configured, servers=['aws'], confirm=lambda digest: True).exit == 2
    assert records(configured) == before


def test_findings_decision_while_another_server_unmeasured(configured, monkeypatch):
    fake_scanner(monkeypatch, 1, [metadata('critical')])
    aws_server(configured)
    assert core().check(configured).exit == 2
    assert core().cached(configured).exit == 1
    pending = next(workspace.day_dir(configured).glob('decisions/D-*.md'))
    pending.write_text(pending.read_text().replace('Outcome: pending', 'Outcome: proceed'))
    assert core().decide(configured, confirm=lambda digest: True).exit == 0
    assert json.loads((configured / '.wuwei/ziran/status.json').read_text())['exit'] == 2
    assert core().cached(configured).exit == 0


def test_proceed_unmeasured_keeps_exit_while_findings_pending(configured, monkeypatch):
    fake_scanner(monkeypatch, 1, [metadata('critical')])
    aws_server(configured)
    assert core().check(configured).exit == 2
    assert core().decide(configured, servers=['aws'], confirm=lambda digest: True).exit == 0
    assert json.loads((configured / '.wuwei/ziran/status.json').read_text())['exit'] == 1
    assert core().cached(configured).exit == 1


def test_mcp_cli_forms(configured, monkeypatch):
    from wuwei import integrity
    from wuwei.__main__ import main
    monkeypatch.chdir(configured)
    fake_scanner(monkeypatch)
    aws_server(configured)
    assert main(['mcp', 'check']) == 2
    assert main(['mcp', 'decide', 'proceed-unmeasured']) == 2
    assert main(['mcp', 'check', 'proceed-unmeasured', 'aws']) == 2
    assert main(['mcp', 'decide', 'aws']) == 2
    monkeypatch.setattr(integrity, '_host_confirm', lambda value, prompt: True)
    assert main(['mcp', 'decide', 'proceed-unmeasured', 'aws']) == 0
    assert main(['mcp', 'check']) == 0


def test_launcher_args_not_a_list_fail_closed(configured, monkeypatch):
    calls = fake_scanner(monkeypatch)
    (configured / '.mcp.json').write_text(json.dumps({'mcpServers': {'docs': {'command': 'npx', 'args': 'pkg'}}}))
    result = core().check(configured)
    assert result.exit == 2 and not calls and 'docs:' not in result.reason
