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
    monkeypatch.setattr(adapter, '_installed', lambda: True)
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


def test_verify_leaves_no_signers_file(tmp_path, monkeypatch):
    # #587: the allowed-signers file lives in a private directory under TMPDIR, gone after
    # a match, a mismatch and a timeout alike.
    adapter = ssh()
    base = plugin(tmp_path)
    manifest, signature = base / 'MANIFEST.sha256', base / 'MANIFEST.sha256.sig'
    manifest.write_text('inventory')
    signature.write_text('sig')
    temp = tmp_path / 'tmp'
    temp.mkdir()
    monkeypatch.setenv('TMPDIR', str(temp))
    monkeypatch.setattr(adapter, '_installed', lambda: True)
    for outcome, code in ((0, 0), (1, 1), (None, 2)):
        seen = []
        def run(argv, outcome=outcome, **kwargs):
            signers = Path(argv[argv.index('-f') + 1])
            seen.append((signers.parent.parent, signers.read_text()))
            if outcome is None:
                raise subprocess.TimeoutExpired('ssh-keygen', 30)
            return Namespace(returncode=outcome, stdout=b'', stderr=b'')
        monkeypatch.setattr(adapter.subprocess, 'run', run)
        assert adapter.verify(manifest, signature, base / 'keys/manifest-signing-key.pub').exit == code
        assert seen == [(temp, 'wuwei ssh-ed25519 test-key\n')]
        assert list(temp.iterdir()) == []


@pytest.mark.parametrize('missing', ['manifest', 'signature'])
def test_unsigned_install_needs_no_ssh_process(tmp_path, monkeypatch, missing):
    adapter = ssh()
    manifest, signature, key = (tmp_path / name for name in ('manifest', 'signature', 'key'))
    for path in (manifest, signature, key):
        if path.name != missing:
            path.write_text('unused')
    monkeypatch.setattr(adapter, '_installed', lambda: True)
    def unexpected(*args, **kwargs):
        pytest.fail('unsigned install must not spawn ssh-keygen')
    monkeypatch.setattr(adapter.subprocess, 'run', unexpected)
    result = adapter.verify(manifest, signature, key)
    assert result.exit == 1
    assert result.reason == 'missing MANIFEST.sha256 or signature'
    monkeypatch.setattr(adapter, '_installed', lambda: False)
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
    seen = []
    assert api.reconfirm(root, confirm=lambda digest: seen.append(digest) or True).exit == 0
    recorded = json.loads((root / '.wuwei/integrity/confirmation.json').read_text())['fingerprint']
    assert recorded == seen[0] and len(recorded) == 64  # the owner answers y/N; the full digest is kept
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


@pytest.mark.xdist_group('timing')
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
    outputs = {'status': b' M charters/builder.md\0?? memory/new.md\0',
               'log': b'\x1ewuwei\n\0\ncharters/old.md\0\x1e\0\nmemory/voice.md\0'}
    monkeypatch.setattr(adapter.subprocess, 'run', lambda argv, **kw: Namespace(
        returncode=0, stdout=next(value for key, value in outputs.items() if key in argv)))
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
    monkeypatch.setattr(core(), 'check', lambda root: registry.Result(0, 'a' * 64))
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
    assert {'.claude-plugin/plugin.json', 'cli/wuwei/commands/board.py'} <= names
    assert '.mcp.json' not in names
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
    monkeypatch.setattr(api, 'PLUGIN', plugin(tmp_path))
    monkeypatch.setattr(api, 'measure', lambda **kw: (_ for _ in ()).throw(ValueError('bad evidence')))
    assert api.check(root).exit == 2
    assert api.cached(root).exit == 2


