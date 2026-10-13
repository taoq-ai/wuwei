"""wuwei doctor: one report over the existing checks, and --fix for the allow-listed ones."""

from argparse import Namespace
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from fakes.code_host import Fake as CodeHost
from fakes.host import Fake as Host
from fakes.vcs import Fake as Vcs
from wuwei import integrity, registry, state, workspace
from wuwei.__main__ import main
from wuwei.commands import doctor, init
from wuwei.registry import Result

UPGRADE = init.upgrade  # the real one; the ws fixture replaces init.upgrade
REAL_MEASURE = doctor.measure  # the real probes; the ws fixture replaces doctor.measure
REAL_LOAD = registry.load  # the real adapters; the ws fixture replaces registry.load

NOW = '2026-10-03T12:00:00+00:00'
TODAY = '2026-10-03'
REPO = ('[[repos]]\nname = "acme/widget"\npath = "repo"\ndefault_branch = "main"\n'
        'fast_checks = ["ruff check ."]\nidentity = { name = "Ada", email = "ada@example.com" }\n')
IDENTITY = ('\n[owner]\nhandles = ["ada"]\n\n[shepherd]\nlead_login = "ada"\n\n'
            '[shepherd.authors]\n"ada@example.com" = {login = "ada"}\n')
CONFIG = '[adapters]\ncode_host = "github"\n' + REPO + IDENTITY + '\n[telemetry]\nshare = "off"\n'
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
    probes = {name: {'result': 'ok', 'value': 'ok'} for name in doctor.PROBES}
    monkeypatch.setattr(doctor, 'measure', lambda root: probes)
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
    host.hand_over = real('host', {'adapters': {'host': 'local'}}).hand_over  # #645: the real exec
    monkeypatch.setattr(registry, 'load', lambda kind, config: fakes.get(kind) or real(kind, config))
    return SimpleNamespace(root=root, plugin=plugin, bin=bin_dir, probes=probes, service=service,
                           host=host, code_host=code_host, vcs=vcs, installed=installed, mp=monkeypatch)


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
    waiting = {'status': 'waiting'}  # #784
    assert doctor.outcome([ok, waiting]) == 2 and doctor.outcome([waiting, warn]) == 1
    assert doctor.CODES['waiting'] == 2


def test_fix_allow_list_is_pinned():
    # config-set waits for #327's confirmed `config set`.
    assert set(doctor.FIXES) == {'integrity-reconfirm', 'init-upgrade'}


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

    # #848 review F3: an unmeasured or stale cached verdict names the fix that measures again.
    from wuwei import integrity as api
    for reason in ('plugin integrity unmeasured; run bin/wuwei doctor --fix --apply integrity-reconfirm, '
                   'which measures it again', 'plugin integrity unmeasured: gone'):
        ws.mp.setattr(integrity, 'fresh', lambda root, reason=reason: Result(2, reason=reason))
        found = row(doctor.diagnose(), 'integrity')
        assert found['status'] == 'unmeasured' and found['apply'] == 'integrity-reconfirm', found
        assert found['fix'].startswith(W('doctor --fix --apply integrity-reconfirm'))
    assert not [text for text in (api.cached.__code__.co_consts + api.fresh.__code__.co_consts)
                if isinstance(text, str) and re.search(r'run (?:bin/)?wuwei doctor(?! --fix)', text)]
    ws.mp.setattr(integrity, 'fresh', lambda root: Result(2, reason=TRIAL))
    found = row(doctor.diagnose(), 'integrity')
    assert found['status'] == 'fail' and found['value'] == TRIAL
    assert 'wuwei doctor --fix --apply integrity-reconfirm' in found['fix'] and 'reinstall' in found['fix']
    assert 'apply' not in found

    (ws.plugin / 'MANIFEST.sha256.sig').unlink()
    (ws.plugin / '.git').mkdir()
    rows = doctor.diagnose()
    assert row(rows, 'hooks')['value'].startswith('development checkout')
    assert row(rows, 'hooks')['status'] == 'ok'
    found = row(rows, 'integrity')
    assert found['fix'] == W('doctor --fix --apply integrity-reconfirm') and found['apply'] == 'integrity-reconfirm'


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
    (('config', '[adapters]\nruntime = "codex"\n[codex]\ncommand = ["codex"]\n' + REPO), 'codex', 'fail',
     'install the Codex CLI'),
    (('memory', None), 'memory', 'fail', None),
    (('config', '[adapters]\nhost = "none"\n' + REPO), 'memory', 'unmeasured', None),
])
def test_host_rows(ws, change, name, status, fix):
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
    assert names(rows, 'host') == ['gh', 'git identity', 'ziran', 'codex', 'memory']
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'host'), rows
    (ws.bin / 'ziran').unlink()
    config(ws.root, '[adapters]\nscanner = "ziran"\n' + REPO)
    assert row(doctor.diagnose(), 'ziran')['status'] == 'fail'


@pytest.mark.parametrize('floor, percent, status, value', [
    # #898: the memory row names both floors and the share free
    ('', Result(0, 62), 'ok', '8192 MiB (floor 1024 MiB); 62% free (floor off)'),
    ('min_free_memory_pct = 40\n', Result(0, 62), 'ok', '8192 MiB (floor 1024 MiB); 62% free (floor 40%)'),
    ('min_free_memory_pct = 40\n', Result(0, 38), 'fail', '8192 MiB (floor 1024 MiB); 38% free below the floor 40%'),
    ('min_free_memory_pct = 40\n', Result(2, None, 'memory_pressure exited 1'), 'unmeasured',
     '8192 MiB (floor 1024 MiB); memory_pressure exited 1'),
    ('', Result(2, None, 'memory_pressure exited 1'), 'ok', '8192 MiB (floor 1024 MiB); memory_pressure exited 1'),
])
def test_memory_row_reports_the_percentage_floor(ws, floor, percent, status, value):
    config(ws.root, CONFIG + '\n[host]\n' + floor)
    ws.host.results['free_percent'] = percent
    found = row(doctor.diagnose(), 'memory')
    assert (found['status'], found['value']) == (status, value), found
    if status != 'ok':
        assert 'host.min_free_memory_pct' in found['fix']


