"""wuwei doctor: one report over the existing checks, and --fix for the allow-listed ones."""

from argparse import Namespace
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from fakes.code_host import Fake as CodeHost
from fakes.host import Fake as Host
from fakes.vcs import Fake as Vcs
from wuwei import heartbeat, integrity, registry, state, workspace
from wuwei.__main__ import main
from wuwei.commands import doctor, init
from wuwei.registry import Result

UPGRADE = init.upgrade  # the real one; the ws fixture replaces init.upgrade

NOW = '2026-10-03T12:00:00+00:00'
TODAY = '2026-10-03'
REPO = ('[[repos]]\nname = "acme/widget"\npath = "repo"\ndefault_branch = "main"\n'
        'fast_checks = ["ruff check ."]\nidentity = { name = "Ada", email = "ada@example.com" }\n')
IDENTITY = ('\n[owner]\nhandles = ["ada"]\n\n[shepherd]\nlead_login = "ada"\n\n'
            '[shepherd.authors]\n"ada@example.com" = {login = "ada"}\n')
CONFIG = '[adapters]\ncode_host = "github"\n' + REPO + IDENTITY + '\n[telemetry]\nshare = "off"\n'
DIGEST = 'd' * 64
ZIRAN = CONFIG.replace('code_host = "github"\n', 'code_host = "github"\nscanner = "ziran"\n')  # #424: record rows
CLASSIC_LINE = 'acme/widget main: classic protection: none visible (404: unprotected or no admin)'
TRIAL = 'page: plugin integrity: .in_use/12345'


def W(rest):
    """A fix line as doctor prints it, with the real launcher (#362)."""
    return f"{integrity.PLUGIN / 'bin/wuwei'} {rest}"


class Service:
    def __init__(self):
        self.results, self.calls, self.installed, self.error = [(0, '', 30)], [], [], None

    def probe(self, calls, cwd, during=lambda: None, timeout=10):
        self.calls.append((calls, cwd))
        if self.error:
            raise self.error
        return list(self.results), during()

    def call(self, argv):
        self.installed.append(argv)


def stub(directory, *names):
    for name in names:
        (directory / name).write_text('#!/bin/sh\nexit 0\n')
        (directory / name).chmod(0o755)


def old(path):
    for item in [path, *path.rglob('*')]:
        os.utime(item, (1_000_000, 1_000_000))


def no_changes(args):
    print('No workspace changes needed')
    return 0


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from fakes.integrity import seed
    plugin = tmp_path / 'plugin'
    for name in ('bin', 'hooks', '.claude-plugin'):
        (plugin / name).mkdir(parents=True)
    stub(plugin / 'bin', 'wuwei')
    (plugin / 'hooks/hooks.json').write_text(json.dumps({'hooks': {'PreToolUse': []}}))
    (plugin / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'wuwei', 'version': '0.11.0'}))
    (plugin / 'MANIFEST.sha256.sig').write_text('sig\n')
    old(plugin)
    monkeypatch.setattr(integrity, 'PLUGIN', plugin)
    installed = Path.home() / '.claude/plugins/installed_plugins.json'
    installed.parent.mkdir(parents=True)
    installed.write_text(json.dumps({'version': 2, 'plugins': {
        'wuwei@wuwei': [{'scope': 'user', 'installPath': str(plugin)}]}}))
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    stub(bin_dir, 'gh', 'launchctl', 'systemctl', 'ziran')
    monkeypatch.setenv('PATH', str(bin_dir))
    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / 'repo/.git').mkdir(parents=True)
    (root / 'repo/.specify').mkdir()
    (root / '.wuwei/config.toml').write_text(CONFIG)
    (root / '.wuwei/calibration.json').write_text(json.dumps({'acme/widget': {'date': TODAY}}))
    (root / '.wuwei/executable').write_text(f"{plugin / 'bin/wuwei'}\n")
    seed(root)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    record(root)
    unit = workspace.watch_unit(root)[1]
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text('')
    state.append_event('watch: clock', {}, root)
    probes = {name: {'result': 'ok', 'value': 'ok'} for name, _ in heartbeat.PROBES}
    monkeypatch.setattr(heartbeat, 'measure', lambda root: probes)
    monkeypatch.setattr(init, 'upgrade', no_changes)
    service = Service()
    monkeypatch.setattr(registry, 'watch_service', lambda: service)
    host = Host()
    code_host = CodeHost()
    code_host.results['auth_status'] = Result(0)
    code_host.auth_status = lambda root=None: code_host._call('auth_status', (), root)
    vcs = Vcs({'identity': Result(0, {'name': 'Ada', 'email': 'ada@example.com'}),
               'branches': Result(0, ['main'])})
    fakes = {'host': host, 'code_host': code_host, 'vcs': vcs}
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: fakes.get(kind) or real(kind, config))
    return SimpleNamespace(root=root, plugin=plugin, bin=bin_dir, probes=probes, service=service,
                           host=host, code_host=code_host, vcs=vcs, installed=installed, mp=monkeypatch)


def record(root, day=TODAY, **changes):
    path = root / '.wuwei/ziran/status.json'
    path.parent.mkdir(exist_ok=True)
    path.unlink(missing_ok=True)
    path.write_text(json.dumps({'exit': 0, 'day': day, 'reason': '', 'generation': 'g', 'reports': [],
                                'pending': None, **changes}))


def config(root, text):
    (root / '.wuwei/config.toml').write_text(text)


def row(rows, name):
    found = [r for r in rows if r['name'] == name]
    assert len(found) == 1, (name, [r['name'] for r in rows])
    return found[0]


def names(rows, section):
    return [r['name'] for r in rows if r['section'] == section]


def events(root, kind):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [r['payload'] for r in rows if r['kind'] == kind]


def protected(**changes):
    from fakes.replay import recordings
    data = next(c for c in recordings('code_host') if c['operation'] == 'protection')['data']
    return Result(0, {**data, **changes})


CLASSIC_404 = dict(classic=False, required_checks=[], approvals=0, allow_force_pushes=True,
                   allow_deletions=True)


# Phase 1: rows and exit rule

def test_outcome_findings_before_unmeasured():
    ok, warn, fail, unmeasured = ({'status': s} for s in ('ok', 'warn', 'fail', 'unmeasured'))
    assert doctor.outcome([ok, unmeasured, warn]) == 1
    assert doctor.outcome([fail, unmeasured]) == 1
    assert doctor.outcome([ok, unmeasured]) == 2
    assert doctor.outcome([ok, ok]) == 0


def test_fix_allow_list_is_pinned():
    # config-set waits for #327's confirmed `config set`.
    assert set(doctor.FIXES) == {'integrity-reconfirm', 'init-upgrade', 'config-promote', 'calibrate',
                                 'watch-install', 'listen-install', 'trace-decisions', 'mcp-reports'}


# US1: the rows

