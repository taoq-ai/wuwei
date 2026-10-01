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


def measure(plugin=None, pinned=None, *, checkout=None, root=None):
    plugin = PLUGIN if plugin is None else Path(plugin)
    try:
        if checkout is None:
            actual = inventory(plugin)
        else:
            vcs = registry.load('vcs', workspace.load_config(root))
            tree = vcs.read_tree(plugin, checkout['head'], ['.'], root=root)
            if tree.exit:
                return Result(2, reason='checkout tracked files unmeasured: ' + tree.reason)
            if (not isinstance(tree.data, dict) or not tree.data
                    or not all(isinstance(name, str) for name in tree.data)):
                return Result(2, reason='invalid checkout tracked files evidence')
            actual = {}
            for name in tree.data:
                relative = Path(_name(name))
                if any((plugin / part).is_symlink() for part in (relative, *relative.parents)):
                    raise ValueError(f'symlink in installed plugin: {name}')
                actual[name] = hashlib.sha256((plugin / relative).read_bytes()).hexdigest()
        key = plugin / KEY
        signature = plugin / (MANIFEST + '.sig')
        manifest = plugin / MANIFEST
        for path in (manifest, signature, key):
            if path.is_symlink():
                raise ValueError(f'symlink in installed plugin: {path.name}')
        result = (Result(1, reason='development checkout requires host reconfirmation; '
                          'run wuwei integrity reconfirm on the host')
                  if checkout is not None else signature_adapter().verify(manifest, signature, key))
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
            **({'checkout': checkout} if checkout is not None else {}),
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


def _checkout(root):
    # Partial release artifacts must still go through signature verification.
    if any((PLUGIN / name).exists() or (PLUGIN / name).is_symlink() for name in EXCLUDED):
        return None
    git = PLUGIN / '.git'
    if git.is_symlink():
        raise ValueError('checkout .git must not be a symlink')
    if not git.exists():
        return None
    vcs = registry.load('vcs', workspace.load_config(root))
    head = vcs.head(PLUGIN, root=root)
    if head.exit:
        raise ValueError('checkout HEAD unmeasured: ' + head.reason)
    if (not isinstance(head.data, dict) or not isinstance(head.data.get('sha'), str)
            or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', head.data['sha'])):
        raise ValueError('invalid checkout HEAD evidence')
    status = vcs.status(PLUGIN, root=root)
    if status.exit:
        raise ValueError('checkout tree unmeasured: ' + status.reason)
    if (not isinstance(status.data, list) or not all(
            isinstance(entry, dict) and all(isinstance(entry.get(key), str)
                                          for key in ('path', 'index', 'worktree'))
            for entry in status.data)):
        raise ValueError('invalid checkout status evidence')
    return {'head': head.data['sha'], 'clean': not status.data}


def check(root):
    try:
        _record(root, 'verdict.json', {'exit': 2, 'fingerprint': None,
                                     'reason': 'plugin integrity measurement incomplete'})
        checkout = _checkout(root)
        result = (Result(1, reason='page: plugin integrity: dirty development checkout; restore a clean commit '
                                 'and run wuwei integrity reconfirm on the host')
                  if checkout is not None and not checkout['clean'] else
                  measure(pinned=_path(root, 'pinned.pub'), checkout=checkout, root=root))
        confirmation = _path(root, 'confirmation.json')
        if result.exit == 1 and result.data and confirmation.exists():
            record = json.loads(confirmation.read_text())
            if (isinstance(record, dict) and record.get('fingerprint') == result.data
                    and record.get('checkout') == checkout):
                result = Result(0, result.data, 'plugin integrity: owner-confirmed content (local evidence)')
        _record(root, 'verdict.json', {'exit': result.exit, 'fingerprint': result.data,
                                     'reason': result.reason, 'checkout': checkout})
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
        if record.get('checkout') is not None:
            current = _checkout(root)
            if current != record['checkout'] or not current or not current['clean']:
                return Result(2, reason='plugin integrity: checkout HEAD or tree changed; '
                              'restore a clean commit and run wuwei integrity reconfirm on the host')
        return Result(0)
    except (OSError, ValueError, TypeError) as exc:
        return Result(2, reason=f'plugin integrity unmeasured: {exc}; run wuwei integrity check on the host')


def fresh(root):
    """The cached verdict, also stale when an installed file changed after it (release installs).

    Mtimes are tamper evidence, not a boundary (spec 7.1, 9.1); a checkout is covered by cached.
    """
    result = cached(root)
    if result.exit:
        return result
    try:
        path = _path(root, 'verdict.json')
        if json.loads(path.read_text()).get('checkout') is not None:
            return result
        since = path.stat().st_mtime
        def failed(error):
            raise error
        for directory, dirs, names in os.walk(PLUGIN, onerror=failed):
            dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__'))
            for name in sorted(names):
                file = Path(directory) / name
                if not name.endswith('.pyc') and file.lstat().st_mtime > since:
                    return Result(1, reason=f'page: plugin integrity: {file.relative_to(PLUGIN).as_posix()} '
                                  'changed after the cached verdict; run wuwei integrity check on the host')
        return result
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return Result(2, reason=f'plugin integrity unmeasured: {exc}')


HOST_TERMINAL = 'this is an owner action: run it in a host terminal'


def _host_confirm(fingerprint, *, prompt='Review the installation on this host. To confirm its exact content, type:'):
    # This is a local friction boundary, not proof against a same-uid process (spec 9.1).
    try:
        reader = open('/dev/tty', 'r')
    except OSError:
        raise OSError(HOST_TERMINAL) from None
    with reader:
        try:
            terminal = open('/dev/tty', 'w')
        except OSError:
            raise OSError(HOST_TERMINAL) from None
        with terminal:
            if not reader.isatty() or not terminal.isatty():
                raise OSError(HOST_TERMINAL)
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
        verdict = json.loads(_path(root, 'verdict.json').read_text())
        _record(root, 'confirmation.json', {'fingerprint': result.data,
                                          'checkout': verdict.get('checkout')})
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