def codex_plugin(ws):
    script = ws.root.parent / 'codex-plugin/scripts/codex-companion.mjs'
    script.parent.mkdir(parents=True)
    script.write_text('')
    plugins = json.loads(ws.installed.read_text())
    plugins['plugins']['codex@openai-codex'] = [{'scope': 'user', 'installPath': str(script.parents[1])}]
    ws.installed.write_text(json.dumps(plugins))
    return script


def test_empty_codex_command_names_the_installed_companion(ws):
    # #860: an empty codex.command with the codex plugin installed is one warn row naming its script
    script = codex_plugin(ws)
    found = row(doctor.diagnose(), 'codex.command')
    assert (found['section'], found['status']) == ('host', 'warn')
    assert found['value'] == f'codex.command empty: runtime codex unavailable; companion found at {script}'
    assert found['fix'] == W(f"config set codex.command '[\"node\", \"{script}\"]'")
    config(ws.root, CONFIG + f'\n[codex]\ncommand = ["node", "{script}"]\n')
    assert 'codex.command' not in names(doctor.diagnose(), 'host')


@pytest.mark.parametrize('wanted', ['[gates]\nsecond_opinion = "codex:m1"\n',
                                    '[budget.codex]\nfive_hour = 1000\n', 'policy', ''])
def test_empty_codex_command_warns_when_codex_is_wanted(ws, wanted):
    # #860: the config, a codex usage window or today's seat policy names the codex runtime
    stub(ws.bin, 'codex')
    if wanted == 'policy':
        state._write_state(lambda data: data.update(seat_policy={
            'builder': {'runtime': 'claude', 'model': 'opus', 'alternate': 'codex'}}), ws.root)
    else:
        config(ws.root, CONFIG + '\n' + wanted)
    rows = names(doctor.diagnose(), 'host')
    assert ('codex.command' in rows) == bool(wanted)
    if wanted:
        found = row(doctor.diagnose(), 'codex.command')
        assert found['value'] == 'codex.command empty: runtime codex unavailable'
        assert 'codex-companion.mjs' in found['fix']


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
    assert row(rows, 'workspace')['fix'].startswith(W('init --shadow'))
    assert names(rows, 'gates') == names(rows, 'day') == []
    assert names(rows, 'guards') == ['outside workspace']
    assert doctor.outcome(rows) == 1


def test_workspace_rows_healthy(ws):
    rows = doctor.diagnose()
    assert names(rows, 'workspace') == [
        'workspace', 'config', 'template', 'executable', 'acme/widget path', 'acme/widget git',
        'acme/widget branch', 'acme/widget identity', 'acme/widget fast_checks', 'acme/widget spec',
        'calibration', 'drift',
        'guards', 'telemetry']
    assert row(rows, 'guards')['value'] == 'enforce (guards.enforce = true)'
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
     'acme/widget identity', 'fail', None),
    (REPO.replace('["ruff check ."]', '[]'), 'acme/widget fast_checks', 'ok', None),
])
def test_workspace_repository_rows(ws, repo, name, status, apply):
    (ws.root / 'plain').mkdir()
    config(ws.root, '[adapters]\ncode_host = "github"\n' + repo)
    found = row(doctor.diagnose(), name)
    assert found['status'] == status, found
    assert found.get('apply') == apply
    if name.endswith('fast_checks'):  # #600: none configured is a state
        from wuwei import fast_checks
        assert found['value'] == fast_checks.NONE and not found.get('fix')
    if name.endswith('identity'):  # #605: the guard's reason; the fix names what git resolves
        assert found['value'] == 'repos.0.identity is empty or malformed'
        assert found['fix'] == W('config set repos.0.identity \'{name = "Ada", email = "ada@example.com"}\'')


@pytest.mark.parametrize('identity', ['', 'identity = { name = "<name>", email = "<email>" }\n'])
def test_identity_row_without_git_identity_is_the_guards_answer(ws, identity):
    # #605: an empty or malformed identity with no git identity either: doctor gives the
    # guard's reason and fix word for word.
    from wuwei import commit_push
    from wuwei.registry import Result
    config(ws.root, '[adapters]\ncode_host = "github"\n'
           + REPO.replace('identity = { name = "Ada", email = "ada@example.com" }\n', identity))
    ws.vcs.results['identity'] = Result(1, reason='git.identity: no user.name')
    found = row(doctor.diagnose(), 'acme/widget identity')
    reason, fix = commit_push.unset_identity({'name': '', 'email': ''}, 0)
    assert (found['status'], found['value'], found['fix']) == ('fail', reason, W(fix.removeprefix('bin/wuwei ')))


@pytest.mark.parametrize('present', [True, False])
def test_workspace_check_interpreter_row(ws, present):
    # #520: a fast check naming a relative interpreter shows which one it runs.
    config(ws.root, '[adapters]\ncode_host = "github"\n'
           + REPO.replace('["ruff check ."]', '[".venv/bin/python -m pytest -q"]'))
    python = ws.root / 'repo/.venv/bin/python'
    if present:
        python.parent.mkdir(parents=True)
        python.write_text('')
    found = row(doctor.diagnose(), 'acme/widget check interpreter')
    if present:
        assert found['status'] == 'ok' and str(python.resolve()) in found['value']
    else:
        assert found['status'] == 'warn'
        assert '[checks] python' in found['fix'] and '[checks] bootstrap' in found['fix']


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
    found = row(doctor.diagnose(), 'calibration')
    assert (found['status'], found['value'], found['fix']) == ('warn', 'never applied', W('config promote'))
    state.append_event('calibration.drift', {'repo': 'acme/widget', 'changed': ['runner']}, ws.root)
    found = row(doctor.diagnose(), 'drift')
    assert found['status'] == 'warn' and 'apply' not in found and 'acme/widget' in found['value']
    assert found['fix'] == W('config promote')
    # #837: one guards row, ok either way; the log-only text names the switch back.
    config(ws.root, CONFIG.replace('[adapters]', '[guards]\nenforce = false\n[adapters]'))
    found = row(doctor.diagnose(), 'guards')
    assert found['status'] == 'ok' and found['value'].startswith('log only (guards.enforce = false)')
    assert 'bin/wuwei config set guards.enforce true' in found['value']