def test_install_rows(ws):
    rows = doctor.diagnose()
    assert names(rows, 'install') == ['plugin', 'integrity', 'in_use', 'hooks', 'launcher', 'python']
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'install'), rows
    assert row(rows, 'plugin')['value'] == f'{ws.plugin} 0.11.0 (signed release)'
    assert row(rows, 'in_use')['value'] == '0 Claude Code process markers (expected)'
    assert row(rows, 'hooks')['value'] == 'registered in Claude Code'

    (ws.plugin / '.in_use').mkdir()
    (ws.plugin / '.in_use/12345').write_text('')
    old(ws.plugin)
    rows = doctor.diagnose()
    assert row(rows, 'in_use') == {'section': 'install', 'name': 'in_use', 'status': 'ok',
                                   'value': '1 Claude Code process markers (expected)'}
    assert row(rows, 'integrity')['status'] == 'ok'

    ws.installed.write_text(json.dumps({'version': 2, 'plugins': {}}))
    hooks = row(doctor.diagnose(), 'hooks')
    assert hooks['status'] == 'fail' and hooks['fix'] == '/plugin install wuwei@wuwei in Claude Code'

    ws.mp.setattr(integrity, 'fresh', lambda root: Result(2, reason=TRIAL))
    found = row(doctor.diagnose(), 'integrity')
    assert found['status'] == 'fail' and found['value'] == TRIAL
    assert 'wuwei integrity reconfirm' in found['fix'] and 'reinstall' in found['fix']
    assert 'apply' not in found

    (ws.plugin / 'MANIFEST.sha256.sig').unlink()
    (ws.plugin / '.git').mkdir()
    rows = doctor.diagnose()
    assert row(rows, 'hooks')['value'].startswith('development checkout')
    assert row(rows, 'hooks')['status'] == 'ok'
    found = row(rows, 'integrity')
    assert found['fix'] == W('integrity reconfirm') and found['apply'] == 'integrity-reconfirm'


def host_case(ws, change):
    kind, value = change
    if kind == 'unpath':
        (ws.bin / value).unlink()
    elif kind == 'config':
        config(ws.root, value)
    elif kind == 'auth':
        ws.code_host.results['auth_status'] = Result(value, reason='gh auth: could not run')
    elif kind == 'identity':
        ws.vcs.results['identity'] = Result(2, reason='missing configured identity')
        config(ws.root, CONFIG.replace('identity = { name = "Ada", email = "ada@example.com" }\n', ''))
    elif kind == 'memory':
        ws.host.results['free_memory'] = Result(0, 10 * 2**20)


@pytest.mark.parametrize('change, name, status, fix', [
    (('unpath', 'gh'), 'gh', 'fail', 'install the GitHub CLI, then gh auth login'),
    (('auth', 1), 'gh', 'fail', 'gh auth login'),
    (('auth', 2), 'gh', 'unmeasured', None),
    (('config', '[adapters]\ncode_host = "none"\n' + REPO), 'gh', 'ok', None),
    (('identity', None), 'git identity', 'fail', None),
    (('config', '[adapters]\nscanner = "ziran"\n' + REPO), 'ziran', 'ok', None),
    (('config', '[adapters]\ninbound = "slack"\n' + REPO), 'claude', 'fail', None),
    (('config', '[adapters]\nruntime = "codex"\n[codex]\ncommand = ["codex"]\n' + REPO), 'codex', 'fail',
     'install the Codex CLI'),
    (('memory', None), 'memory', 'fail', None),
    (('config', '[adapters]\nhost = "none"\n' + REPO), 'memory', 'unmeasured', None),
    (('unpath', 'launchctl'), 'service manager', 'fail', None),
])
def test_host_rows(ws, change, name, status, fix):
    import sys
    if change == ('unpath', 'launchctl') and sys.platform != 'darwin':
        change = ('unpath', 'systemctl')
    host_case(ws, change)
    rows = doctor.diagnose()
    found = row(rows, name)
    assert found['status'] == status, found
    if fix:
        assert found['fix'] == fix
    if name == 'git identity':
        assert found['fix'].startswith('git config --global user.name')
    assert not events(ws.root, 'adapter: none')


def test_host_rows_healthy(ws):
    rows = doctor.diagnose()
    assert names(rows, 'host') == ['gh', 'git identity', 'ziran', 'claude', 'codex', 'memory',
                                   'service manager']
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'host'), rows
    assert row(rows, 'claude')['value'].startswith('not on PATH')
    (ws.bin / 'ziran').unlink()
    config(ws.root, '[adapters]\nscanner = "ziran"\n' + REPO)
    assert row(doctor.diagnose(), 'ziran')['status'] == 'fail'


def test_host_identity_set_per_repository(ws):
    ws.vcs.results['identity'] = Result(1, reason='git.identity: could not run: git exited 1')
    rows = doctor.diagnose()
    found = row(rows, 'git identity')
    assert found['status'] == 'ok' and 'repositories set their own' in found['value']
    assert doctor.outcome(rows) == 0


def test_no_workspace(ws, tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE')
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(integrity, 'measure', lambda: Result(0, 'f' * 64))
    rows = doctor.diagnose()
    assert names(rows, 'install') and names(rows, 'host')
    assert [(r['name'], r['status']) for r in rows if r['section'] == 'workspace'] == [('workspace', 'fail')]
    assert row(rows, 'workspace')['fix'].startswith(W('setup --shadow'))
    assert names(rows, 'gates') == names(rows, 'day') == []
    assert names(rows, 'guards') == ['outside workspace']
    assert doctor.outcome(rows) == 1


def test_workspace_rows_healthy(ws):
    rows = doctor.diagnose()
    assert names(rows, 'workspace') == [
        'workspace', 'config', 'template', 'executable', 'memory tiers', 'acme/widget path', 'acme/widget git', 'acme/widget branch',
        'acme/widget identity', 'acme/widget fast_checks', 'acme/widget spec', 'calibration', 'drift',
        'interview', 'profile', 'posture', 'telemetry']
    assert row(rows, 'posture')['value'] == 'guarded (from security.posture)'
    assert row(rows, 'telemetry')['value'] == 'share off'
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'workspace'), rows


def test_workspace_config_does_not_load(ws):
    config(ws.root, 'repos = []\n' + CONFIG)
    rows = doctor.diagnose()
    found = row(rows, 'config')
    assert found['status'] == 'fail'
    assert 'delete that line before using [[repos]] tables' in found['value']
    assert found['fix'] == W('init --upgrade') and found['apply'] == 'init-upgrade'
    assert names(rows, 'workspace') == ['workspace', 'config', 'template', 'executable']
    assert [(r['name'], r['status'], r['value']) for r in rows if r['section'] in ('gates', 'day')] == [
        ('gates', 'unmeasured', 'config.toml does not load'), ('day', 'unmeasured', 'config.toml does not load')]

    config(ws.root, '[adapters]\ntracker = "bogus"\n')
    found = row(doctor.diagnose(), 'config')
    assert found['status'] == 'fail' and found['fix'].startswith('edit .wuwei/config.toml: ')
    assert 'apply' not in found