def test_declined_confirmation_caches_new_failure(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    from fakes.integrity import seed
    seed(root)
    monkeypatch.setattr(api, 'PLUGIN', plugin(tmp_path))
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


@pytest.mark.parametrize('answer, expected', [('y', True), ('YES', True), ('n', False), ('', False),
                                              ('ab' * 32, False)])
def test_host_confirm_asks_yes_or_no(monkeypatch, answer, expected):
    import builtins
    import os
    import pty
    import select
    api = core()
    master, slave = pty.openpty()
    real_open = builtins.open
    def terminal_open(path, *args, **kwargs):
        return real_open(os.ttyname(slave) if path == '/dev/tty' else path, *args,
                         opener=lambda name, flags: os.open(name, flags | os.O_NOCTTY), **kwargs)
    monkeypatch.setattr(builtins, 'open', terminal_open)
    try:
        fingerprint = 'ab' * 32
        os.write(master, (answer + '\n').encode())
        assert api._host_confirm(fingerprint) is expected
        shown = b''
        while select.select([master], [], [], 0.2)[0]:
            shown += os.read(master, 4096)
        shown = shown.decode()
        assert 'Confirm? [y/N]' in shown and fingerprint[:12] in shown
        # The terminal echoes the typed line; the prompt itself never shows the full digest.
        assert shown.count(fingerprint) == (answer == fingerprint)
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


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    from fakes.vcs import Fake
    api = core()
    root = workspace_root(tmp_path)
    base = plugin(tmp_path)
    (base / '.git').mkdir()
    shutil.copyfile(base / api.KEY, root / '.wuwei/integrity/pinned.pub')
    fake = Fake({'head': registry.Result(0, {'sha': 'a' * 40}),
                 'status': registry.Result(0, []),
                 'read_tree': registry.Result(0, {
                     'charters/builder.md': 'Run tests.\n',
                     api.KEY: 'ssh-ed25519 test-key\n'})})
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake if kind == 'vcs' else load(kind, config))
    monkeypatch.setattr(api, 'PLUGIN', base)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(1, reason='missing MANIFEST.sha256 or signature')))
    return api, root, base, fake


@pytest.mark.parametrize('artifact', ['file', 'symlink'])
def test_checkout_ignored_artifacts_preserve_confirmation(checkout, artifact):
    api, root, base, fake = checkout
    confirmed = api.reconfirm(root, confirm=lambda digest: True)
    assert confirmed.exit == 0
    if artifact == 'file':
        (base / '.pytest_cache').mkdir()
        (base / '.pytest_cache/README.md').write_text('Generated cache\n')
    else:
        (base / '.venv/bin').mkdir(parents=True)
        (base / '.venv/bin/python').symlink_to(sys.executable)
    measured = api.check(root)
    assert measured.data == confirmed.data
    assert measured.exit == api.cached(root).exit == 0
    assert api.reconfirm(root, confirm=lambda digest: digest == confirmed.data).exit == 0


@pytest.mark.parametrize('result', [registry.Result(2, reason='git unavailable'),
                                  registry.Result(0, None), registry.Result(0, [])])
def test_checkout_unreadable_tracked_paths_cannot_be_confirmed(checkout, result):
    api, root, base, fake = checkout
    fake.results['read_tree'] = result
    assert api.reconfirm(root, confirm=lambda digest: pytest.fail('unmeasured tree')).exit == 2