def test_workspace_telemetry_question_pending(ws):
    # #422: share unset behaves as off, and the choice is still owed; #832: config set makes it.
    config(ws.root, CONFIG.replace('share = "off"', 'share = ""'))
    found = row(doctor.diagnose(), 'telemetry')
    assert (found['status'], found['value'], found['fix']) == (
        'warn', 'sharing not chosen yet', W('config set telemetry.share \'"anonymous"\' (or "attributed" or "off")'))
    config(ws.root, CONFIG.replace('share = "off"', 'enabled = false'))
    assert row(doctor.diagnose(), 'telemetry')['status'] == 'ok'


def test_workspace_retired_shadow_mode(ws, monkeypatch):
    config(ws.root, CONFIG.replace('[adapters]', '[guards]\nmode = "shadow"\n'
                                                 'shadow_since = "2026-09-30"\n[adapters]'))
    monkeypatch.setattr(init, 'upgrade', UPGRADE)
    found = row(doctor.diagnose(), 'template')
    assert found['status'] == 'warn' and found['apply'] == 'init-upgrade'
    assert ('Would upgrade config.toml: guards.enforce = false (was guards.mode = "shadow")'
            in found['detail'])


def test_gates_rows(ws):
    ws.code_host.results['protection'] = protected(**CLASSIC_404)
    found = row(doctor.diagnose(), 'config check')
    assert (found['status'], found['value']) == ('fail', 'exit 1')
    assert CLASSIC_LINE in found['detail']
    assert any(line.startswith('acme/widget main: required reviews: missing (') for line in found['detail'])

    ws.code_host.results['protection'] = Result(2, None, 'github.protection: could not run')
    assert row(doctor.diagnose(), 'config check')['status'] == 'unmeasured'

    ws.code_host.results['protection'] = protected()
    assert row(doctor.diagnose(), 'config check')['status'] == 'ok'



def test_a_protection_finding_outranks_a_rate_limit(ws):
    # #867 F2: one repository rate limited and another missing a setting: the finding is the row.
    (ws.root / 'paper/.git').mkdir(parents=True)
    config(ws.root, CONFIG + REPO.replace('acme/widget', 'acme/paper').replace('"repo"', '"paper"'))
    limited = Result(2, None, 'github.protection: could not run: GitHub rate limit until 14:05:00 UTC '
                     '(0 of 5000 core calls left); retry after it')
    finding = protected(**CLASSIC_404)
    ws.code_host.protection = lambda repo, branch, root=None: limited if repo == 'acme/paper' else finding
    found = row(doctor.diagnose(), 'config check')
    assert found['status'] == 'unmeasured' and any('missing (' in line for line in found['detail'])
    ws.code_host.protection = lambda repo, branch, root=None: limited if repo == 'acme/paper' else protected()
    assert row(doctor.diagnose(), 'config check')['status'] == 'waiting'

def protection_calls(ws):
    return sum(call[0] == 'protection' for call in ws.code_host.calls)


def test_protection_is_read_once_a_day_when_clean(ws):
    # #867: findings and errors are read again, so the owner's fix shows; a clean read is kept.
    ws.code_host.results['protection'] = protected(**CLASSIC_404)
    doctor.diagnose()
    doctor.diagnose()
    assert protection_calls(ws) == 2
    ws.code_host.results['protection'] = protected()
    assert row(doctor.diagnose(), 'config check')['status'] == 'ok'
    assert row(doctor.diagnose(), 'config check')['status'] == 'ok'
    assert protection_calls(ws) == 3
    kept = json.loads((workspace.day_dir(ws.root) / 'protection.json').read_text())
    assert list(kept) == ['acme/widget@main']
    # A changed requirement is judged against the kept read, with no call.
    config(ws.root, CONFIG.replace('identity =', 'review_required_checks = ["absent"]\nidentity ='))
    assert row(doctor.diagnose(), 'config check')['status'] == 'fail'
    assert protection_calls(ws) == 3


@pytest.mark.parametrize('kept', ['not json', '[]', '{"acme/widget@main": "yes"}'])
def test_unreadable_protection_cache_reads_again(ws, kept):
    path = workspace.day_dir(ws.root) / 'protection.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(kept)
    assert row(doctor.diagnose(), 'config check')['status'] == 'ok'
    assert protection_calls(ws) == 1


def test_rate_limited_doctor_never_waits(ws, monkeypatch):
    # #867 acceptance: every GitHub call is rate limited with a reset 100 s out; doctor waits for
    # none, the gh and config check rows wait, and the override does not outlive the run.
    import subprocess
    from fakes.replay import NOW, hms, install_clock, limits
    slept = install_clock(monkeypatch)
    real_run, real_load = subprocess.run, REAL_LOAD
    fakes = {'host': ws.host, 'vcs': ws.vcs}
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: fakes.get(kind) or real_load(kind, cfg))

    def run(argv, **kwargs):
        if argv[:1] != ['gh']:
            return real_run(argv, **kwargs)
        if argv[1:3] == ['api', 'rate_limit']:
            return subprocess.CompletedProcess(argv, 0, limits(0, 4000, NOW + 100), '')
        if argv[1:3] == ['auth', 'status']:
            return subprocess.CompletedProcess(argv, 1, 'The token in keyring is invalid.', '')
        return subprocess.CompletedProcess(argv, 1, '', 'gh: API rate limit exceeded. (HTTP 403)')
    monkeypatch.setattr(subprocess, 'run', run)
    monkeypatch.delenv('WUWEI_RATE_LIMIT_WAIT', raising=False)
    rows = doctor.diagnose()
    assert slept == []
    for name in ('gh', 'config check'):
        found = row(rows, name)
        assert found['status'] == 'waiting', found
    assert row(rows, 'gh')['value'].startswith(f'rate limited until {hms(NOW + 100)} UTC (0 of 5000 core')
    assert 'WUWEI_RATE_LIMIT_WAIT' not in os.environ