def test_workspace_executable_pointer(ws, tmp_path):
    pointer = ws.root / '.wuwei/executable'
    pointer.write_text(f"{ws.plugin / 'bin/wuwei'}\n")
    assert row(doctor.diagnose(), 'executable')['status'] == 'ok'
    stale = tmp_path / 'cache/0.11.0/bin/wuwei'
    pointer.write_text(f'{stale}\n')
    found = row(doctor.diagnose(), 'executable')
    assert found['status'] == 'fail' and str(stale) in found['value'] and 'missing' in found['value']
    assert found['fix'] == W('init --upgrade') and found['apply'] == 'init-upgrade'
    pointer.unlink()
    found = row(doctor.diagnose(), 'executable')
    assert found['status'] == 'fail' and found['apply'] == 'init-upgrade'


def test_workspace_template_drift(ws, monkeypatch):
    def upgrade(args):
        assert args.dry_run
        print('Would upgrade config.toml: add x')
        print('Charter override needs review: lead.md (local 1, base 2)')
        return 0
    monkeypatch.setattr(init, 'upgrade', upgrade)
    rows = doctor.diagnose()
    found = row(rows, 'template')
    assert found['status'] == 'warn' and found['detail'] == ['Would upgrade config.toml: add x']
    assert found['apply'] == 'init-upgrade'
    charters = row(rows, 'charter overrides')
    assert charters['status'] == 'warn' and 'apply' not in charters
    assert charters['docs'] == 'docs/site/charter-overrides.md'


@pytest.mark.parametrize('repo, name, status, apply', [
    (REPO.replace('"repo"', '"gone"'), 'acme/widget path', 'fail', None),
    (REPO.replace('"repo"', '"plain"'), 'acme/widget git', 'fail', None),
    (REPO.replace('"main"', '"trunk"'), 'acme/widget branch', 'fail', None),
    (REPO.replace('identity = { name = "Ada", email = "ada@example.com" }\n', ''),
     'acme/widget identity', 'warn', None),
    (REPO.replace('["ruff check ."]', '[]'), 'acme/widget fast_checks', 'warn', 'config-promote'),
])
def test_workspace_repository_rows(ws, repo, name, status, apply):
    (ws.root / 'plain').mkdir()
    config(ws.root, '[adapters]\ncode_host = "github"\n' + repo)
    found = row(doctor.diagnose(), name)
    assert found['status'] == status, found
    assert found.get('apply') == apply
    if name.endswith('fast_checks'):
        assert found['fix'].startswith(W('config promote --measure'))
        assert "bin/wuwei config set repos.0.fast_checks '[\"<command>\"]'" in found['fix']
    if name.endswith('identity'):
        assert 'repos.0.identity.name = "Ada"' in found['fix']


@pytest.mark.parametrize('spec, plugins, status', [
    ('', None, 'ok'), ('[spec]\nengine = "none"\n', None, 'ok'),
    ('[spec]\nengine = "superpowers"\n', '{"plugins": {"superpowers@superpowers-marketplace": []}}', 'ok'),
    ('[spec]\nengine = "superpowers"\n', '{"plugins": {}}', 'fail'),
    ('[spec]\nengine = "superpowers"\n', b'\xff', 'unmeasured')])
def test_workspace_spec_row(ws, spec, plugins, status):
    from wuwei import specmode
    if plugins is not None:
        path = ws.root / 'plugins.json'
        path.write_bytes(plugins if isinstance(plugins, bytes) else plugins.encode())
        spec += f'[scanner.mcp]\nplugins_file = "{path}"\n'
    config(ws.root, CONFIG + spec)
    found = row(doctor.diagnose(), 'acme/widget spec')
    assert found['status'] == status, found
    if status == 'fail':
        assert found['fix'] == specmode.INSTALL['superpowers']
    (ws.root / 'repo/.specify').rmdir()
    if not spec:
        found = row(doctor.diagnose(), 'acme/widget spec')
        assert found['status'] == 'fail' and found['fix'] == specmode.INSTALL['speckit']


def test_workspace_calibration_and_shadow(ws, monkeypatch):
    (ws.root / '.wuwei/calibration.json').unlink()
    assert row(doctor.diagnose(), 'calibration')['status'] == 'warn'
    state.append_event('calibration.drift', {'repo': 'acme/widget', 'changed': ['runner']}, ws.root)
    found = row(doctor.diagnose(), 'drift')
    assert found['status'] == 'warn' and found['apply'] == 'calibrate' and 'acme/widget' in found['value']
    observe = '[security]\nposture = "observe"\n[guards]\nshadow_since = "{}"\n[adapters]'
    config(ws.root, CONFIG.replace('[adapters]', observe.format('2026-09-30')))
    found = row(doctor.diagnose(), 'posture')
    assert (found['status'], found['value']) == ('ok', 'observe (from security.posture), 4 days left')
    config(ws.root, CONFIG.replace('[adapters]', observe.format('2026-09-25')))
    found = row(doctor.diagnose(), 'posture')
    assert found['status'] == 'warn' and 'apply' not in found and '8 days' in found['value']
    assert found['value'].startswith('observe (from security.posture)')
    assert found['fix'] == ('set security.posture = "guarded" in .wuwei/config.toml, '
                            'or raise guards.shadow_days')
    # guards.mode = "shadow" is the deprecated alias for observe (#308).
    config(ws.root, CONFIG.replace('[adapters]', '[guards]\nmode = "shadow"\nshadow_since = "2026-09-25"\n'
                                                 '[adapters]'))
    found = row(doctor.diagnose(), 'posture')
    assert found['status'] == 'warn' and found['apply'] == 'init-upgrade'
    config(ws.root, CONFIG.replace('[adapters]', '[security]\nposture = "strict"\n[adapters]'))
    assert row(doctor.diagnose(), 'posture')['value'] == 'strict (from security.posture)'


def test_workspace_telemetry_question_pending(ws):
    # #422: share unset behaves as off but the interview question is still owed.
    config(ws.root, CONFIG.replace('share = "off"', 'share = ""'))
    found = row(doctor.diagnose(), 'telemetry')
    assert (found['status'], found['value'], found['fix']) == (
        'warn', 'sharing not chosen yet (pending interview question)', W('calibrate --interview telemetry'))
    config(ws.root, CONFIG.replace('share = "off"', 'enabled = false'))
    assert row(doctor.diagnose(), 'telemetry')['status'] == 'ok'


def test_workspace_retired_shadow_mode(ws, monkeypatch):
    config(ws.root, CONFIG.replace('[adapters]', '[security]\nposture = "guarded"\n[guards]\nmode = "shadow"\n'
                                                 'shadow_since = "2026-09-30"\n[adapters]'))
    found = row(doctor.diagnose(), 'posture')
    assert (found['status'], found['value'], found['fix'], found['apply']) == (
        'warn', 'observe (from guards.mode = "shadow", deprecated; run doctor --fix)',
        W('init --upgrade'), 'init-upgrade')
    monkeypatch.setattr(init, 'upgrade', UPGRADE)
    found = row(doctor.diagnose(), 'template')
    assert found['status'] == 'warn' and found['apply'] == 'init-upgrade'
    assert ('Would upgrade config.toml: guards.mode = "shadow" becomes security.posture = "observe"'
            in found['detail'])