@pytest.mark.parametrize('git_file', [False, True])
def test_checkout_confirmation_pins_commit_and_clean_tree(checkout, git_file):
    api, root, base, fake = checkout
    if git_file:
        (base / '.git').rmdir()
        (base / '.git').write_text('gitdir: ../git/worktrees/plugin\n')
    assert api.check(root).exit == 1
    assert api.cached(root).exit == 2
    assert api.reconfirm(root, confirm=lambda digest: True).exit == 0
    confirmation = json.loads((root / '.wuwei/integrity/confirmation.json').read_text())
    verdict = json.loads((root / '.wuwei/integrity/verdict.json').read_text())
    assert confirmation['checkout'] == verdict['checkout'] == {'head': 'a' * 40, 'clean': True}
    from wuwei.guards.integrity import check
    payload = {'cwd': str(root), 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
    fake.calls.clear()
    for _ in range(3):
        assert check(payload) == (0, '')
    assert len(fake.calls) == 6
    assert all(call[1] == (base,) for call in fake.calls)
    assert api.check(root).exit == 0
    # A pull can move HEAD without changing any installed file content.
    fake.results['head'] = registry.Result(0, {'sha': 'b' * 40})
    assert check(payload)[0] == 2
    assert api.check(root).exit == 1
    assert api.reconfirm(root, confirm=lambda digest: True).exit == 0
    assert check(payload)[0] == 0
    (base / 'charters/builder.md').write_text('Uncommitted edit\n')
    fake.results['status'] = registry.Result(0, [
        {'path': 'charters/builder.md', 'index': ' ', 'worktree': 'M', 'original_path': None}])
    assert check(payload)[0] == 2
    assert api.check(root).exit == 1
    assert api.reconfirm(root, confirm=lambda digest: pytest.fail('dirty tree cannot be confirmed')).exit == 1
    assert api.cached(root).exit == 2


@pytest.mark.parametrize('operation,result', [
    ('head', registry.Result(2, reason='git missing')),
    ('head', registry.Result(1, reason='HEAD missing')),
    ('head', registry.Result(0, {'error': 'unknown HEAD'})),
    ('head', registry.Result(0, {'sha': 'short'})),
    ('head', registry.Result(0, {'sha': 40})),
    ('status', registry.Result(2, reason='git timed out')),
    ('status', registry.Result(0, {'error': 'unreadable tree'})),
    ('status', registry.Result(0, None)),
    ('status', registry.Result(0, [None])),
])
def test_checkout_evidence_failures_close_cache_and_confirmation(checkout, operation, result):
    api, root, base, fake = checkout
    assert api.reconfirm(root, confirm=lambda digest: True).exit == 0
    fake.results[operation] = result
    cached = api.cached(root)
    assert cached.exit == 2 and cached.reason
    measured = api.check(root)
    assert measured.exit == 2 and measured.reason
    assert api.reconfirm(root, confirm=lambda digest: pytest.fail('unmeasured checkout')).exit == 2


@pytest.mark.parametrize('change', ['head', 'dirty', 'content'])
def test_checkout_changes_during_confirmation_are_not_confirmed(checkout, change):
    api, root, base, fake = checkout
    def confirm(digest):
        if change == 'head':
            fake.results['head'] = registry.Result(0, {'sha': 'b' * 40})
        elif change == 'dirty':
            fake.results['status'] = registry.Result(0, [
                {'path': 'charters/builder.md', 'index': 'M', 'worktree': ' ', 'original_path': None}])
        else:
            (base / 'charters/builder.md').write_text('Changed\n')
        return True
    assert api.reconfirm(root, confirm=confirm).exit == 2
    assert not (root / '.wuwei/integrity/confirmation.json').exists()
    assert api.cached(root).exit == 2


def test_checkout_does_not_need_signature_tool(checkout, monkeypatch):
    api, root, base, fake = checkout
    monkeypatch.setattr(api, 'signature_adapter', lambda: pytest.fail('checkout is pinned through VCS'))
    assert api.reconfirm(root, confirm=lambda digest: True).exit == 0


def test_checkout_legacy_confirmation_needs_new_host_confirmation(checkout):
    api, root, base, fake = checkout
    fingerprint = api.measure(pinned=root / '.wuwei/integrity/pinned.pub').data
    api._record(root, 'confirmation.json', {'fingerprint': fingerprint})
    assert api.check(root).exit == 1
    assert api.cached(root).exit == 2


@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'for x in a; do echo "$x"; done', 'export X=1'])
def test_checkout_guard_uses_existing_scope_before_vcs_reads(checkout, tmp_path, command):
    from wuwei.guards.integrity import check
    api, root, base, fake = checkout
    fake.results['head'] = registry.Result(2, reason='git missing')
    payload = {'cwd': str(tmp_path), 'tool_name': 'Bash', 'tool_input': {'command': command}}
    assert check(payload) == (0, '')
    assert not fake.calls
    payload.update(tool_name='Read', tool_input={'file_path': str(root / 'source.py')})
    assert check(payload)[0] == 2