def test_day_rows(ws):
    rows = doctor.diagnose()
    assert names(rows, 'day') == ['state', 'stuck seats', 'traces', 'untraced subagents', 'tracker']
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'day'), rows
    assert row(rows, 'untraced subagents')['value'] == 'none today'
    # #676: a subagent stop that matched no seat is named, with the way to register one.
    state.append_event('subagent.untraced', {'agent_type': 'Explore', 'agent_id': 'a1', 'reason': 'no seat'},
                       ws.root)
    found = row(doctor.diagnose(), 'untraced subagents')
    assert (found['status'], found['value']) == ('warn', '1 stopped with no seat today')
    assert 'seat start --role <role> --adhoc' in found['fix']
    ws.probes['seats'] = {'result': 'failed', 'value': 'dead: builder; run wuwei seat stop builder --verdict <file>'}
    found = row(doctor.diagnose(), 'stuck seats')
    assert found['status'] == 'fail' and 'wuwei seat stop' in found['fix']
    ws.probes['seats'] = {'result': 'ok', 'value': 'none stuck'}

    ws.probes['state'] = {'result': 'failed', 'value': 'bad state'}
    found = row(doctor.diagnose(), 'state')
    assert found['status'] == 'fail' and 'recover' not in found['fix']
    state.append_event('security.finding', {'reason': 'secret in diff'}, ws.root)
    found = row(doctor.diagnose(), 'security.finding')
    assert found['status'] == 'fail' and 'wuwei next' not in found['fix']
    assert 'security.finding' in found['fix'] and 'events.jsonl' in found['fix']


def test_day_probes_read_state_and_the_seat_ledger(ws):
    # #847: no heartbeat; doctor reads the day and the seat ledger itself.
    probes = REAL_MEASURE(ws.root)
    assert (probes['state']['result'], probes['seats']) == ('ok', {'result': 'ok', 'value': 'none stuck'})
    assert set(probes) == {'refused', 'allowed', 'state_write', 'state', 'seats'}


def test_guards_rows(ws):
    rows = doctor.diagnose()
    assert names(rows, 'guards') == ['refused', 'allowed', 'state_write', 'outside workspace']
    assert all(r['status'] == 'ok' for r in rows if r['section'] == 'guards'), rows
    (calls, cwd), = ws.service.calls
    (argv, text), = calls
    payload = json.loads(text)
    assert argv == ('hook', 'PreToolUse')
    assert not Path(cwd).resolve().is_relative_to(ws.root.resolve()) and payload['cwd'] == str(cwd)
    assert payload['session_id'] == 'wuwei-probe'
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


def test_hook_probes_through_the_launcher(ws):
    # #847: a force push the edges refuse, a Read they allow, a write to the day log the records
    # guard refuses; exit codes only, no timings.
    ws.service.results = [(2, 'refused', 30), (0, '', 30), (2, 'refused', 30)]
    probes = REAL_MEASURE(ws.root)
    assert {name: probes[name] for name in ('refused', 'allowed', 'state_write')} == {
        name: {'result': 'ok', 'value': f'exit {code}'} for name, code in
        (('refused', 2), ('allowed', 0), ('state_write', 2))}
    (calls, _), = ws.service.calls
    inputs = [json.loads(text)['tool_input'] for _, text in calls]
    assert inputs[0] == {'command': 'git push --force origin main'}
    assert inputs[2]['file_path'].endswith('events.jsonl')
    ws.service.results = [(0, '', 30), (0, '', 30), (2, 'refused', 30)]
    assert REAL_MEASURE(ws.root)['refused'] == {'result': 'failed', 'value': 'exit 0'}


def test_outside_probe_through_launcher(monkeypatch):
    # One real smoke of the outside-workspace probe through bin/wuwei (#323).
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert row(doctor._guards(None, None), 'outside workspace')['status'] == 'ok'


def test_healthy_workspace_exits_zero(ws, capsys):
    def listing():  # #867: the day's clean protection read is the one file doctor keeps
        return {p: p.stat().st_mtime_ns for p in (ws.root / '.wuwei').rglob('*')
                if p.is_file() and p.name not in ('state.lock', 'protection.json')}
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
    ws.code_host.results['protection'] = protected(**CLASSIC_404)
    trial = CONFIG.replace('["ruff check ."]', '[]')
    config(ws.root, 'repos = []\n' + trial)

    assert main(['doctor']) == 1
    out = capsys.readouterr().out
    assert 'wuwei doctor --fix --apply integrity-reconfirm' in out and f"fix: {W('init --upgrade')}" in out
    assert 'delete that line before using [[repos]] tables' in out

    config(ws.root, trial)
    assert main(['doctor']) == 1
    out = capsys.readouterr().out
    for text in (CLASSIC_LINE, 'acme/widget main: required reviews: missing ('):
        assert text in out, text

    monkeypatch.setattr(integrity, 'fresh', lambda root: Result(0))
    config(ws.root, CONFIG)
    ws.code_host.results['protection'] = protected()
    assert main(['doctor']) == 0, capsys.readouterr().out


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
    assert rows['shepherd.authors']['fix'].startswith('add "<email>" = {login = "<login>"')
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
    monkeypatch.setattr(doctor, 'measure', refuse)
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
            'run wuwei doctor --fix --apply integrity-reconfirm')


def fix(confirm):
    return doctor.run(Namespace(fix=True, json=False, widget=False, apply=None, section=None), confirm=confirm)


def upgrade_pending(ws):
    """One allow-listed fix pending: init --upgrade has a change; applies are recorded."""
    applied = []

    def upgrade(args):
        if not args.dry_run:
            applied.append(args.path)
        print('Would upgrade config.toml: add x')
        return 0
    ws.mp.setattr(init, 'upgrade', upgrade)
    return applied


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
    assert '[integrity-reconfirm] wuwei doctor --fix --apply integrity-reconfirm' in shown and 'f' * 64 in shown
    assert len(digest) == 12
    assert events(ws.root, 'doctor.fixed') == [{'fix': 'integrity-reconfirm', 'exit': 0}]
    out = capsys.readouterr().out
    assert 'integrity-reconfirm: exit 0' in out
    assert out.splitlines()[-1] == 'doctor: ok'