def test_gates_rows(ws):
    rows = doctor.diagnose()
    assert row(rows, 'config check')['status'] == 'ok'
    assert row(rows, 'mcp gate')['status'] == 'ok'

    ws.code_host.results['protection'] = protected(**CLASSIC_404)
    found = row(doctor.diagnose(), 'config check')
    assert (found['status'], found['value']) == ('fail', 'exit 1')
    assert CLASSIC_LINE in found['detail']
    assert any(line.startswith('acme/widget main: required reviews: missing (') for line in found['detail'])

    ws.code_host.results['protection'] = Result(2, None, 'github.protection: could not run')
    assert row(doctor.diagnose(), 'config check')['status'] == 'unmeasured'


def test_gates_without_scanner(ws):
    # #424: CONFIG leaves adapters.scanner at "none": the gate is off and WUWEI's own servers are covered.
    from wuwei import mcp
    manifest = integrity.PLUGIN / '.claude-plugin/plugin.json'
    manifest.write_text(json.dumps({**json.loads(manifest.read_text()),
                                    'mcpServers': {'cockpit': {'command': 'bin/wuwei'}}}))
    record(ws.root, exit=2, unmeasured=[['docs', DIGEST]], reason='MCP registry unmeasured; docs: unmeasured')
    rows = doctor.diagnose()
    assert (row(rows, 'mcp gate')['status'], row(rows, 'mcp gate')['value']) == ('ok', mcp.NO_SCANNER)
    assert row(rows, 'mcp cockpit') == {'section': 'gates', 'name': 'mcp cockpit', 'status': 'ok',
                                        'value': 'covered by plugin integrity'}
    assert 'mcp docs' not in names(rows, 'gates')


def test_gates_mcp_servers(ws):
    (ws.root / '.wuwei/config.toml').write_text(ZIRAN)
    record(ws.root, exit=2, reason='MCP registry unmeasured; docs: scanner check incomplete; '
           'remote: not attached (unapproved)', unmeasured=[['docs', DIGEST]], decided=[['notes', DIGEST]])
    rows = doctor.diagnose()
    found = row(rows, 'mcp docs')
    assert (found['status'], found['value']) == ('warn', 'unmeasured')
    assert found['fix'].startswith(W('mcp decide proceed-unmeasured docs'))
    assert row(rows, 'mcp notes') == {'section': 'gates', 'name': 'mcp notes', 'status': 'ok',
                                      'value': 'proceeding unmeasured by owner decision'}
    assert row(rows, 'mcp remote')['value'] == 'not attached (unapproved)'
    assert row(rows, 'mcp gate')['status'] == 'ok'

    record(ws.root, exit=1, pending=f'.wuwei/days/{TODAY}/decisions/D-1.md', severities=['critical'])
    assert row(doctor.diagnose(), 'mcp gate')['status'] == 'ok'  # #351: guarded warns.
    with (ws.root / '.wuwei/config.toml').open('a') as config:
        config.write('[security]\nposture = "strict"\n')
    found = row(doctor.diagnose(), 'mcp gate')
    assert found['status'] == 'fail' and found['fix'] == W('mcp decide D-1 proceed in a host terminal')
    assert 'Outcome' not in found['fix']

    record(ws.root, day='2026-10-02')
    found = row(doctor.diagnose(), 'mcp gate')
    assert found['status'] == 'unmeasured' and found['fix'] == W('mcp check')


def test_day_rows(ws):
    rows = doctor.diagnose()
    assert names(rows, 'day') == ['state', 'planner', 'watch', 'listener', 'heartbeat', 'nudges']
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'day'), rows
    assert row(rows, 'listener')['value'] == 'not used'

    ws.probes['state'] = {'result': 'failed', 'value': 'bad state'}
    ws.probes['planner'] = {'result': 'failed', 'value': 'planner P not registered'}
    rows = doctor.diagnose()
    assert row(rows, 'state')['fix'] == W('state recover in a host terminal')
    assert row(rows, 'planner')['status'] == 'fail' and '--take-over' in row(rows, 'planner')['fix']

    workspace.watch_unit(ws.root)[1].unlink()
    (workspace.day_dir(ws.root) / 'events.jsonl').unlink()
    found = row(doctor.diagnose(), 'watch')
    assert (found['status'], found['value'], found['apply']) == ('warn', 'not installed', 'watch-install')

    state.append_event('watch: clock', {}, ws.root)
    ws.mp.setenv('WUWEI_NOW', '2026-10-03T13:00:00+00:00')
    assert row(doctor.diagnose(), 'watch')['status'] == 'fail'

    ws.mp.setenv('WUWEI_NOW', NOW)
    state.append_event('heartbeat: clock', {'health': 'degraded', 'page': 'heartbeat refused failed: exit 0'},
                       ws.root)
    rows = doctor.diagnose()
    assert row(rows, 'heartbeat')['status'] == 'fail'
    page = row(rows, 'heartbeat page')
    assert page['status'] == 'fail' and page['fix'] == W('nudges')
    assert row(rows, 'nudges')['status'] == 'ok'


def test_guards_rows(ws):
    rows = doctor.diagnose()
    assert names(rows, 'guards') == ['refused', 'allowed', 'state_write', 'read_loop', 'status_line', 'outside workspace']
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'guards'), rows
    (calls, cwd), = ws.service.calls
    (argv, text), = calls
    payload = json.loads(text)
    assert argv == ('hook', 'PreToolUse')
    assert not Path(cwd).resolve().is_relative_to(ws.root.resolve()) and payload['cwd'] == str(cwd)
    assert payload['session_id'] == 'wuwei-heartbeat'
    assert '<<' in payload['tool_input']['command'] and 'gh ' in payload['tool_input']['command']

    ws.probes['refused'] = {'result': 'failed', 'value': 'exit 0'}
    ws.probes['allowed'] = {'result': 'unmeasured', 'value': 'timeout'}
    ws.service.results = [(2, 'refused: uninspectable', 20)]
    rows = doctor.diagnose()
    assert row(rows, 'refused')['status'] == 'fail' and 'reinstall' in row(rows, 'refused')['fix']
    assert row(rows, 'allowed')['status'] == 'unmeasured'
    ws.probes['allowed'] = {'result': 'failed', 'value': 'exit 2: page: plugin integrity: x.py'}
    assert row(doctor.diagnose(), 'allowed')['fix'] == 'fix the integrity row first'
    found = row(rows, 'outside workspace')
    assert found['status'] == 'fail' and '#323' in found['fix']
    ws.service.results = [(None, 'timeout', 10000)]
    assert row(doctor.diagnose(), 'outside workspace')['status'] == 'unmeasured'


def test_outside_probe_through_launcher(monkeypatch):
    # One real smoke of the outside-workspace probe through bin/wuwei (#323).
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert row(doctor._guards(None, None), 'outside workspace')['status'] == 'ok'


def test_healthy_workspace_exits_zero(ws, capsys):
    def listing():
        return {p: p.stat().st_mtime_ns for p in (ws.root / '.wuwei').rglob('*')
                if p.is_file() and p.name != 'state.lock'}
    before = listing()
    assert main(['doctor']) == 0
    out = capsys.readouterr().out
    headers = [line for line in out.splitlines() if line in doctor.SECTIONS.values()]
    assert headers == list(doctor.SECTIONS.values())
    assert 'fix:' not in out
    assert out.splitlines()[-1] == 'doctor: ok'
    assert listing() == before


