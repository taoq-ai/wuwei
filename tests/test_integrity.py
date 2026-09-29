"""Offline integrity acceptance and adapter boundary tests."""

from argparse import Namespace
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from wuwei import registry

ROOT = Path(__file__).resolve().parents[1]


def core():
    assert (ROOT / 'cli/wuwei/integrity.py').is_file(), 'integrity core missing'
    return importlib.import_module('wuwei.integrity')


def plugin(tmp_path):
    base = tmp_path / 'plugin'
    (base / 'charters').mkdir(parents=True)
    (base / 'charters/builder.md').write_text('Run tests.\n')
    (base / 'keys').mkdir()
    (base / 'keys/manifest-signing-key.pub').write_text('ssh-ed25519 test-key\n')
    return base


def test_inventory_detects_changed_missing_and_extra_files(tmp_path, monkeypatch):
    api = core()
    base = plugin(tmp_path)
    api.write_manifest(base)
    (base / 'MANIFEST.sha256.sig').write_text('signature')
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(0)))
    assert api.measure(base).exit == 0
    charter = base / 'charters/builder.md'
    charter.write_text('run tests.\n')
    result = api.measure(base)
    assert result.exit == 1 and 'charters/builder.md' in result.reason
    charter.unlink()
    assert api.measure(base).exit == 1
    charter.write_text('Run tests.\n')
    (base / 'charters/extra.md').write_text('Extra')
    assert 'charters/extra.md' in api.measure(base).reason


@pytest.mark.parametrize('line', ['../escape', '/absolute', './charters/builder.md',
                                   'charters/../keys/key', 'charters/builder.md\nextra'])
def test_inventory_rejects_unsafe_names(tmp_path, monkeypatch, line):
    api = core()
    base = plugin(tmp_path)
    (base / 'MANIFEST.sha256').write_text('0' * 64 + '  ' + line + '\n')
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(0)))
    assert api.measure(base).exit == 1


def test_symlink_and_unreadable_inventory_are_not_clean(tmp_path, monkeypatch):
    api = core()
    base = plugin(tmp_path)
    api.write_manifest(base)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(0)))
    (base / 'alias').symlink_to(base / 'charters', target_is_directory=True)
    assert api.measure(base).exit != 0
    (base / 'alias').unlink()
    original = Path.read_bytes
    def unreadable(path):
        if path.name == 'builder.md':
            raise PermissionError('denied')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', unreadable)
    assert api.measure(base).exit == 2


def ssh():
    assert 'integrity' in registry.INTERFACES, 'signature port missing'
    return registry.load('integrity', {'adapters': {'integrity': 'ssh'}})


def test_signature_stub_allowlist_and_missing_tool(tmp_path, monkeypatch):
    adapter = ssh()
    base = plugin(tmp_path)
    manifest = base / 'MANIFEST.sha256'
    manifest.write_text('inventory')
    signature = base / 'MANIFEST.sha256.sig'
    signature.write_text('sig')
    key = base / 'keys/manifest-signing-key.pub'
    calls = []
    monkeypatch.setattr(adapter.shutil, 'which', lambda name: name)
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Namespace(returncode=0, stdout=b'', stderr=b'')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    assert adapter.verify(manifest, signature, key).exit == 0
    assert calls[0][0][1:3] == ['-Y', 'verify']
    assert calls[0][1]['input'] == b'inventory'
    assert calls[0][0][calls[0][0].index('-n') + 1] == 'wuwei-manifest'
    with pytest.raises(ValueError, match='unsupported'):
        adapter._run(['-Y', 'find-principals'])
    def absent(*a, **kw):
        raise FileNotFoundError('ssh-keygen')
    monkeypatch.setattr(adapter.subprocess, 'run', absent)
    assert adapter.verify(manifest, signature, key).exit == 2
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired('ssh-keygen', 30)
    monkeypatch.setattr(adapter.subprocess, 'run', timeout)
    assert adapter.verify(manifest, signature, key).exit == 2