def test_fix_applies_only_the_allow_list(ws, monkeypatch, capsys):
    rows = [doctor._row('workspace', 'guards', 'warn', 'log only', 'set guards.enforce = true'),
            doctor._row('day', 'state', 'fail', 'bad', 'wuwei doctor')]
    monkeypatch.setattr(doctor, 'diagnose', lambda section=None: rows)
    asked = []
    assert fix(asked.append) == 1
    out = capsys.readouterr().out
    assert not asked and 'Nothing to apply' in out
    notes = out.split('Not applied:', 1)[1]
    for text in ('set guards.enforce = true',):
        assert text in notes
    assert not events(ws.root, 'doctor.fixed')


def test_fix_wrong_digest_applies_nothing(ws, monkeypatch, capsys):
    applied = upgrade_pending(ws)
    assert fix(lambda digest: False) == 1
    assert 'wuwei doctor: declined; nothing applied' in capsys.readouterr().err
    assert not applied and not events(ws.root, 'doctor.fixed')


def test_fix_asks_the_owner_step_card(ws, monkeypatch, capsys):
    # #831: no terminal; the owner's Yes on the printed Owner step card applies the batch.
    from fakes import owner
    applied = upgrade_pending(ws)
    assert fix(None) == 1
    err = capsys.readouterr().err
    assert 'Owner step: bin/wuwei doctor --fix (' in err and 'host terminal' not in err
    assert not applied and not events(ws.root, 'doctor.fixed')
    owner.answer_card(ws.root, err)
    fix(None)
    assert applied and events(ws.root, 'doctor.fixed') == [{'fix': 'init-upgrade', 'exit': 0}]


def test_fix_changed_since_preview(ws, monkeypatch, capsys):
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
    assert events(ws.root, 'doctor.fixed') == [{'fix': 'init-upgrade', 'exit': 1}]


def test_fix_nothing_to_apply(ws, capsys):
    asked = []
    assert fix(asked.append) == 0
    assert 'Nothing to apply' in capsys.readouterr().out and not asked


def two_fixes(ws, monkeypatch):
    """integrity-reconfirm and init-upgrade due, each with a fake preview and an apply that records its call."""
    applied = []
    rows = [doctor._row('install', 'integrity', 'warn', 'old', 'wuwei doctor --fix --apply integrity-reconfirm', apply='integrity-reconfirm'),
            doctor._row('workspace', 'template', 'warn', 'drift', 'wuwei init --upgrade', apply='init-upgrade')]
    monkeypatch.setattr(doctor, 'diagnose', lambda section=None: rows)
    for name, command in (('integrity-reconfirm', 'wuwei doctor --fix --apply integrity-reconfirm'), ('init-upgrade', 'wuwei init --upgrade')):
        monkeypatch.setitem(doctor.FIXES, name, (command, lambda root, name=name: (f'preview {name}\n', name),
                                                 lambda root, token: applied.append(token) or 0))
    return applied


def widget_args(**changes):
    return Namespace(**{'fix': True, 'json': False, 'widget': True, 'apply': None, 'section': None, **changes})


def test_fix_widget_prints_the_owner_step_card(ws, monkeypatch, capsys):
    """#831 F5: one card per fix batch: the widget is the Owner step card the fix asks."""
    from fakes import owner
    applied, asked = two_fixes(ws, monkeypatch), []
    assert doctor.run(widget_args(), confirm=asked.append) in (0, 1)
    (built,) = json.loads(capsys.readouterr().out)
    assert built['header'] == 'Owner step' and built['multiSelect'] is False
    assert built['question'].startswith('Owner step: bin/wuwei doctor --fix (')
    assert built['record'] == 'bin/wuwei doctor --fix'
    assert '[integrity-reconfirm] wuwei doctor --fix --apply integrity-reconfirm' in built['options'][0]['description']
    assert not asked and not applied and not events(ws.root, 'doctor.fixed')
    assert doctor.run(widget_args(widget=False)) == 1
    refusal = capsys.readouterr().err
    assert json.dumps(built) in refusal
    owner.answer_card(ws.root, refusal)
    doctor.run(widget_args(widget=False))
    assert sorted(applied) == ['init-upgrade', 'integrity-reconfirm']


def test_fix_apply_limits_the_batch(ws, monkeypatch, capsys):
    applied = two_fixes(ws, monkeypatch)
    assert doctor.run(widget_args(widget=False, apply='integrity-reconfirm'), confirm=lambda digest: True) == 1
    out = capsys.readouterr().out
    assert '[integrity-reconfirm]' in out and '[init-upgrade]' not in out
    assert applied == ['integrity-reconfirm'] and len(events(ws.root, 'doctor.fixed')) == 1
    assert doctor.run(widget_args(widget=False, apply='nope'), confirm=lambda digest: True) == 2
    assert 'nope' in capsys.readouterr().err and applied == ['integrity-reconfirm']
    assert doctor.run(widget_args(widget=False, apply='Skip'), confirm=lambda digest: True) == 2
    assert applied == ['integrity-reconfirm']
    for changes in ({'fix': False}, {'fix': False, 'widget': False, 'apply': 'integrity-reconfirm'}, {'apply': 'integrity-reconfirm'}):
        assert doctor.run(widget_args(**changes), confirm=lambda digest: True) == 2
    assert applied == ['integrity-reconfirm']
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
        'warn', 'restart Claude Code: hooks 0.10.0 still running (plugin 0.11.0 installed)', integrity.RESTART)

    (sibling / str(os.getpid())).unlink()
    config(ws.root, 'template_version = "0.12.0"\n' + CONFIG)
    found = row(doctor.diagnose(), 'in_use')
    assert (found['status'], found['value']) == (
        'warn', 'restart Claude Code: hooks 0.11.0 still running (plugin 0.12.0 installed)')


def test_no_stray_stderr(ws, monkeypatch, capsys):
    import sys

    def identity(repo, root=None):
        print('git.identity: could not run: git exited 1', file=sys.stderr)
        return Result(2, None, 'git.identity: could not run: git exited 1')
    monkeypatch.setattr(ws.vcs, 'identity', identity)
    doctor.run(Namespace(section=None, json=False, widget=False, apply=None, fix=False))
    assert capsys.readouterr().err == ''