def test_json_rows(ws, capsys):
    ws.code_host.results['auth_status'] = Result(1, reason='gh auth: missing')
    code = main(['doctor', '--json'])
    data = json.loads(capsys.readouterr().out)
    assert data['exit'] == code == 1
    for r in data['rows']:
        assert {'section', 'name', 'status', 'value'} <= set(r)
        assert ('fix' in r and 'docs' in r) == (r['status'] != 'ok')


def test_fix_and_json_are_exclusive(ws, capsys):
    with pytest.raises(SystemExit) as exit:
        main(['doctor', '--fix', '--json'])
    assert exit.value.code == 2
    assert not events(ws.root, 'doctor.fixed')


def test_trial_failures_then_clean(ws, monkeypatch, capsys):
    monkeypatch.setattr(integrity, 'fresh', lambda root: Result(2, reason=TRIAL))
    record(ws.root, exit=2, reason='MCP registry unmeasured; docs: scanner check incomplete',
           unmeasured=[['docs', DIGEST]])
    ws.code_host.results['protection'] = protected(**CLASSIC_404)
    trial = ZIRAN.replace('["ruff check ."]', '[]')
    config(ws.root, 'repos = []\n' + trial)

    assert main(['doctor']) == 1
    out = capsys.readouterr().out
    assert 'wuwei integrity reconfirm' in out and f"fix: {W('init --upgrade')}" in out
    assert 'delete that line before using [[repos]] tables' in out

    config(ws.root, trial)
    assert main(['doctor']) == 1
    out = capsys.readouterr().out
    for text in ('wuwei mcp decide proceed-unmeasured docs', f"fix: {W('config promote --measure')}", CLASSIC_LINE,
                 'acme/widget main: required reviews: missing ('):
        assert text in out, text

    monkeypatch.setattr(integrity, 'fresh', lambda root: Result(0))
    record(ws.root, reason='docs: proceeding unmeasured by owner decision', decided=[['docs', DIGEST]])
    config(ws.root, CONFIG)
    ws.code_host.results['protection'] = protected()
    assert main(['doctor']) == 0, capsys.readouterr().out


def test_unapproved_server_is_ok(ws):
    config(ws.root, ZIRAN)
    record(ws.root, reason='remote: not attached (unapproved)')
    rows = doctor.diagnose()
    assert row(rows, 'mcp remote')['status'] == 'ok'
    assert doctor.outcome(rows) == 0


def pr_flow(extra=''):
    return {r['name']: r for r in doctor.pr_flow(workspace.load_config(Path('pr-flow'), raw=extra))}


def test_pr_flow_rows():
    rows = pr_flow()
    assert list(rows) == ['owner.handles', 'shepherd.lead_login', 'shepherd.authors',
                          'adapters.tracker', 'adapters.chat', 'adapters.review_bot']
    for name, phase in (('owner.handles', 'reviewer selection, review replies and obligations at pr raise'),
                        ('shepherd.lead_login', 'the lead review request at pr raise'),
                        ('shepherd.authors', 'reviewer mentions in the review ping at pr ping')):
        assert rows[name]['status'] == 'warn' and rows[name]['value'].endswith('will block: ' + phase), name
        assert rows[name]['fix'] and rows[name]['docs']
    assert rows['owner.handles']['fix'] == W("config set owner.handles '[\"<code-host login>\"]'")
    assert rows['shepherd.lead_login']['fix'] == W("config set shepherd.lead_login '\"<lead login>\"'")
    assert rows['shepherd.authors']['fix'].startswith(W('setup'))
    assert '{login = "<login>", mention = "<chat id>"}' in rows['shepherd.authors']['fix']
    for name in ('adapters.tracker', 'adapters.chat', 'adapters.review_bot'):
        assert rows[name]['status'] == 'ok' and rows[name]['value'].startswith('none: ')
    slack = pr_flow('[adapters]\nchat = "slack"\n')
    channel = slack['shepherd.review_channel']
    assert channel['status'] == 'warn' and channel['value'].endswith('will block: the review ping at pr ping')
    assert channel['fix'] == W("config set shepherd.review_channel '\"<channel id>\"'")
    assert slack['adapters.chat'] == {'section': 'pr-flow', 'name': 'adapters.chat', 'status': 'ok',
                                      'value': 'slack'}
    solo = pr_flow('[adapters]\nchat = "slack"\n[shepherd]\nmin_reviewers = 0\n')
    for name in ('shepherd.lead_login', 'shepherd.authors', 'shepherd.review_channel'):
        assert (solo[name]['status'], solo[name]['value']) == ('ok', 'not applicable: shepherd.min_reviewers = 0')
    assert solo['owner.handles']['status'] == 'warn'
    filled = pr_flow('[adapters]\nchat = "slack"\n' + IDENTITY.replace(
        'lead_login = "ada"\n', 'lead_login = "ada"\nreview_channel = "C0123ABCD"\n'))
    assert all(r['status'] == 'ok' for r in filled.values()), filled
    assert filled['owner.handles']['value'] == 'ada' and filled['shepherd.authors']['value'] == '1 mapped'


def test_pr_flow_in_full_report(ws, capsys):
    config(ws.root, CONFIG.replace('handles = ["ada"]', 'handles = []'))
    assert main(['doctor']) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines.index('Gates and adapters') < lines.index('PR flow') < lines.index('Day and sessions')
    assert '      fix: ' + W('config set owner.handles \'["<code-host login>"]\'') in lines


def test_pr_flow_section_only(ws, monkeypatch, capsys):
    def refuse(*a, **k):
        raise AssertionError('measured outside the PR flow section')
    monkeypatch.setattr(heartbeat, 'measure', refuse)
    monkeypatch.setattr(init, 'upgrade', refuse)
    monkeypatch.setattr(registry, 'load', refuse)
    assert main(['doctor', '--section', 'pr-flow']) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == 'PR flow' and out[-1] == 'doctor: ok'
    assert not set(out) & (set(doctor.SECTIONS.values()) - {'PR flow'})
    config(ws.root, CONFIG.replace('handles = ["ada"]', 'handles = []'))
    assert main(['doctor', '--section', 'pr-flow', '--json']) == 1
    data = json.loads(capsys.readouterr().out)
    assert {r['section'] for r in data['rows']} == {'pr-flow'}
    config(ws.root, 'repos = []\n' + CONFIG)
    assert main(['doctor', '--section', 'pr-flow']) == 2
    assert 'unmeasured' in capsys.readouterr().out


# US2: --fix

CHECKOUT = ('page: plugin integrity: development checkout requires host reconfirmation; '
            'run wuwei integrity reconfirm on the host')


def fix(confirm):
    return doctor.run(Namespace(fix=True, json=False, widget=False, apply=None, section=None), confirm=confirm)