@pytest.mark.parametrize('missing', ['manifest', 'signature'])
def test_unsigned_install_needs_no_ssh_process(tmp_path, monkeypatch, missing):
    adapter = ssh()
    manifest, signature, key = (tmp_path / name for name in ('manifest', 'signature', 'key'))
    for path in (manifest, signature, key):
        if path.name != missing:
            path.write_text('unused')
    monkeypatch.setattr(adapter.shutil, 'which', lambda name: name)
    def unexpected(*args, **kwargs):
        pytest.fail('unsigned install must not spawn ssh-keygen')
    monkeypatch.setattr(adapter.subprocess, 'run', unexpected)
    result = adapter.verify(manifest, signature, key)
    assert result.exit == 1
    assert result.reason == 'missing MANIFEST.sha256 or signature'
    monkeypatch.setattr(adapter.shutil, 'which', lambda name: None)
    assert adapter.verify(manifest, signature, key).exit == 2


def test_real_ssh_release_roundtrip_and_wrong_key(tmp_path):
    if not shutil.which('ssh-keygen'):
        pytest.skip('ssh-keygen absent; stub coverage still runs')
    api = core()
    base = plugin(tmp_path)
    keys = [tmp_path / 'owner', tmp_path / 'other']
    for key in keys:
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                       check=True, capture_output=True)
    shutil.copyfile(str(keys[0]) + '.pub', base / 'keys/manifest-signing-key.pub')
    api.write_manifest(base)
    adapter = ssh()
    manifest = base / 'MANIFEST.sha256'
    assert adapter.sign(manifest, keys[0]).exit == 0
    assert api.measure(base).exit == 0
    (base / 'MANIFEST.sha256.sig').unlink()
    assert adapter.sign(manifest, keys[1]).exit == 0
    assert api.measure(base).exit == 1


def test_core_never_imports_subprocess():
    import ast
    for path in (ROOT / 'cli').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(alias.name != 'subprocess' for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert node.module != 'subprocess', path


def workspace_root(tmp_path):
    root = tmp_path / 'workspace'
    (root / '.wuwei/integrity').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    return root


def test_cached_failure_confirmation_and_reinstall(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    base = plugin(tmp_path)
    monkeypatch.setattr(api, 'PLUGIN', base)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(0)))
    api.write_manifest(base)
    shutil.copyfile(base / api.KEY, root / '.wuwei/integrity/pinned.pub')
    assert api.check(root).exit == 0
    assert api.cached(root).exit == 0
    (base / 'charters/builder.md').write_text('Changed\n')
    assert api.check(root).exit == 1
    assert api.cached(root).exit == 2
    assert api.reconfirm(root, confirm=lambda digest: False).exit != 0
    assert api.cached(root).exit == 2
    assert api.reconfirm(root, confirm=lambda digest: True).exit == 0
    assert api.check(root).exit == 0
    (base / 'charters/builder.md').write_text('Changed again\n')
    assert api.check(root).exit == 1
    (base / 'charters/builder.md').write_text('Run tests.\n')
    assert api.check(root).exit == 0
    assert api.cached(root).exit == 0


@pytest.mark.parametrize('content', [None, '{}', 'broken', '{"exit":false}', '{"exit":0}'])
def test_missing_or_invalid_cache_is_unmeasured(tmp_path, content):
    api = core()
    root = workspace_root(tmp_path)
    if content is not None:
        (root / '.wuwei/integrity/verdict.json').write_text(content)
    assert api.cached(root).exit == 2