def test_init_shadow_without_workspace(ws, tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE')
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(integrity, 'measure', lambda: Result(0, 'f' * 64))
    ws.vcs.results['identity'] = Result(2, None, 'git.identity: could not run: git exited 1')
    rows = doctor.diagnose()
    launcher = str(ws.plugin / 'bin/wuwei')
    assert row(rows, 'workspace')['fix'] == f'{launcher} init --shadow in the directory that holds your repositories'
    found = row(rows, 'git identity')
    assert found['status'] == 'ok' and found['value'] == 'not set globally; repositories set their own'


def test_fix_lines_use_the_launcher(ws, monkeypatch, capsys):
    launcher = str(ws.plugin / 'bin/wuwei')
    rows = [doctor._row('workspace', 'config', 'fail', 'x', 'wuwei init --upgrade'),
            doctor._row('install', 'a', 'fail', 'x', 'run bin/wuwei doctor --fix --apply integrity-reconfirm'),
            doctor._row('install', 'b', 'fail', 'x', '/plugin install wuwei@wuwei, then /wuwei:wuwei-plan')]
    assert [r['fix'] for r in rows] == [
        f'{launcher} init --upgrade', f'run {launcher} doctor --fix --apply integrity-reconfirm',
        '/plugin install wuwei@wuwei, then /wuwei:wuwei-plan']
    assert f'{launcher} init --upgrade' in doctor.render(rows)
    monkeypatch.setattr(doctor, 'diagnose', lambda section=None: rows)
    doctor.run(Namespace(section=None, json=True, widget=False, apply=None, fix=False))
    assert json.loads(capsys.readouterr().out)['rows'][0]['fix'] == f'{launcher} init --upgrade'


def test_tracker_row(ws):
    from fakes.tracker import Fake
    assert row(doctor.diagnose(), 'tracker')['status'] == 'ok'
    config(ws.root, CONFIG.replace('code_host = "github"\n', 'code_host = "github"\ntracker = "linear"\n'))
    tracker = Fake({'backlog': Result(2, reason='LINEAR_API_KEY is missing')})
    real = registry.load
    ws.mp.setattr(registry, 'load', lambda kind, cfg: tracker if kind == 'tracker' else real(kind, cfg))
    found = row(doctor.diagnose(), 'tracker')
    assert found['status'] == 'fail' and 'LINEAR_API_KEY' in found['value']
    assert 'LINEAR_API_KEY' in found['fix']
    assert 'bin/wuwei config set adapters.tracker \'"none"\'' in found['fix']
    tracker.results['backlog'] = Result(0, [])
    assert row(doctor.diagnose(), 'tracker')['status'] == 'ok'


def test_tracker_row_on_a_rate_limit(ws):
    # #738: a rate limit is not a broken tracker; the row says when to look again.
    from fakes.tracker import Fake
    config(ws.root, CONFIG.replace('code_host = "github"\n', 'code_host = "github"\ntracker = "github"\n'))
    reason = ('github.backlog: could not run: GitHub rate limit until 14:05:00 UTC '
              '(0 of 5000 graphql calls left); retry after it')
    tracker = Fake({'backlog': Result(2, reason=reason)})
    real = registry.load
    ws.mp.setattr(registry, 'load', lambda kind, cfg: tracker if kind == 'tracker' else real(kind, cfg))
    found = row(doctor.diagnose(), 'tracker')
    assert found['status'] == 'waiting'  # #784
    assert found['value'] == ('rate limited until 14:05:00 UTC (0 of 5000 graphql calls left); '
                              'retry after it')
    assert 'wait until the reset' in found['fix']


def test_gh_row_on_a_rate_limit(ws, capsys):
    # #784: a rate limit on gh auth is a wait, never missing auth.
    ws.code_host.results['auth_status'] = Result(2, reason='GitHub rate limit until 14:05:00 UTC '
                                                 '(5000 of 5000 core calls left); retry after it')
    rows = doctor.diagnose()
    found = row(rows, 'gh')
    assert found['status'] == 'waiting'
    assert found['value'] == 'rate limited until 14:05:00 UTC (5000 of 5000 core calls left); retry after it'
    assert 'wait until the reset' in found['fix']
    assert not any('gh auth: missing' in r['value'] or 'gh auth login' in r.get('fix', '') for r in rows)
    assert row(rows, 'config check')['status'] == 'waiting'  # #867: its gh auth line names the limit
    assert main(['doctor']) == 2
    assert capsys.readouterr().out.splitlines()[-1].endswith('2 waiting')
def test_tracker_labels_row(ws):
    """#670: doctor lists the lifecycle labels the tracker lacks; it creates none."""
    from fakes.tracker import Fake
    assert 'tracker labels' not in names(doctor.diagnose(), 'day')
    config(ws.root, CONFIG.replace('code_host = "github"\n', 'code_host = "github"\ntracker = "github"\n'))
    tracker = Fake({'labels': Result(0, {'created': [], 'missing': ['In Review']}),
                    'backlog': Result(0, [])})
    real = registry.load
    ws.mp.setattr(registry, 'load', lambda kind, cfg: tracker if kind == 'tracker' else real(kind, cfg))
    found = row(doctor.diagnose(), 'tracker labels')
    assert (found['section'], found['status'], found['value'], found['fix']) == (
        'day', 'warn', 'missing: "In Review"', W('init --upgrade'))
    assert 'apply' not in found
    assert [call[:2] for call in tracker.calls if call[0] == 'labels'] == [('labels', (False,))]
    tracker.results['labels'] = Result(0, {'created': [], 'missing': []})
    found = row(doctor.diagnose(), 'tracker labels')
    assert (found['status'], found['value']) == ('ok', 'none missing')
    tracker.results['labels'] = Result(2, reason='github.labels: could not run: offline')
    found = row(doctor.diagnose(), 'tracker labels')
    assert (found['status'], found['value']) == ('unmeasured', 'github.labels: could not run: offline')


@pytest.mark.parametrize('auth, fix', [
    ('', 'set GITHUB_TRACKER_TOKEN in .wuwei/env, or bin/wuwei config set tracker.auth \'"gh"\' to use '
         'your gh login, or bin/wuwei config set adapters.tracker \'"none"\''),
    ('[tracker]\nauth = "gh"\n', 'run gh auth status (with tracker.board: gh auth refresh -s project), '
                                 'or bin/wuwei config set adapters.tracker \'"none"\'')])
def test_github_tracker_row_names_the_auth_fix(ws, auth, fix):
    from fakes.tracker import Fake
    config(ws.root, CONFIG.replace('code_host = "github"\n', 'code_host = "github"\ntracker = "github"\n') + auth)
    tracker = Fake({'backlog': Result(2, reason='github.backlog: could not run: HTTP 401: credential rejected')})
    real = registry.load
    ws.mp.setattr(registry, 'load', lambda kind, cfg: tracker if kind == 'tracker' else real(kind, cfg))
    found = row(doctor.diagnose(), 'tracker')
    assert found['status'] == 'fail' and 'HTTP 401' in found['value']
    assert re.sub(r'\S*/bin/wuwei', 'bin/wuwei', found['fix']) == fix


class HandedOver(Exception):
    pass


def handing(monkeypatch):
    def fake(path, argv, env):
        raise HandedOver(path, argv, env)
    monkeypatch.setattr(doctor.os, 'execve', fake)


def copy(tmp_path, name='other'):
    """A second install built like the ws fixture's (#645)."""
    plugin = tmp_path / name
    for part in ('bin', 'hooks', '.claude-plugin'):
        (plugin / part).mkdir(parents=True)
    stub(plugin / 'bin', 'wuwei')
    (plugin / 'hooks/hooks.json').write_text(json.dumps({'hooks': {'PreToolUse': []}}))
    (plugin / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'wuwei', 'version': '0.11.0'}))
    (plugin / 'MANIFEST.sha256.sig').write_text('sig\n')
    return plugin