def empty_checks(ws, monkeypatch, repos=1):
    from wuwei.commands import config as config_command
    text = '[adapters]\ncode_host = "github"\n'
    for index in range(repos):
        (ws.root / f'repo{index}/.git').mkdir(parents=True)
        text += REPO.replace('acme/widget', f'acme/widget{index}').replace('"repo"', f'"repo{index}"').replace(
            '["ruff check ."]', '[]')
    config(ws.root, text)
    calls, applied = [], []

    def promote(args, confirm=None):
        calls.append(args)
        print('fast_checks = ["pytest -q"]')
        print(ws.promote_extra, end='')
        if not confirm(f'digest{len(calls)}' if ws.promote_changes else 'digest', prompt='Review'):
            print('wuwei config promote: declined; nothing written', file=__import__('sys').stderr)
            return 1
        applied.append(args)
        return 0
    ws.promote_changes, ws.promote_extra = False, ''
    monkeypatch.setattr(config_command, 'promote', promote)
    return calls, applied


def test_doctor_fixed_is_reserved(ws, capsys):
    assert main(['event', 'doctor.fixed', '{}']) == 1
    assert 'owner host wuwei doctor --fix' in capsys.readouterr().err


def test_fix_reconfirms_development_checkout(ws, monkeypatch, capsys):
    (ws.plugin / 'MANIFEST.sha256.sig').unlink()
    (ws.plugin / '.git').mkdir()
    confirmed, typed = [], []
    monkeypatch.setattr(integrity, 'fresh', lambda root: Result(0) if confirmed else Result(2, reason=CHECKOUT))
    monkeypatch.setattr(integrity, 'check', lambda root: Result(1, 'f' * 64, CHECKOUT))

    def reconfirm(root, *, confirm=None):
        if confirm('f' * 64) and not confirm('0' * 64):
            confirmed.append(root)
            return Result(0)
        return Result(1, reason='declined')
    monkeypatch.setattr(integrity, 'reconfirm', reconfirm)

    def owner(digest):
        typed.append((digest, capsys.readouterr().out))
        return True
    assert fix(owner) == 0
    (digest, shown), = typed
    assert '[integrity-reconfirm] wuwei integrity reconfirm' in shown and 'f' * 64 in shown
    assert len(digest) == 12
    assert events(ws.root, 'doctor.fixed') == [{'fix': 'integrity-reconfirm', 'exit': 0}]
    out = capsys.readouterr().out
    assert 'integrity-reconfirm: exit 0' in out
    assert out.splitlines()[-1] == 'doctor: ok'


def test_fix_applies_only_the_allow_list(ws, monkeypatch, capsys):
    rows = [doctor._row('gates', 'mcp docs', 'warn', 'unmeasured', 'wuwei mcp decide proceed-unmeasured docs'),
            doctor._row('workspace', 'posture', 'warn', 'observe long', 'set security.posture = "guarded"'),
            doctor._row('day', 'state', 'fail', 'bad', 'wuwei state recover in a host terminal'),
            doctor._row('gates', 'decision', 'fail', 'pending', 'wuwei mcp decide', apply='mcp-decide')]
    monkeypatch.setattr(doctor, 'diagnose', lambda section=None: rows)
    asked = []
    assert fix(asked.append) == 1
    out = capsys.readouterr().out
    assert not asked and 'Nothing to apply' in out
    notes = out.split('Not applied:', 1)[1]
    for text in ('wuwei mcp decide proceed-unmeasured docs', 'set security.posture = "guarded"',
                 'wuwei state recover in a host terminal', 'wuwei mcp decide'):
        assert text in notes
    assert not events(ws.root, 'doctor.fixed')


def test_fix_dedupes(ws, monkeypatch, capsys):
    calls, applied = empty_checks(ws, monkeypatch, repos=2)
    assert fix(lambda digest: True) == 1  # the fake promote writes nothing, so the rows stay
    assert capsys.readouterr().out.count('[config-promote] wuwei config promote') == 1
    assert len(calls) == 2 and len(applied) == 1
    assert events(ws.root, 'doctor.fixed') == [{'fix': 'config-promote', 'exit': 0}]


def test_fix_wrong_digest_applies_nothing(ws, monkeypatch, capsys):
    calls, applied = empty_checks(ws, monkeypatch)
    assert fix(lambda digest: False) == 1
    assert 'wuwei doctor: declined; nothing applied' in capsys.readouterr().err
    assert len(calls) == 1 and not applied and not events(ws.root, 'doctor.fixed')


def test_fix_without_terminal(ws, monkeypatch, capsys):
    calls, applied = empty_checks(ws, monkeypatch)

    def no_terminal(value, *, prompt=''):
        raise OSError(integrity.HOST_TERMINAL)
    monkeypatch.setattr(integrity, '_host_confirm', no_terminal)
    assert fix(None) == 2
    assert integrity.HOST_TERMINAL in capsys.readouterr().err
    assert not applied and not events(ws.root, 'doctor.fixed')


def test_fix_changed_since_preview(ws, monkeypatch, capsys):
    calls, applied = empty_checks(ws, monkeypatch)
    runs = []

    def upgrade(args):
        runs.append(args.dry_run)
        assert args.dry_run, 'the real upgrade must not run'
        print('Would upgrade config.toml: add ' + ('x' if len(runs) <= 2 else 'y'))
        return 0
    monkeypatch.setattr(init, 'upgrade', upgrade)
    assert fix(lambda digest: True) == 1
    out = capsys.readouterr().out
    assert 'init-upgrade: exit 1' in out and 'changed since the preview' in out
    assert len(applied) == 1
    assert events(ws.root, 'doctor.fixed') == [{'fix': 'init-upgrade', 'exit': 1},
                                               {'fix': 'config-promote', 'exit': 0}]


def test_fix_binds_promote_digest(ws, monkeypatch, capsys):
    calls, applied = empty_checks(ws, monkeypatch)
    ws.promote_changes = True
    assert fix(lambda digest: True) == 1
    assert len(calls) == 2 and not applied
    assert events(ws.root, 'doctor.fixed') == [{'fix': 'config-promote', 'exit': 1}]


@pytest.mark.parametrize('extra', ['Interview answers:\n  merge: auto\n',
                                   'Profile acme: guards.mode = "enforce"\n'])
def test_fix_holds_promote_with_decisions(ws, monkeypatch, capsys, extra):
    calls, applied = empty_checks(ws, monkeypatch)
    ws.promote_extra = extra
    asked = []
    assert fix(asked.append) == 1
    out = capsys.readouterr().out
    assert not asked and not applied and not events(ws.root, 'doctor.fixed')
    assert 'wuwei config promote: cannot be applied now' in out.split('Not applied:', 1)[1]


def test_fix_installs_watch(ws, monkeypatch, capsys):
    workspace.watch_unit(ws.root)[1].unlink()
    (workspace.day_dir(ws.root) / 'events.jsonl').unlink()
    started = ws.service.call

    def call(argv):
        started(argv)
        state.append_event('watch: clock', {}, ws.root)  # the service manager starts the watch
    ws.service.call = call
    shown = []
    assert fix(lambda digest: shown.append(capsys.readouterr().out) or True) == 0
    assert '[watch-install] wuwei watch install' in shown[0] and 'unit: ' in shown[0]
    assert workspace.watch_unit(ws.root)[1].exists() and ws.service.installed
    assert events(ws.root, 'doctor.fixed') == [{'fix': 'watch-install', 'exit': 0}]


