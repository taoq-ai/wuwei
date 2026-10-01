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
    return path


@pytest.mark.parametrize('severity,code', [('high', 1), ('critical', 1), ('medium', 0), ('low', 0), (None, 0)])
def test_adapter_fixed_argv_and_metadata(source, monkeypatch, severity, code):
    ziran = importlib.import_module('adapters.scanner.ziran')
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['capture_output'] and kwargs['text'] and kwargs['timeout'] >= 60
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


@pytest.fixture
def configured(source, monkeypatch):
    root = source.parent
    (root / '.wuwei/config.toml').write_text('[adapters]\nscanner="ziran"\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T08:00:00+02:00')
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
    rows = [{**metadata(), 'drift_type': 'tool_poisoning'}]
    calls = fake_scanner(monkeypatch, 1, rows)
    if upgrade:
        (root / '.wuwei').mkdir()
        (root / '.wuwei/config.toml').write_text('')
    args = ['init', str(root), *(['--upgrade'] if upgrade else [])]
    assert main(args) == 1
    assert calls == [[root / '.mcp.json']]
    assert 'MCP' in capsys.readouterr().err
    assert core().cached(root).exit == 1
    assert list((root / '.wuwei/days').glob('*/decisions/D-*.md'))


@pytest.mark.parametrize('code', [0, 1, 2])
def test_morning_check_before_launch(configured, monkeypatch, code):
    from test_plan import proposal
    from wuwei import plan, state
    from wuwei.guards.agent_launch import check
    memory = configured / '.wuwei/memory'
    memory.mkdir()
    (memory / 'goals.md').write_text('# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    calls = fake_scanner(monkeypatch, code, [metadata()] if code == 1 else [])
    if code:
        with pytest.raises(state.StateError if code == 1 else OSError, match='MCP'):
            plan.propose(proposal(), configured)
    else:
        assert plan.propose(proposal(), configured).is_file()
    assert len(calls) == 1
    result = check({'cwd': str(configured), 'tool_input': {
        'subagent_type': 'wuwei:builder', 'description': 'Build', 'prompt': 'no brief'}})
    assert result[0] == (code or 1)
    if code:
        assert 'MCP' in result[1]
    assert not state.read_state(configured)['seats']


def test_sticky_findings_owner_confirmation_and_rollover(configured, monkeypatch):
    from wuwei import state
    fake_scanner(monkeypatch, 1, [metadata()])
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
    assert next(row['payload'] for row in rows if row['kind'] == 'mcp.finding') == metadata()
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
    fake_scanner(monkeypatch, 2)
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
    'python3 -mwuwei mcp decide',
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
        return registry.Result(2, reason='watch-registry timeout')
    monkeypatch.setattr(registry, 'load', lambda *args: SimpleNamespace(mcp=failed))
    assert mcp.check(configured).exit == 2
    assert snapshot.read_text() == 'approved'
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


def test_path_stub_init_then_description_drift_before_morning_launch(tmp_path, monkeypatch):
    import os
    import sys
    from test_plan import proposal
    from wuwei.__main__ import main
    from wuwei.guards.agent_launch import check
    root = tmp_path / 'workspace'
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T08:00:00+02:00')
    assert main(['init']) == 0
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('scanner = "none"', 'scanner = "ziran"'))
    mcp_file = root / '.mcp.json'
    mcp_file.write_text('{"mcpServers":{"docs":{"command":"fake","description":"approved"}}}')
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
    assert core().check(root).exit == 0


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
    monkeypatch.setattr(core(), 'PLUGIN', plugin, raising=False)
    path = (plugin if where == 'install' else root) / '.mcp.json'
    path.write_text(json.dumps({'mcpServers': {'cockpit': server}}))
    assert core().discover(root, workspace.load_config(root)) == [path]
    assert core().cached(root).exit == 2
    result = core().check(root)
    assert result.exit == 2 and 'unmeasured' in result.reason
    assert core().launch(root).exit == 2