def options(**changes):
    return Namespace(**{'fix': False, 'json': False, 'widget': False, 'apply': None, 'section': None, **changes})


@pytest.mark.parametrize('changes, flags', [
    ({'json': True}, ['--json']), ({'fix': True}, ['--fix']),
    ({'fix': True, 'widget': True}, ['--fix', '--widget']),
    ({'fix': True, 'apply': 'integrity-reconfirm'}, ['--fix', '--apply', 'integrity-reconfirm']),
    ({'section': 'pr-flow'}, ['--section', 'pr-flow'])])
def test_doctor_hands_over_to_the_pointer(ws, tmp_path, monkeypatch, changes, flags):
    """#645: any copy runs the doctor of the install .wuwei/executable names, same options."""
    other = copy(tmp_path)
    monkeypatch.setattr(integrity, 'PLUGIN', other)
    handing(monkeypatch)
    with pytest.raises(HandedOver) as handed:
        doctor.run(options(**changes))
    path, argv, env = handed.value.args
    assert path == str(ws.plugin / 'bin/wuwei')
    assert argv == [path, 'doctor', *flags]
    assert env['WUWEI_DOCTOR_FROM'] == str(other / 'bin/wuwei')
    assert env['WUWEI_WORKSPACE'] == str(ws.root)


def _pointer(ws, tmp_path, monkeypatch, case):
    pointer = ws.root / '.wuwei/executable'
    if case == 'symlinked directory':
        (tmp_path / 'link').symlink_to(ws.plugin)
        pointer.write_text(f"{tmp_path / 'link/bin/wuwei'}\n")
    elif case == 'missing pointer':
        pointer.unlink()
    elif case == 'missing file':
        pointer.write_text(f"{tmp_path / 'gone/bin/wuwei'}\n")
    elif case == 'not executable':
        other = copy(tmp_path)
        (other / 'bin/wuwei').chmod(0o644)
        pointer.write_text(f"{other / 'bin/wuwei'}\n")
    elif case == 'already handed over':
        pointer.write_text(f"{copy(tmp_path) / 'bin/wuwei'}\n")
        monkeypatch.setenv('WUWEI_DOCTOR_FROM', str(tmp_path / 'first/bin/wuwei'))
    elif case == 'no workspace':
        pointer.write_text(f"{copy(tmp_path) / 'bin/wuwei'}\n")
        monkeypatch.delenv('WUWEI_WORKSPACE')
        monkeypatch.chdir(tmp_path)
    elif case == 'relative path':
        stub(ws.root, 'evil')
        pointer.write_text('evil\n')
        monkeypatch.chdir(ws.root)
    elif case == 'not a launcher':
        stub(tmp_path, 'evil')
        pointer.write_text(f"{tmp_path / 'evil'}\n")
    elif case == 'symlinked pointer':
        (tmp_path / 'pointer').write_text(f"{copy(tmp_path) / 'bin/wuwei'}\n")
        pointer.unlink()
        pointer.symlink_to(tmp_path / 'pointer')


@pytest.mark.parametrize('case', ['running launcher', 'symlinked directory', 'missing pointer', 'missing file',
                                  'not executable', 'already handed over', 'no workspace',
                                  'relative path', 'not a launcher', 'symlinked pointer'])
def test_doctor_reports_here_without_a_hand_over(ws, tmp_path, monkeypatch, capsys, case):
    _pointer(ws, tmp_path, monkeypatch, case)
    monkeypatch.setattr(doctor.os, 'execve', lambda *a: pytest.fail('handed over'))
    if case == 'no workspace':
        monkeypatch.setattr(integrity, 'measure', lambda: Result(0, 'f' * 64))
    doctor.run(options(json=True))
    rows = json.loads(capsys.readouterr().out)['rows']
    assert case == 'already handed over' or not [r for r in rows if r['name'] == 'invoked']


def test_doctor_with_a_confirm_callback_never_hands_over(ws, tmp_path, monkeypatch):
    (ws.root / '.wuwei/executable').write_text(f"{copy(tmp_path) / 'bin/wuwei'}\n")
    monkeypatch.setattr(doctor.os, 'execve', lambda *a: pytest.fail('handed over'))
    assert doctor.run(options(fix=True, widget=True), confirm=lambda digest: True) in (0, 1)