def test_fix_nothing_to_apply(ws, capsys):
    asked = []
    assert fix(asked.append) == 0
    assert 'Nothing to apply' in capsys.readouterr().out and not asked


# #352: doctor supersedes the tool-sequence decisions the pre-#352 sweep wrote

LEGACY_BODY = (
    'Question: How should this critical tool sequence be investigated?\n'
    'Context: {context}\n'
    'Chain: Bash -> {tool}\n'
    'Session digest: ' + 'a' * 64 + '\n'
    'Options:\n| Option | Description |\n| --- | --- |\n'
    '| investigate | Investigate the session and contain any exposure |\n'
    '| defer | Defer investigation while affected work stays paused |\n'
    'Musts:\n| Criterion | investigate | defer |\n| --- | --- | --- |\n'
    '| Keep affected work paused | pass | pass |\n'
    'Wants:\n| Criterion | Weight | investigate | defer |\n| --- | --- | --- | --- |\n'
    '| Resolve potential exposure | 10 | 10 | 0 |\n'
    'Recommendation: investigate\nConfidence: high\nReversibility: unsure\n'
    'Blast radius: workspace security\nPre-mortem: Further activity could expose data.\n'
    'Revisit: Before resuming affected work.\nDecided-by: owner\nOutcome: pending\n')


def legacy_decisions(root):
    directory = workspace.day_dir(root) / 'decisions'
    directory.mkdir(exist_ok=True)
    for ident, context, tool in [('D-2', 'Session has no matching item reservation.', 'Write'),
                                 ('D-3', 'Session has no matching item reservation.', 'Edit'),
                                 ('D-4', 'Affected reserved items parked where active.', 'Write')]:
        (directory / f'{ident}.md').write_text(LEGACY_BODY.format(context=context, tool=tool))
    return directory


def test_trace_decisions_row_and_fix(ws, capsys):
    from wuwei import decision
    from wuwei.commands.dashboard import cockpit_snapshot
    directory = legacy_decisions(ws.root)
    seat = (directory / 'D-4.md').read_text()
    found = row(doctor.diagnose(), 'trace decisions')
    assert found['status'] == 'warn' and 'D-2, D-3' in found['value']
    assert found['apply'] == 'trace-decisions'
    shown = []
    fix(lambda digest: shown.append(capsys.readouterr().out) or True)
    assert '[trace-decisions]' in shown[0] and 'D-2' in shown[0] and 'D-3' in shown[0]
    data = state.read_state(ws.root)
    for ident in ('D-2', 'D-3'):
        text = (directory / f'{ident}.md').read_text()
        assert 'Outcome: superseded' in text and text.count('Outcome:') == 1
        assert 'Notes: superseded by wuwei doctor --fix' in text
        decision.evaluate(text)
        assert data['decision_outcomes'][ident]['decided_by'] == 'owner'
        assert decision.answered(data, ident) == 'superseded'
    assert [d['id'] for d in cockpit_snapshot(workspace.day_dir(ws.root))['decisions']] == ['D-4']
    assert {'fix': 'trace-decisions', 'exit': 0} in events(ws.root, 'doctor.fixed')
    assert not [r for r in doctor.diagnose() if r['name'] == 'trace decisions']
    assert (directory / 'D-4.md').read_text() == seat


def test_trace_decisions_changed_since_preview(ws, capsys):
    directory = legacy_decisions(ws.root)

    def answer(digest):
        state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update(
            {'D-2': {'option': 'defer', 'outcome': 'defer', 'decided_by': 'owner',
                     'reversibility': 'unsure'}}), ws.root, reserved=False)
        return True
    fix(answer)
    out = capsys.readouterr().out
    assert 'changed since the preview' in out and 'trace-decisions: exit 1' in out
    assert 'Outcome: pending' in (directory / 'D-3.md').read_text()


def two_fixes(ws, monkeypatch):
    """calibrate and init-upgrade due, each with a fake preview and an apply that records its call."""
    applied = []
    rows = [doctor._row('workspace', 'calibration', 'warn', 'old', 'wuwei calibrate', apply='calibrate'),
            doctor._row('workspace', 'template', 'warn', 'drift', 'wuwei init --upgrade', apply='init-upgrade')]
    monkeypatch.setattr(doctor, 'diagnose', lambda section=None: rows)
    for name, command in (('calibrate', 'wuwei calibrate'), ('init-upgrade', 'wuwei init --upgrade')):
        monkeypatch.setitem(doctor.FIXES, name, (command, lambda root, name=name: (f'preview {name}\n', name),
                                                 lambda root, token: applied.append(token) or 0))
    return applied


def widget_args(**changes):
    return Namespace(**{'fix': True, 'json': False, 'widget': True, 'apply': None, 'section': None, **changes})


def test_fix_widget_needs_todays_plan(ws, monkeypatch, capsys):
    from wuwei.guards.decision import check_question
    applied, asked = two_fixes(ws, monkeypatch), []
    assert doctor.run(widget_args(), confirm=asked.append) == 1
    assert 'run wuwei doctor --fix in a host terminal' in capsys.readouterr().err
    assert not asked and not applied
    plan = workspace.day_dir(ws.root) / 'plan.md'
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text('# Plan\n')
    assert doctor.run(widget_args(), confirm=asked.append) == 1
    (built,) = json.loads(capsys.readouterr().out)
    assert built['header'] == 'Fixes' and built['multiSelect'] is True
    assert [o['label'] for o in built['options']] == ['init-upgrade', 'calibrate']
    assert built['options'][0]['description'].startswith('wuwei init --upgrade')
    assert built['options'][1]['description'].startswith('wuwei calibrate')
    assert built['record'] == 'wuwei doctor --fix --apply <labels>'
    assert built['question'].startswith(f'Morning gate (days/{TODAY}/plan.md): ')
    assert check_question({'cwd': str(ws.root), 'tool_name': 'AskUserQuestion', 'tool_input': {'questions': [
        {key: built[key] for key in ('question', 'header', 'options', 'multiSelect')}]}}) == (0, '')
    assert not asked and not applied and not events(ws.root, 'doctor.fixed')


def test_widgets_split_and_skip(ws):
    names = list(doctor.FIXES)
    def sizes(count):
        batch = [(names[i], 'text\n', None) for i in range(count)]
        return [len(w['options']) for w in doctor.widgets(ws.root, batch)]
    assert sizes(0) == [] and sizes(4) == [4] and sizes(5) == [3, 2] and sizes(6) == [3, 3]
    split = doctor.widgets(ws.root, [(names[i], 'text\n', None) for i in range(5)])
    assert [w['question'][-22:] for w in split] == ['doctor fixes (1 of 2)?', 'doctor fixes (2 of 2)?']
    (single,) = doctor.widgets(ws.root, [(names[0], 'text\n', None)])
    assert [o['label'] for o in single['options']] == [names[0], 'Skip']