def test_integrity_hook_scope_and_session_exit(tmp_path, monkeypatch, capsys):
    import io
    from wuwei.commands import hook
    api = core()
    root = workspace_root(tmp_path)
    base = plugin(tmp_path)
    monkeypatch.setattr(api, 'PLUGIN', base)
    shutil.copyfile(base / api.KEY, root / '.wuwei/integrity/pinned.pub')
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(1, reason='missing manifest signature')))
    payload = {'cwd': str(root), 'session_id': 'test', 'transcript_path': 'transcript',
               'hook_event_name': 'SessionStart', 'tool_name': 'Bash',
               'tool_input': {'command': 'echo hello'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert hook.run(Namespace(event='SessionStart')) == 0
    assert 'page:' in capsys.readouterr().out
    payload['hook_event_name'] = 'PreToolUse'
    for tool in ('Bash', 'Read', 'Write', 'Agent', 'UnknownTool'):
        payload['tool_name'] = tool
        monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
        assert hook.run(Namespace(event='PreToolUse')) == 2
    payload['cwd'] = str(tmp_path)
    payload['tool_name'] = 'Bash'
    for command in ('python3 -m pytest -q', 'for x in a; do echo "$x"; done', 'export X=1'):
        payload['tool_input'] = {'command': command}
        monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
        assert hook.run(Namespace(event='PreToolUse')) == 0


@pytest.mark.parametrize('name', ['verdict.json', 'confirmation.json', 'pinned.pub'])
def test_integrity_files_protected(tmp_path, name):
    from wuwei.guards.protect_state import check_file, check_bash
    root = workspace_root(tmp_path)
    file = '.wuwei/integrity/' + name
    payload = {'cwd': str(root), 'tool_name': 'Write', 'tool_input': {'file_path': file}}
    assert check_file(payload)[0] != 0
    payload.update(tool_name='Bash', tool_input={'command': 'rm ' + file})
    assert check_bash(payload)[0] != 0


@pytest.mark.parametrize('command', ['bin/wuwei integrity reconfirm',
    'python3 -P -m wuwei integrity reconfirm', 'bin/wuwei integrity reconfirm > approval'])
def test_seat_cannot_reconfirm(tmp_path, command):
    from wuwei.guards.protect_state import check_bash
    root = workspace_root(tmp_path)
    assert check_bash({'cwd': str(root), 'tool_name': 'Bash',
                       'tool_input': {'command': command}})[0] != 0


@pytest.mark.parametrize('command', [
    'grep -rn reconfirm cli/', 'python -m pytest -q -k reconfirm',
    "python3 -c 'reconfirm()'",
])
def test_unrelated_reconfirm_mentions_are_allowed(tmp_path, command):
    from wuwei.guards.protect_state import check_bash
    root = workspace_root(tmp_path)
    assert check_bash({'cwd': str(root), 'tool_name': 'Bash',
                       'tool_input': {'command': command}}) == (0, '')


def test_integrity_producer_only_state_and_events(tmp_path, monkeypatch):
    from wuwei import state
    from wuwei.commands import event
    root = workspace_root(tmp_path)
    monkeypatch.chdir(root)
    for key in ('integrity', 'integrity_failed', 'integrity_confirmation'):
        with pytest.raises(ValueError):
            state.set_state(key, {}, root)
        assert event.run(Namespace(kind=key, payload='{}')) == 1


def test_every_sweep_measures_integrity(tmp_path, monkeypatch):
    from wuwei import obligations, watch
    api = core()
    root = workspace_root(tmp_path)
    calls = []
    monkeypatch.setattr(api, 'check', lambda root: calls.append(root) or registry.Result(1, reason='page: changed'))
    monkeypatch.setattr(obligations, 'evaluate', lambda root: dict(
        exit=0, reply_owed=0, visibility_owed=0, unreadable=0))
    assert obligations.sweep(root) == 1
    assert calls == [root]
    watch.sweep(root)
    assert calls == [root, root]


def test_cached_check_latency(tmp_path):
    import time
    api = core()
    root = workspace_root(tmp_path)
    (root / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 0, 'fingerprint': 'a' * 64, 'reason': ''}))
    samples = []
    for _ in range(100):
        start = time.perf_counter()
        assert api.cached(root).exit == 0
        samples.append(time.perf_counter() - start)
    assert sorted(samples)[94] < .05


def vcs():
    return registry.load('vcs', {'adapters': {'vcs': 'git'}})