@pytest.mark.parametrize('artifact', ['MANIFEST.sha256', 'MANIFEST.sha256.sig', 'both'])
def test_checkout_never_bypasses_present_release_artifacts(checkout, monkeypatch, artifact):
    api, root, base, fake = checkout
    if artifact in ('MANIFEST.sha256', 'both'):
        api.write_manifest(base)
    if artifact in ('MANIFEST.sha256.sig', 'both'):
        (base / 'MANIFEST.sha256.sig').write_text('signature')
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(2, reason='signature verifier unavailable')))
    assert api.check(root).exit == 2
    assert api.reconfirm(root, confirm=lambda digest: pytest.fail('unmeasured signature')).exit == 2
    assert not fake.calls


def test_signed_install_passes_without_confirmation_or_vcs(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    base = plugin(tmp_path)
    api.write_manifest(base)
    (base / 'MANIFEST.sha256.sig').write_text('signature')
    shutil.copyfile(base / api.KEY, root / '.wuwei/integrity/pinned.pub')
    monkeypatch.setattr(api, 'PLUGIN', base)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(verify=lambda *a: registry.Result(0)))
    monkeypatch.setattr(registry, 'load', lambda *a: pytest.fail('signed install needs no VCS'))
    assert api.check(root).exit == 0
    assert api.cached(root).exit == 0
    assert not (root / '.wuwei/integrity/confirmation.json').exists()


def test_checkout_reasons_name_reconfirm_line(checkout):
    api, root, base, fake = checkout
    line = 'run wuwei integrity reconfirm on the host'
    result = api.check(root)
    assert result.exit == 1 and result.reason.endswith(line) and '\n' not in result.reason
    assert api.cached(root) == registry.Result(2, reason=result.reason)
    fake.results['status'] = registry.Result(0, [{'path': 'a', 'index': ' ', 'worktree': 'M'}])
    result = api.check(root)
    assert result.exit == 1 and 'restore a clean commit and ' + line in result.reason
    cached = api.cached(root)
    assert cached.exit == 2 and cached.reason == result.reason and 'Errno' not in cached.reason


def measured(monkeypatch, result):
    calls = []
    def check(root):
        calls.append((Path(root), (Path(root) / '.wuwei/config.toml').is_file()))
        return result
    monkeypatch.setattr(core(), 'check', check)
    return calls


@pytest.mark.parametrize('result', [registry.Result(0, 'a' * 64),
                                    registry.Result(2, reason='plugin integrity unmeasured: test')])
def test_init_measures_integrity_last(tmp_path, monkeypatch, capsys, result):
    from wuwei.commands import init
    calls = measured(monkeypatch, result)
    assert init.run(Namespace(path=str(tmp_path))) == 0
    assert calls == [(tmp_path, True)]
    out = capsys.readouterr().out
    assert (result.reason or 'plugin integrity: clean') in out
    assert ('plugin integrity: clean' in out) == (result.exit == 0)


def test_init_upgrade_measures_unless_dry_run(tmp_path, monkeypatch, capsys):
    from wuwei.commands import init
    calls = measured(monkeypatch, registry.Result(0, 'a' * 64))
    assert init.run(Namespace(path=str(tmp_path))) == 0
    calls.clear()
    capsys.readouterr()
    assert init.run(Namespace(path=str(tmp_path), upgrade=True, dry_run=True)) == 0
    assert not calls and 'plugin integrity' not in capsys.readouterr().out
    assert init.run(Namespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    assert calls == [(tmp_path, True)] and 'plugin integrity: clean' in capsys.readouterr().out


def pre_tool_use(monkeypatch, root):
    import io
    from wuwei.commands import hook
    payload = {'cwd': str(root), 'session_id': 'test', 'transcript_path': 'transcript',
               'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    return hook.run(Namespace(event='PreToolUse'))


def test_signed_install_is_usable_right_after_init(tmp_path, monkeypatch, capsys):
    from wuwei.commands import init
    api = core()
    base = plugin(tmp_path)
    api.write_manifest(base)
    monkeypatch.setattr(api, 'PLUGIN', base)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(verify=lambda *a: registry.Result(0)))
    root = tmp_path / 'ws'
    assert init.run(Namespace(path=str(root))) == 0
    assert 'plugin integrity: clean' in capsys.readouterr().out
    assert json.loads((root / '.wuwei/integrity/verdict.json').read_text())['exit'] == 0
    assert pre_tool_use(monkeypatch, root) == 0


def test_development_checkout_init_says_reconfirm(tmp_path, monkeypatch, capsys):
    from wuwei.commands import init
    api = core()
    base = plugin(tmp_path)
    (base / '.git').mkdir()
    vcs = Namespace(workspace_init=lambda *a, **kw: registry.Result(0),
                    head=lambda *a, **kw: registry.Result(0, {'sha': 'a' * 40}),
                    status=lambda *a, **kw: registry.Result(0, []),
                    read_tree=lambda *a, **kw: registry.Result(0, {
                        'charters/builder.md': 'Run tests.\n', api.KEY: 'ssh-ed25519 test-key\n'}))
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: vcs if kind == 'vcs' else load(kind, config))
    monkeypatch.setattr(api, 'PLUGIN', base)
    root = tmp_path / 'ws'
    assert init.run(Namespace(path=str(root))) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if 'wuwei integrity reconfirm' in line]
    assert len(lines) == 1
    assert pre_tool_use(monkeypatch, root) == 2
    reason = json.loads(capsys.readouterr().out)['hookSpecificOutput']['permissionDecisionReason']
    assert 'run wuwei integrity reconfirm on the host' in reason and 'Errno' not in reason