def test_fix_apply_limits_the_batch(ws, monkeypatch, capsys):
    applied = two_fixes(ws, monkeypatch)
    assert doctor.run(widget_args(widget=False, apply='calibrate'), confirm=lambda digest: True) == 1
    out = capsys.readouterr().out
    assert '[calibrate]' in out and '[init-upgrade]' not in out
    assert applied == ['calibrate'] and len(events(ws.root, 'doctor.fixed')) == 1
    assert doctor.run(widget_args(widget=False, apply='nope'), confirm=lambda digest: True) == 2
    assert 'nope' in capsys.readouterr().err and applied == ['calibrate']
    assert doctor.run(widget_args(widget=False, apply='Skip'), confirm=lambda digest: True) in (0, 1)
    assert applied == ['calibrate']
    for changes in ({'fix': False}, {'fix': False, 'widget': False, 'apply': 'calibrate'}, {'apply': 'calibrate'}):
        assert doctor.run(widget_args(**changes), confirm=lambda digest: True) == 2
    assert applied == ['calibrate']
def test_workspace_config_unknown_key_warns(ws):
    config(ws.root, CONFIG.replace('[adapters]\n', '[adapters]\ncode_hst = "github"\n'))
    found = row(doctor.diagnose(), 'config')
    assert (found['status'], found['value']) == ('warn', 'loads; 1 unknown keys')
    assert found['detail'] == ['config.toml: unknown key adapters.code_hst at line 2; did you mean adapters.code_host?']


def test_in_use_row_names_the_restart(ws):
    sibling = ws.plugin.parent / '0.10.0/.in_use'
    sibling.mkdir(parents=True)
    (sibling / str(os.getpid())).write_text('')
    found = row(doctor.diagnose(), 'in_use')
    assert (found['status'], found['value'], found['fix']) == (
        'warn', 'plugin 0.10.0 running against template 0.11.0: restart Claude Code', integrity.RESTART)

    (sibling / str(os.getpid())).unlink()
    config(ws.root, 'template_version = "0.12.0"\n' + CONFIG)
    found = row(doctor.diagnose(), 'in_use')
    assert (found['status'], found['value']) == (
        'warn', 'plugin 0.11.0 running against template 0.12.0: restart Claude Code')


def legacy_reports(root):
    import hashlib
    rows = [{'server_name': 'docs', 'drift_type': 'tool_poisoning', 'severity': 'high', 'tool_name': 'search'}]
    ziran = root / '.wuwei/ziran'
    for name, body in (('report-a', None), ('report-b', json.dumps(rows, indent=1)), ('report-c', '[]'),
                       ('report-d', '{'), ('report-e', json.dumps(rows))):
        (ziran / name).mkdir(parents=True)
        if body is not None:
            (ziran / name / 'registry-watch-report.json').write_text(body)
    record(root, exit=1, pending=f'.wuwei/days/{TODAY}/decisions/D-1.md', severities=['critical'],
           reports=['.wuwei/ziran/report-e/registry-watch-report.json'])
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return ziran, ziran / 'docs' / (digest + '.json')


def test_mcp_reports_migration(ws, capsys):
    ziran, target = legacy_reports(ws.root)
    body = (ziran / 'report-b/registry-watch-report.json').read_text()
    found = row(doctor.diagnose(), 'mcp reports')
    assert (found['status'], found['apply']) == ('warn', 'mcp-reports')
    fix(lambda digest: True)
    assert 'mcp-reports: exit 0' in capsys.readouterr().out
    assert sorted(p.name for p in ziran.glob('report-*')) == ['report-d', 'report-e']
    assert target.read_text() == body


def test_mcp_reports_migration_bound_to_preview(ws, capsys):
    ziran, target = legacy_reports(ws.root)

    def confirm(digest):
        (ziran / 'report-f').mkdir()
        return True
    fix(confirm)
    out = capsys.readouterr().out
    assert 'changed since the preview; nothing applied' in out and 'mcp-reports: exit 1' in out
    assert (ziran / 'report-a').is_dir() and not target.exists()


def test_no_stray_stderr(ws, monkeypatch, capsys):
    import sys

    def identity(repo, root=None):
        print('git.identity: could not run: git exited 1', file=sys.stderr)
        return Result(2, None, 'git.identity: could not run: git exited 1')
    monkeypatch.setattr(ws.vcs, 'identity', identity)
    doctor.run(Namespace(section=None, json=False, widget=False, apply=None, fix=False))
    assert capsys.readouterr().err == ''


def test_setup_shadow_without_workspace(ws, tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE')
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(integrity, 'measure', lambda: Result(0, 'f' * 64))
    ws.vcs.results['identity'] = Result(2, None, 'git.identity: could not run: git exited 1')
    rows = doctor.diagnose()
    launcher = str(ws.plugin / 'bin/wuwei')
    assert row(rows, 'workspace')['fix'] == f'{launcher} setup --shadow in the directory that holds your repositories'
    found = row(rows, 'git identity')
    assert found['status'] == 'ok' and found['value'] == "not set globally; setup reads each repository's own identity"


def test_fix_lines_use_the_launcher(ws, monkeypatch, capsys):
    from wuwei.commands import setup
    launcher = str(ws.plugin / 'bin/wuwei')
    rows = [doctor._row('workspace', 'config', 'fail', 'x', 'wuwei init --upgrade'),
            doctor._row('install', 'a', 'fail', 'x', 'run bin/wuwei integrity reconfirm in a host terminal'),
            doctor._row('install', 'b', 'fail', 'x', '/plugin install wuwei@wuwei, then /wuwei:wuwei-plan')]
    assert [r['fix'] for r in rows] == [
        f'{launcher} init --upgrade', f'run {launcher} integrity reconfirm in a host terminal',
        '/plugin install wuwei@wuwei, then /wuwei:wuwei-plan']
    assert f'{launcher} init --upgrade' in doctor.render(rows)
    assert setup.ending(rows, [], [])[0] == f'Next: {launcher} init --upgrade'
    monkeypatch.setattr(doctor, 'diagnose', lambda section=None: rows)
    doctor.run(Namespace(section=None, json=True, widget=False, apply=None, fix=False))
    assert json.loads(capsys.readouterr().out)['rows'][0]['fix'] == f'{launcher} init --upgrade'


def test_memory_tiers_row_names_days_consolidate_left_raw(ws, tmp_path):
    found = row(doctor.diagnose(), 'memory tiers')
    assert (found['status'], found['value']) == ('ok', 'within 30 days')
    (ws.root / '.wuwei/days/2026-08-01').mkdir(parents=True)
    found = row(doctor.diagnose(), 'memory tiers')
    assert found['status'] == 'warn' and found['fix'] == f"{ws.plugin / 'bin/wuwei'} consolidate"
    assert found['value'] == '1 raw days older than consolidation.archive_after_days (30); consolidate has not run'
    (ws.root / '.wuwei/days/2026-08-01').rmdir()
    days = ws.root / '.wuwei/days'
    days.rename(tmp_path / 'real-days')
    days.symlink_to(tmp_path / 'real-days')
    assert row(doctor.diagnose(), 'memory tiers')['status'] == 'unmeasured'