def test_real_workspace_history_and_selected_promotion_commit(tmp_path):
    if not shutil.which('git'):
        pytest.skip('git absent; workspace adapter stub tests still run')
    adapter = vcs()
    assert hasattr(adapter, 'workspace_init'), 'workspace VCS port missing'
    root = workspace_root(tmp_path)
    base = root / '.wuwei'
    (base / 'charters').mkdir()
    (base / 'memory').mkdir()
    (base / 'memory/goals.md').write_text('Goals\n')
    (base / 'charters/builder.md').write_text('Builder\n')
    assert adapter.workspace_init(base).exit == 0
    assert adapter.workspace_changes(base).data == []
    (base / 'charters/builder.md').write_text('Hand edit\n')
    result = adapter.workspace_changes(base)
    assert result.exit == 0 and result.data == ['charters/builder.md']
    # A trailer-less commit must remain visible even after a later promotion.
    subprocess.run(['git', '-C', str(base), '-c', 'user.name=Test', '-c',
                    'user.email=test@example.invalid', '-c', 'commit.gpgsign=false',
                    'commit', '-am', 'Manual edit'], check=True, capture_output=True)
    assert adapter.workspace_changes(base).data == ['charters/builder.md']
    (base / 'memory/goals.md').write_text('Unrelated staged edit\n')
    subprocess.run(['git', '-C', str(base), 'add', 'memory/goals.md'], check=True)
    (base / 'charters/builder.md').write_text('Promoted\n')
    assert adapter.workspace_commit(base, ['charters/builder.md']).exit == 0
    assert adapter.workspace_changes(base).data == ['charters/builder.md', 'memory/goals.md']
    logged = subprocess.run(['git', '-C', str(base), 'show', '--format=%B', '--name-only', 'HEAD'],
                            check=True, capture_output=True, text=True).stdout
    assert 'Promoted-by: wuwei' in logged and 'memory/goals.md' not in logged


def test_workspace_history_stub_and_allowlist(tmp_path, monkeypatch):
    (tmp_path / '.git').mkdir()
    adapter = vcs()
    assert hasattr(adapter, 'workspace_changes'), 'workspace VCS port missing'
    outputs = iter([b' M charters/builder.md\0?? memory/new.md\0',
                    b'\x1ewuwei\n\0\ncharters/old.md\0\x1e\0\nmemory/voice.md\0'])
    monkeypatch.setattr(adapter.subprocess, 'run', lambda *a, **kw: Namespace(
        returncode=0, stdout=next(outputs)))
    result = adapter.workspace_changes(tmp_path)
    assert result.exit == 0
    assert result.data == ['charters/builder.md', 'memory/new.md', 'memory/voice.md']
    with pytest.raises(ValueError, match='unsupported'):
        adapter._run(tmp_path, 'commit', '-am', 'Anything')
    def absent(*a, **kw):
        raise FileNotFoundError('git')
    monkeypatch.setattr(adapter.subprocess, 'run', absent)
    assert adapter.workspace_init(tmp_path / 'new').exit == 2
    assert adapter.workspace_changes(tmp_path).exit == 2


@pytest.mark.parametrize('changed,severity', [('charters/builder.md', 'page'),
    ('memory/voice.md', 'page'), ('memory/goals.md', 'nudge'), ('memory/notes/a.md', 'nudge')])
def test_workspace_integrity_severity(tmp_path, monkeypatch, changed, severity):
    api = core()
    root = workspace_root(tmp_path)
    monkeypatch.setattr(registry, 'load', lambda *a: Namespace(
        workspace_changes=lambda *a, **kw: registry.Result(0, [changed])))
    result = api.workspace_check(root)
    assert result.exit == 1 and f'{severity}:' in result.reason and changed in result.reason


def test_init_pins_key_and_initializes_workspace_vcs(tmp_path, monkeypatch):
    from wuwei.commands import init
    calls = []
    original = registry.load
    def load(kind, config):
        if kind == 'vcs':
            return Namespace(workspace_init=lambda repo, **kw: calls.append(Path(repo)) or registry.Result(0))
        return original(kind, config)
    monkeypatch.setattr(registry, 'load', load)
    assert init.run(Namespace(path=str(tmp_path))) == 0
    assert calls and calls[0].name.startswith('.wuwei-init-')
    assert (tmp_path / '.wuwei/integrity/pinned.pub').read_bytes() == (ROOT / core().KEY).read_bytes()


def test_promotion_commits_only_landed_targets(tmp_path, monkeypatch):
    from test_promotion import setup, proposal, DAY
    from wuwei import promotion
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    proposal(base)
    calls = []
    monkeypatch.setattr(registry, 'load', lambda *a: Namespace(
        workspace_changes=lambda *a, **kw: registry.Result(0, []),
        workspace_commit=lambda repo, paths, **kw: calls.append(paths) or registry.Result(0)))
    records = promotion.promote(tmp_path)
    assert records[0]['status'] == 'landed'
    assert calls == [['charters/builder.md', 'memory/CHANGELOG.md', 'memory/ledger.jsonl']]