def no_terminal(monkeypatch, tmp_path, mode):
    """Make /dev/tty missing ('missing') or a regular file ('file')."""
    import builtins
    real_open = builtins.open
    regular = tmp_path / 'not-a-tty'
    regular.write_text('')
    def fake_open(path, *args, **kwargs):
        if path != '/dev/tty':
            return real_open(path, *args, **kwargs)
        if mode == 'missing':
            raise OSError(6, 'Device not configured')
        return real_open(regular, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', fake_open)


@pytest.mark.parametrize('mode', ['missing', 'file'])
def test_host_confirmation_without_a_terminal_names_the_owner_action(tmp_path, monkeypatch, mode):
    api = core()
    no_terminal(monkeypatch, tmp_path, mode)
    with pytest.raises(OSError) as raised:
        api._host_confirm('a' * 64)
    assert str(raised.value) == 'this is an owner action: run it in a host terminal'


def test_reconfirm_without_a_terminal_cannot_run(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    from fakes.integrity import seed
    seed(root)
    monkeypatch.setattr(api, 'PLUGIN', plugin(tmp_path))
    monkeypatch.setattr(api, 'measure', lambda **kw: registry.Result(1, 'b' * 64, 'page: changed'))
    no_terminal(monkeypatch, tmp_path, 'missing')
    result = api.reconfirm(root)
    assert result.exit == 2
    assert 'run it in a host terminal' in result.reason and 'Errno' not in result.reason


@pytest.fixture
def fresh_plugin(tmp_path, monkeypatch):
    import os
    from fakes.integrity import seed
    api = core()
    base = tmp_path / 'installed'
    (base / 'cli/__pycache__').mkdir(parents=True)
    (base / 'cli/x.py').write_text('x = 1\n')
    (base / 'cli/__pycache__/x.pyc').write_text('compiled')
    for path in (base / 'cli/x.py', base / 'cli/__pycache__/x.pyc'):
        os.utime(path, (1_000_000, 1_000_000))
    monkeypatch.setattr(api, 'PLUGIN', base)
    seed(tmp_path)
    return api, base, tmp_path


def test_fresh_is_clean_when_every_file_is_older(fresh_plugin):
    api, _, root = fresh_plugin
    assert api.fresh(root) == registry.Result(0)


def test_fresh_names_a_file_changed_after_the_verdict(fresh_plugin):
    import os
    api, base, root = fresh_plugin
    later = (root / '.wuwei/integrity/verdict.json').stat().st_mtime + 10
    os.utime(base / 'cli/__pycache__/x.pyc', (later, later))
    assert api.fresh(root).exit == 0
    os.utime(base / 'cli/x.py', (later, later))
    result = api.fresh(root)
    assert result.exit == 1
    assert 'cli/x.py' in result.reason and 'changed after the cached verdict' in result.reason


def test_fresh_returns_a_failed_cache_unchanged(fresh_plugin):
    api, _, root = fresh_plugin
    (root / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 1, 'fingerprint': None, 'reason': 'page: plugin integrity: x'}))
    assert api.fresh(root) == api.cached(root)
    assert api.fresh(root).exit == 2


