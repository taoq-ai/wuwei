"""Authenticated release inventories and cached workspace verdicts."""

import hashlib
import json
import os
from pathlib import Path
import re

from wuwei import registry, workspace
from wuwei.registry import Result

PLUGIN = Path(__file__).resolve().parents[2]
KEY = 'keys/manifest-signing-key.pub'
MANIFEST = 'MANIFEST.sha256'
EXCLUDED = {MANIFEST, MANIFEST + '.sig'}


def signature_adapter():
    # Fixed trust mechanism, never selected by workspace configuration.
    return registry.load('integrity', {'adapters': {'integrity': 'ssh'}})


def _name(name):
    if (not name or name.startswith('/') or '\\' in name
            or any(part in ('', '.', '..') for part in name.split('/'))
            or any(ord(c) < 32 for c in name)):
        raise ValueError(f'invalid inventory path: {name!r}')
    return name


def inventory(plugin):
    plugin = Path(plugin)
    if not plugin.is_dir():
        raise OSError('installed plugin directory missing')
    files = {}
    def failed(error):
        raise error
    for directory, dirs, names in os.walk(plugin, onerror=failed):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
        for name in dirs + names:
            path = Path(directory) / name
            relative = path.relative_to(plugin).as_posix()
            if path.is_symlink():
                raise ValueError(f'symlink in installed plugin: {relative}')
            if path.is_file() and relative not in EXCLUDED and not name.endswith('.pyc'):
                files[_name(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def write_manifest(plugin):
    files = inventory(plugin)
    workspace.atomic_write(Path(plugin) / MANIFEST, ''.join(
        f'{files[name]}  {name}\n' for name in sorted(files)))


def measure(plugin=None, pinned=None):
    plugin = PLUGIN if plugin is None else Path(plugin)
    try:
        actual = inventory(plugin)
        key = plugin / KEY
        signature = plugin / (MANIFEST + '.sig')
        manifest = plugin / MANIFEST
        for path in (manifest, signature, key):
            if path.is_symlink():
                raise ValueError(f'symlink in installed plugin: {path.name}')
        result = signature_adapter().verify(manifest, signature, key)
        if result.exit == 2:
            return result
        reasons = [result.reason] if result.exit else []
        if pinned is not None and Path(pinned).read_bytes() != key.read_bytes():
            reasons.append('workspace pinned key differs from plugin key')
        if manifest.exists():
            expected = {}
            for line in manifest.read_text(encoding='utf-8').splitlines():
                match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
                if not match:
                    raise ValueError('malformed MANIFEST.sha256')
                name = _name(match[2])
                if name in expected or name in EXCLUDED:
                    raise ValueError(f'duplicate or reserved inventory path: {name}')
                expected[name] = match[1]
            reasons.extend(name for name in sorted(expected.keys() | actual.keys())
                           if expected.get(name) != actual.get(name))
        fingerprint = hashlib.sha256(json.dumps({
            'files': actual,
            'manifest': hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.exists() else None,
            'signature': hashlib.sha256(signature.read_bytes()).hexdigest() if signature.exists() else None,
            'pinned': Path(pinned).read_text() if pinned is not None else None,
        }, sort_keys=True).encode()).hexdigest()
        return Result(int(bool(reasons)), fingerprint,
                      'page: plugin integrity: ' + '; '.join(reasons) if reasons else '')
    except (OSError, UnicodeError) as exc:
        return Result(2, reason=f'plugin integrity unmeasured: {exc}')
    except ValueError as exc:
        return Result(1, reason=f'page: plugin integrity: {exc}')


def _path(root, name):
    path = Path(root) / '.wuwei/integrity' / name
    if any(p.is_symlink() for p in (path, path.parent, path.parent.parent)):
        raise ValueError('integrity records must not use symlinks')
    return path


def _record(root, name, data):
    path = _path(root, name)
    path.parent.mkdir(exist_ok=True)
    workspace.atomic_write(path, json.dumps(data, sort_keys=True) + '\n', mode=0o444)


def check(root):
    try:
        _record(root, 'verdict.json', {'exit': 2, 'fingerprint': None,
                                     'reason': 'plugin integrity measurement incomplete'})
        result = measure(pinned=_path(root, 'pinned.pub'))
        confirmation = _path(root, 'confirmation.json')
        if result.exit == 1 and result.data and confirmation.exists():
            record = json.loads(confirmation.read_text())
            if isinstance(record, dict) and record.get('fingerprint') == result.data:
                result = Result(0, result.data, 'plugin integrity: owner-confirmed content (local evidence)')
        _record(root, 'verdict.json', {'exit': result.exit, 'fingerprint': result.data,
                                     'reason': result.reason})
        return result
    except (OSError, ValueError, TypeError) as exc:
        return Result(2, reason=f'plugin integrity unmeasured: {exc}')


def cached(root):
    try:
        record = json.loads(_path(root, 'verdict.json').read_text())
        if (not isinstance(record, dict) or type(record.get('exit')) is not int
                or record['exit'] not in (0, 1, 2) or not isinstance(record.get('reason'), str)
                or (record['exit'] == 0 and not re.fullmatch(r'[0-9a-f]{64}', record.get('fingerprint') or ''))):
            raise ValueError('invalid cached integrity verdict')
        if record['exit']:
            return Result(2, reason=record['reason'] or 'plugin integrity unmeasured')
        return Result(0)
    except (OSError, ValueError, TypeError) as exc:
        return Result(2, reason=f'plugin integrity unmeasured: {exc}; run wuwei integrity check on the host')


def _host_confirm(fingerprint, *, prompt='Review the installation on this host. To confirm its exact content, type:'):
    # This is a local friction boundary, not proof against a same-uid process (spec 9.1).
    with open('/dev/tty', 'r') as reader, open('/dev/tty', 'w') as terminal:
        if not reader.isatty() or not terminal.isatty():
            return False
        terminal.write(prompt + '\n' + fingerprint + '\n> ')
        terminal.flush()
        return reader.readline().strip() == fingerprint


def reconfirm(root, *, confirm=None):
    try:
        result = check(root)
        if result.exit == 2 or not result.data:
            return result
        if not (confirm or _host_confirm)(result.data):
            return Result(1, reason='integrity re-confirmation declined')
        # Re-measure after the terminal interaction to avoid confirming a changed tree.
        current = check(root)
        if current.exit == 2 or current.data != result.data:
            return Result(2, reason='integrity changed during confirmation; retry on the host')
        _record(root, 'confirmation.json', {'fingerprint': result.data})
        return check(root)
    except (OSError, ValueError) as exc:
        return Result(2, reason=f'host confirmation unmeasured: {exc}')


def initialize(directory):
    directory = Path(directory)
    (directory / 'integrity').mkdir()
    workspace.atomic_write(directory / 'integrity/pinned.pub', (PLUGIN / KEY).read_text(), mode=0o444)
    vcs = registry.load('vcs', {'adapters': {'vcs': 'git'}})
    result = vcs.workspace_init(directory)
    if result.exit:
        raise OSError(result.reason)


def workspace_check(root):
    try:
        vcs = registry.load('vcs', workspace.load_config(root))
        result = vcs.workspace_changes(Path(root) / '.wuwei', root=root)
        if result.exit:
            return Result(2, reason='workspace integrity unmeasured: ' + result.reason)
        if not isinstance(result.data, list) or not all(isinstance(p, str) for p in result.data):
            raise ValueError('invalid workspace history evidence')
        lines = []
        for path in result.data:
            severity = 'page' if path.startswith(('charters/', 'voice/')) or path in (
                'memory/voice.md', 'voice') else 'nudge'
            lines.append(f'{severity}: workspace integrity: {path} uncommitted or without Promoted-by: wuwei')
        return Result(int(bool(lines)), reason='\n'.join(lines))
    except (OSError, ValueError, TypeError) as exc:
        return Result(2, reason=f'workspace integrity unmeasured: {exc}')