def test_promotion_vcs_failure_is_unmeasured(tmp_path, monkeypatch):
    from test_promotion import setup, proposal, DAY
    from wuwei import promotion
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    proposal(base)
    monkeypatch.setattr(registry, 'load', lambda *a: Namespace(
        workspace_changes=lambda *a, **kw: registry.Result(0, []),
        workspace_commit=lambda *a, **kw: registry.Result(2, reason='git missing')))
    with pytest.raises(OSError, match='git missing'):
        promotion.promote(tmp_path)


def test_release_package_covers_every_shipped_file(tmp_path, monkeypatch):
    import runpy
    script = ROOT / 'scripts/build-release.py'
    assert script.is_file(), 'release packaging missing'
    build = runpy.run_path(str(script))['build']
    api = core()
    calls = []
    def sign(manifest, key):
        calls.append(Path(manifest))
        Path(str(manifest) + '.sig').write_text('signature')
        return registry.Result(0)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        sign=sign, verify=lambda *a: registry.Result(0)))
    archive = build(ROOT, tmp_path / 'release', tmp_path / 'private-key')
    assert archive.is_file() and calls
    stage = tmp_path / 'release/wuwei'
    names = set(api.inventory(stage))
    for directory in ('cli', 'adapters', 'hooks', 'charters', 'skills', 'agents', 'templates', 'keys', 'bin', '.claude-plugin'):
        assert any(n.startswith(directory + '/') for n in names)
    lines = (stage / api.MANIFEST).read_text().splitlines()
    assert names == {line[66:] for line in lines}
    assert not any('__pycache__' in n for n in names)
    assert api.measure(stage).exit == 0
    workflow = (ROOT / '.github/workflows/release.yml').read_text()
    assert 'WUWEI_MANIFEST_SIGNING_KEY' in workflow
    assert 'scripts/build-release.py' in workflow


@pytest.mark.parametrize('command', ["bin/wuwei 'integrity' 'reconfirm'",
    'bin/wuwei integ"rity" re"confirm"', 'bin/wuwei integrity re\\confirm',
    "sh -c 'bin/wuwei integrity reconfirm'", "python3 -c 'integrity.reconfirm()'",
    "bin/wuwei 'integrity' 'reconfirm' $(date)"])
def test_reconfirmation_obfuscation_is_relevant(tmp_path, command):
    from wuwei.guards.protect_state import check_bash
    root = workspace_root(tmp_path)
    assert check_bash({'cwd': str(root), 'tool_name': 'Bash',
                       'tool_input': {'command': command}})[0] != 0