def test_fresh_skips_the_walk_for_a_checkout(fresh_plugin, monkeypatch):
    import os
    api, _, root = fresh_plugin
    checkout = {'head': 'b' * 40, 'clean': True}
    (root / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 0, 'fingerprint': 'a' * 64, 'reason': '', 'checkout': checkout}))
    monkeypatch.setattr(api, '_checkout', lambda root: checkout)
    monkeypatch.setattr(os, 'walk', lambda *a, **k: (_ for _ in ()).throw(AssertionError('walked')))
    assert api.fresh(root) == registry.Result(0)


def signed(tmp_path, monkeypatch):
    api = core()
    base = plugin(tmp_path)
    api.write_manifest(base)
    (base / 'MANIFEST.sha256.sig').write_text('signature')
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        verify=lambda *a: registry.Result(0)))
    return api, base


def test_in_use_markers_do_not_change_measure(tmp_path, monkeypatch):
    api, base = signed(tmp_path, monkeypatch)
    clean = api.measure(base)
    assert clean.exit == 0
    (base / '.in_use').mkdir()
    (base / '.in_use/12345').write_text('')
    assert api.measure(base) == clean
    (base / '.in_use/12345').unlink()
    (base / '.in_use/23456').write_text('')
    assert api.measure(base) == clean


def test_in_use_markers_across_an_upgrade(tmp_path, monkeypatch):
    """#353: two cached versions, each with a live marker, measure clean and name each other."""
    (tmp_path / 'cache').mkdir()
    bases, clean = [], []
    for version, pid in (('0.12.0', '12345'), ('0.13.0', '23456')):
        api, built = signed(tmp_path / version, monkeypatch)
        base = built.rename(tmp_path / 'cache' / version)
        clean.append(api.measure(base))
        (base / '.in_use').mkdir()
        (base / '.in_use' / pid).write_text('')
        bases.append(base)
    for base, before, other in zip(bases, clean, reversed(bases)):
        assert before.exit == 0 and api.measure(base) == before
        monkeypatch.setattr(api, 'PLUGIN', base)
        assert api.other_versions() == [other.name]


@pytest.mark.parametrize('shape, fragment', [
    ('file', 'not a Claude Code process marker: .in_use/evil.py'),
    ('directory', 'not a Claude Code process marker: .in_use/sub'),
    ('symlinked marker', 'not a Claude Code process marker: .in_use/12345'),
    ('nested', 'charters/.in_use/12345'),
    ('root symlink', 'symlink in installed plugin: .in_use')])
def test_in_use_cannot_hide_other_content(tmp_path, monkeypatch, shape, fragment):
    api, base = signed(tmp_path, monkeypatch)
    markers = base / '.in_use'
    if shape == 'root symlink':
        (tmp_path / 'elsewhere').mkdir()
        markers.symlink_to(tmp_path / 'elsewhere', target_is_directory=True)
    elif shape == 'nested':
        (base / 'charters/.in_use').mkdir()
        (base / 'charters/.in_use/12345').write_text('')
    else:
        markers.mkdir()
        if shape == 'file':
            (markers / 'evil.py').write_text('print(1)\n')
        elif shape == 'directory':
            (markers / 'sub').mkdir()
        else:
            (markers / '12345').symlink_to(base / 'charters/builder.md')
    result = api.measure(base)
    assert result.exit == 1 and fragment in result.reason