def test_failed_hand_over_reports_here_with_a_warn_row(ws, tmp_path, monkeypatch, capsys):
    other = copy(tmp_path)
    monkeypatch.setattr(integrity, 'PLUGIN', other)
    old(other)
    ws.installed.write_text(json.dumps({'version': 2, 'plugins': {
        'wuwei@wuwei': [{'scope': 'user', 'installPath': str(other)}]}}))

    def fail(path, argv, env):
        raise OSError(8, 'Exec format error')
    monkeypatch.setattr(doctor.os, 'execve', fail)
    assert doctor.run(options(json=True)) == 1
    rows = json.loads(capsys.readouterr().out)['rows']
    pointer = str(ws.plugin / 'bin/wuwei')
    found = row(rows, 'invoked')
    assert (found['section'], found['status']) == ('install', 'warn')
    assert pointer in found['value'] and 'OSError' in found['value'] and str(other / 'bin/wuwei') in found['value']
    assert 'Exec format error' not in json.dumps(found)
    assert found['fix'] == f'{pointer} doctor'
    assert [r for r in rows if r['name'] != 'invoked'] == doctor.diagnose()


def test_hand_over_runs_the_pointer_launcher(tmp_path):
    """One real process: python3 -P -m wuwei doctor replaces itself with the pointer's launcher."""
    import subprocess
    import sys
    repository = Path(__file__).resolve().parents[1]
    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    pointer = tmp_path / 'stub/bin/wuwei'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('#!/bin/sh\necho "$WUWEI_DOCTOR_FROM|$*"\n')
    pointer.chmod(0o755)
    (root / '.wuwei/executable').write_text(f'{pointer}\n')
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(repository / 'cli'), str(repository)]),
           'WUWEI_WORKSPACE': str(root)}
    env.pop('WUWEI_DOCTOR_FROM', None)
    done = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'doctor', '--json'], cwd=root, env=env,
                          capture_output=True, text=True, timeout=60)
    assert (done.returncode, done.stdout) == (0, f"{repository / 'bin/wuwei'}|doctor --json\n"), done.stderr


def test_either_copy_prints_the_same_findings(ws, tmp_path, monkeypatch):
    """#645: the handed-over doctor prints the direct rows plus one ok row naming the copies."""
    other = copy(tmp_path)
    third = tmp_path / 'third'
    verdict = json.loads((ws.root / '.wuwei/integrity/verdict.json').read_text())
    integrity._record(ws.root, 'verdict.json', {**verdict, 'plugin': str(third)})
    direct = doctor.diagnose()
    monkeypatch.setenv('WUWEI_DOCTOR_FROM', str(other / 'bin/wuwei'))
    handed = doctor.diagnose()
    assert [r for r in handed if r['name'] != 'invoked'] == direct
    found = row(handed, 'invoked')
    assert (found['section'], found['status']) == ('install', 'ok')
    for path in (other / 'bin/wuwei', ws.plugin / 'bin/wuwei', third):
        assert str(path) in found['value'], path
    assert doctor.outcome(handed) == doctor.outcome(direct)

    integrity._record(ws.root, 'verdict.json', verdict)
    assert 'unknown' in row(doctor.diagnose(), 'invoked')['value']

    monkeypatch.setenv('WUWEI_DOCTOR_FROM', str(ws.plugin / 'bin/wuwei'))
    assert not [r for r in doctor.diagnose() if r['name'] == 'invoked']

    monkeypatch.delenv('WUWEI_DOCTOR_FROM')
    monkeypatch.setattr(integrity, 'PLUGIN', other)
    handing(monkeypatch)
    with pytest.raises(HandedOver) as handed_over:
        doctor.run(options(json=True))
    assert handed_over.value.args[0] == str(ws.plugin / 'bin/wuwei')


def test_doctor_names_the_hooks_copy_when_it_differs(ws, tmp_path):
    """#645 F3: run from the pointer copy while the hooks measured another: a warn row names both."""
    verdict = json.loads((ws.root / '.wuwei/integrity/verdict.json').read_text())
    assert not [r for r in doctor.diagnose() if r['name'] == 'hooks copy']
    integrity._record(ws.root, 'verdict.json', {**verdict, 'plugin': str(ws.plugin)})
    assert not [r for r in doctor.diagnose() if r['name'] == 'hooks copy']
    third = tmp_path / 'third'
    integrity._record(ws.root, 'verdict.json', {**verdict, 'plugin': str(third)})
    found = row(doctor.diagnose(), 'hooks copy')
    assert (found['section'], found['status']) == ('install', 'warn')
    assert str(third) in found['value'] and str(ws.plugin) in found['value']
    assert found['fix'] == f"{third / 'bin/wuwei'} doctor"
def second_install(ws, tmp_path):
    """#601: a release extraction B beside the registered install A (ws.plugin)."""
    b = tmp_path / 'extracted'
    for name in ('bin', 'hooks', '.claude-plugin'):
        (b / name).mkdir(parents=True)
    stub(b / 'bin', 'wuwei')
    (b / 'hooks/hooks.json').write_text(json.dumps({'hooks': {'PreToolUse': []}}))
    (b / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'wuwei', 'version': '0.11.0'}))
    (b / 'MANIFEST.sha256.sig').write_text('sig\n')
    ws.mp.setattr(integrity, 'PLUGIN', b)
    return b


def test_hooks_row_reads_the_registration_from_either_launcher(ws, tmp_path):
    second_install(ws, tmp_path)
    found = row(doctor.diagnose(), 'hooks')
    assert (found['status'], found['value']) == ('ok', 'registered in Claude Code')


def test_two_installs_named_with_the_fix(ws, tmp_path):
    a = ws.plugin
    b = second_install(ws, tmp_path)
    (ws.root / '.wuwei/executable').write_text(f"{b / 'bin/wuwei'}\n")
    rows = doctor.diagnose()
    found = row(rows, 'installs')
    assert found['status'] == 'warn' and found['section'] == 'install'
    assert f'{a} (registered' in found['value']
    assert f'{b} (this launcher, named by .wuwei/executable)' in found['value']
    assert found['fix'].startswith(f"{a / 'bin/wuwei'} init --upgrade") and str(b) in found['fix']
    executable = row(rows, 'executable')
    assert executable['status'] == 'fail' and str(a / 'bin/wuwei') in executable['value']
    (ws.root / '.wuwei/executable').write_text(f"{a / 'bin/wuwei'}\n")
    rows = doctor.diagnose()
    assert row(rows, 'executable')['status'] == 'ok'
    ws.mp.setattr(integrity, 'PLUGIN', a)
    assert 'installs' not in names(doctor.diagnose(), 'install')