def test_check_failure_replaces_old_clean_cache(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    from fakes.integrity import seed
    seed(root)
    monkeypatch.setattr(api, 'measure', lambda **kw: (_ for _ in ()).throw(ValueError('bad evidence')))
    assert api.check(root).exit == 2
    assert api.cached(root).exit == 2


def test_declined_confirmation_caches_new_failure(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    from fakes.integrity import seed
    seed(root)
    monkeypatch.setattr(api, 'measure', lambda **kw: registry.Result(1, 'b' * 64, 'page: changed'))
    assert api.reconfirm(root, confirm=lambda digest: False).exit == 1
    assert api.cached(root).exit == 2


def test_adapter_rejects_unreadable_signature_as_unmeasured(tmp_path, monkeypatch):
    adapter = ssh()
    base = plugin(tmp_path)
    (base / 'MANIFEST.sha256').write_text('inventory')
    signature = base / 'MANIFEST.sha256.sig'
    signature.mkdir()
    assert adapter.verify(base / 'MANIFEST.sha256', signature, base / core().KEY).exit == 2


def test_promotion_cannot_bless_prior_hand_edit(tmp_path, monkeypatch):
    from test_promotion import setup, proposal, DAY
    from wuwei import promotion
    base = setup(tmp_path)
    target = base / 'charters/builder.md'
    target.write_text('Unapproved hand edit\n')
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+02:00')
    proposal(base)
    calls = []
    monkeypatch.setattr(registry, 'load', lambda *a: Namespace(
        workspace_changes=lambda *a, **kw: registry.Result(0, ['charters/builder.md']),
        workspace_commit=lambda *a, **kw: calls.append(a) or registry.Result(0)))
    assert promotion.promote(tmp_path)[0]['status'] == 'rejected'
    assert target.read_text() == 'Unapproved hand edit\n'
    assert not calls


def test_session_start_reports_hand_edited_charter(tmp_path, monkeypatch, capsys):
    import io
    from wuwei.commands import hook
    api = core()
    root = workspace_root(tmp_path)
    monkeypatch.setattr(api, 'check', lambda root: registry.Result(0, 'a' * 64))
    monkeypatch.setattr(registry, 'load', lambda *a: Namespace(
        workspace_changes=lambda *a, **kw: registry.Result(0, ['charters/builder.md'])))
    payload = {'cwd': str(root), 'session_id': 'test', 'transcript_path': 'trace',
               'hook_event_name': 'SessionStart'}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert hook.run(Namespace(event='SessionStart')) == 0
    output = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert 'page: workspace integrity: charters/builder.md' in output


def test_workspace_git_never_uses_parent_repository(tmp_path, monkeypatch):
    adapter = vcs()
    calls = []
    monkeypatch.setattr(adapter.subprocess, 'run', lambda *a, **kw: calls.append(a) or Namespace(
        returncode=0, stdout=b'\x1ewuwei\0'))
    assert adapter.workspace_changes(tmp_path).exit == 2
    assert adapter.workspace_commit(tmp_path, ['charters/builder.md']).exit == 2
    assert not calls


def test_missing_ssh_is_unmeasured_even_with_invalid_pin(tmp_path, monkeypatch):
    adapter = ssh()
    base = plugin(tmp_path)
    (base / 'MANIFEST.sha256').write_text('inventory')
    (base / 'MANIFEST.sha256.sig').write_text('sig')
    (base / core().KEY).write_text('invalid\nmultiline pin')
    monkeypatch.setenv('PATH', str(tmp_path / 'absent'))
    assert adapter.verify(base / 'MANIFEST.sha256', base / 'MANIFEST.sha256.sig', base / core().KEY).exit == 2


def test_sweep_summary_cannot_report_clean_when_integrity_failed(tmp_path, monkeypatch):
    from wuwei import obligations, state
    api = core()
    root = workspace_root(tmp_path)
    monkeypatch.setattr(api, 'check', lambda root: registry.Result(1, reason='page: changed'))
    monkeypatch.setattr(obligations, 'evaluate', lambda root: dict(
        exit=0, reply_owed=0, visibility_owed=0, unreadable=0))
    records = []
    monkeypatch.setattr(state, 'append_event', lambda kind, data, **kw: records.append(data))
    assert obligations.sweep(root) == 1
    assert records[0]['exit'] == 1 and records[0]['integrity_owed'] == 1


def test_host_confirmation_uses_a_nonseekable_terminal(monkeypatch):
    import builtins
    import os
    import pty
    api = core()
    master, slave = pty.openpty()
    real_open = builtins.open
    def terminal_open(path, *args, **kwargs):
        return real_open(os.ttyname(slave) if path == '/dev/tty' else path, *args,
                         opener=lambda name, flags: os.open(name, flags | os.O_NOCTTY), **kwargs)
    monkeypatch.setattr(builtins, 'open', terminal_open)
    try:
        fingerprint = 'a' * 64
        os.write(master, (fingerprint + '\n').encode())
        assert api._host_confirm(fingerprint) is True
    finally:
        os.close(master)
        os.close(slave)


def test_host_action_guard_ignores_outside_workspace_override(tmp_path, monkeypatch):
    from wuwei.guards.protect_state import check_bash
    root = workspace_root(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    payload = {'cwd': str(tmp_path), 'tool_name': 'Bash',
               'tool_input': {'command': 'bin/wuwei integrity reconfirm'}}
    assert check_bash(payload)[0] == 0


def test_cli_names_changed_charter_and_missing_tool(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    api = core()
    root = workspace_root(tmp_path)
    base = plugin(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(api, 'PLUGIN', base)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(0)))
    api.write_manifest(base)
    shutil.copyfile(base / api.KEY, root / '.wuwei/integrity/pinned.pub')
    assert main(['integrity', 'check']) == 0
    (base / 'charters/builder.md').write_text('run tests.\n')
    assert main(['integrity', 'check']) == 1
    assert 'charters/builder.md' in capsys.readouterr().out
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(2, reason='ssh-keygen unmeasured: missing')))
    assert main(['integrity', 'check']) == 2
    assert 'unmeasured' in capsys.readouterr().out