def test_fresh_ignores_markers_but_not_other_in_use_entries(fresh_plugin):
    import os
    api, base, root = fresh_plugin
    later = (root / '.wuwei/integrity/verdict.json').stat().st_mtime + 10
    (base / '.in_use').mkdir()
    (base / '.in_use/12345').write_text('')
    os.utime(base / '.in_use/12345', (later, later))
    assert api.fresh(root) == registry.Result(0)
    (base / '.in_use/evil.py').write_text('')
    result = api.fresh(root)
    assert result.exit != 0 and '.in_use/evil.py' in result.reason
    (base / '.in_use/evil.py').unlink()
    (base / 'cli/.in_use').mkdir()
    (base / 'cli/.in_use/12345').write_text('')
    os.utime(base / 'cli/.in_use/12345', (later, later))
    result = api.fresh(root)
    assert result.exit == 1 and 'cli/.in_use/12345' in result.reason


def test_confirmation_survives_marker_churn(tmp_path, monkeypatch):
    api, base = signed(tmp_path, monkeypatch)
    root = workspace_root(tmp_path)
    monkeypatch.setattr(api, 'PLUGIN', base)
    shutil.copyfile(base / api.KEY, root / '.wuwei/integrity/pinned.pub')
    (base / '.in_use').mkdir()
    (base / '.in_use/12345').write_text('')
    assert api.check(root).exit == 0 and api.cached(root).exit == 0
    (base / 'charters/builder.md').write_text('Changed\n')
    assert api.reconfirm(root, confirm=lambda digest: True).exit == 0
    (base / '.in_use/12345').unlink()
    (base / '.in_use/23456').write_text('')
    result = api.check(root)
    assert result.exit == 0 and 'owner-confirmed' in result.reason
    assert api.cached(root).exit == 0


def test_release_asset_through_the_launcher_with_a_marker(tmp_path, monkeypatch):
    import os
    import runpy
    if not shutil.which('ssh-keygen'):
        pytest.skip('ssh-keygen absent; in-process marker coverage still runs')
    api = core()
    real = ssh()
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(
        sign=lambda manifest, key: Path(str(manifest) + '.sig').write_text('signature') and registry.Result(0),
        verify=lambda *a: registry.Result(0)))
    runpy.run_path(str(ROOT / 'scripts/build-release.py'))['build'](
        ROOT, tmp_path / 'release', tmp_path / 'unused-key')
    stage = tmp_path / 'release/wuwei'
    key = tmp_path / 'owner'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                   check=True, capture_output=True)
    shutil.copyfile(str(key) + '.pub', stage / api.KEY)
    (stage / 'MANIFEST.sha256.sig').unlink()
    api.write_manifest(stage)
    assert real.sign(stage / api.MANIFEST, key).exit == 0
    (stage / '.in_use').mkdir()
    (stage / '.in_use/12345').write_text('')
    path = tmp_path / 'path'
    path.mkdir()
    (path / 'python3').symlink_to(sys.executable)
    home = tmp_path / 'home'
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k != 'WUWEI_WORKSPACE'}
    env.update(PATH=str(path) + os.pathsep + env['PATH'], HOME=str(home))
    ws = tmp_path / 'ws'
    def wuwei(*args, stdin=None, cwd=tmp_path):
        return subprocess.run([str(stage / 'bin/wuwei'), *args], input=stdin, env=env, cwd=cwd,
                              capture_output=True, text=True, timeout=60)
    payload = json.dumps({'cwd': str(ws), 'session_id': 'test', 'transcript_path': 'transcript',
                          'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                          'tool_input': {'command': 'ls'}})
    init = wuwei('init', str(ws))
    assert init.returncode == 0 and 'plugin integrity: clean' in init.stdout, init.stdout + init.stderr
    hook = wuwei('hook', 'PreToolUse', stdin=payload)
    assert hook.returncode == 0, hook.stdout + hook.stderr
    (stage / '.in_use/23456').write_text('')
    check = wuwei('integrity', 'check', cwd=ws)
    assert check.returncode == 0, check.stdout + check.stderr
    assert wuwei('hook', 'PreToolUse', stdin=payload).returncode == 0


def test_both_paths_cached(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    copy_a, copy_b = (tmp_path / 'a/plugin').resolve(), (tmp_path / 'b/plugin').resolve()
    (root / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 0, 'fingerprint': 'a' * 64, 'reason': '', 'plugin': str(copy_a),
         'checkout': {'head': 'b' * 40, 'clean': True}}))
    monkeypatch.setattr(api, 'PLUGIN', copy_b)
    result = api.cached(root)
    assert result.exit == 2
    for text in (f'confirmed the plugin at {copy_a}', f'runs {copy_b}', f'claude --plugin-dir {copy_a}',
                 'bin/wuwei integrity reconfirm in a host terminal'):
        assert text in result.reason, text
    monkeypatch.setattr(api, 'PLUGIN', copy_a)
    assert 'confirmed the plugin at' not in api.cached(root).reason


def test_both_paths_check(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    base = plugin(tmp_path)
    monkeypatch.setattr(api, 'PLUGIN', base)
    monkeypatch.setattr(api, 'signature_adapter', lambda: Namespace(verify=lambda *a: registry.Result(0)))
    api.write_manifest(base)
    shutil.copyfile(base / api.KEY, root / '.wuwei/integrity/pinned.pub')
    (base / 'charters/builder.md').write_text('Changed\n')
    assert api.reconfirm(root, confirm=lambda digest: True).exit == 0
    assert json.loads((root / '.wuwei/integrity/confirmation.json').read_text())['plugin'] == str(base)
    assert json.loads((root / '.wuwei/integrity/verdict.json').read_text())['plugin'] == str(base)
    other = tmp_path / 'other'
    shutil.copytree(base, other)
    (other / 'charters/builder.md').write_text('Other\n')
    monkeypatch.setattr(api, 'PLUGIN', other)
    result = api.check(root)
    assert result.exit == 1 and f'confirmed the plugin at {base}' in result.reason
    assert f'runs {other}' in result.reason


def test_both_paths_old_records(tmp_path, monkeypatch):
    api = core()
    root = workspace_root(tmp_path)
    (root / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 0, 'fingerprint': 'a' * 64, 'reason': ''}))
    monkeypatch.setattr(api, 'PLUGIN', tmp_path / 'anywhere')
    assert api.cached(root).exit == 0
    # A signed release verifies wherever it runs: another copy's clean verdict still holds.
    (root / '.wuwei/integrity/verdict.json').write_text(json.dumps(
        {'exit': 0, 'fingerprint': 'a' * 64, 'reason': '', 'plugin': str(tmp_path / 'other')}))
    assert api.cached(root).exit == 0


def release_install(path):
    (path / 'bin').mkdir(parents=True)
    (path / 'bin/wuwei').write_text('#!/bin/sh\n')
    (path / 'MANIFEST.sha256.sig').write_text('sig\n')
    return path


def test_launcher_prefers_the_registered_install(tmp_path, monkeypatch):
    # #601: the hooks run the registered install; .wuwei/executable names it whichever launcher ran.
    api = core()
    a, b = release_install(tmp_path / 'a'), release_install(tmp_path / 'b')
    monkeypatch.setattr(api, 'PLUGIN', b)
    plugins = Path.home() / '.claude/plugins/installed_plugins.json'
    plugins.parent.mkdir(parents=True)
    root = tmp_path / 'ws'
    root.mkdir()
    assert api.registered(root) is None
    assert api.launcher(root) == b / 'bin/wuwei'
    for data in ({'version': 2, 'plugins': {}},
                 {'version': 2, 'plugins': {'wuwei@wuwei': [{'installPath': str(tmp_path / 'empty')}]}}):
        plugins.write_text(json.dumps(data))
        assert api.launcher(root) == b / 'bin/wuwei'
    plugins.write_text('{')
    with pytest.raises(ValueError):
        api.registered(root)
    assert api.launcher(root) == b / 'bin/wuwei'
    plugins.write_text(json.dumps({'version': 2, 'plugins': {
        'other@market': [{'installPath': str(b)}], 'wuwei@wuwei': [{'scope': 'user', 'installPath': str(a)}]}}))
    assert api.registered(root) == a
    assert api.launcher(root) == a / 'bin/wuwei'
    (b / '.git').mkdir()
    (b / 'MANIFEST.sha256.sig').unlink()
    assert api.development()
    assert api.launcher(root) == b / 'bin/wuwei'
