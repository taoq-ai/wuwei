"""The signed release inventory: every shipped file's sha256, signed with the release key."""

import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile

PLUGIN = Path(__file__).resolve().parents[2]
KEY = 'keys/manifest-signing-key.pub'
MANIFEST = 'MANIFEST.sha256'
EXCLUDED = {MANIFEST, MANIFEST + '.sig'}
NAMESPACE = 'wuwei-manifest'


def inventory(plugin):
    plugin = Path(plugin)
    files = {}
    for directory, dirs, names in os.walk(plugin):
        dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__', '.in_use'))
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(plugin).as_posix()
            mode = os.lstat(path).st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f'symlink in plugin: {relative}')
            if stat.S_ISREG(mode) and relative not in EXCLUDED and not name.endswith('.pyc'):
                files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def write_manifest(plugin):
    files = inventory(plugin)
    (Path(plugin) / MANIFEST).write_text(''.join(f'{files[n]}  {n}\n' for n in sorted(files)), encoding='utf-8')


def sign(plugin, key):
    done = subprocess.run(['ssh-keygen', '-Y', 'sign', '-n', NAMESPACE, '-f', str(Path(key).resolve()),
                           str((Path(plugin) / MANIFEST).resolve())], capture_output=True, timeout=30)
    if done.returncode:
        raise OSError('manifest signing failed')


def measure(plugin=PLUGIN):
    """Problems with the installed plugin against its signed manifest; empty means intact."""
    plugin = Path(plugin)
    manifest, signature = plugin / MANIFEST, plugin / (MANIFEST + '.sig')
    if not manifest.is_file() or not signature.is_file():
        return ['unsigned: no MANIFEST.sha256 or signature (a development checkout)']
    with tempfile.TemporaryDirectory() as scratch:
        signers = Path(scratch) / 'allowed_signers'
        signers.write_text('wuwei ' + (plugin / KEY).read_text(encoding='utf-8').strip() + '\n', encoding='utf-8')
        done = subprocess.run(['ssh-keygen', '-Y', 'verify', '-f', str(signers), '-I', 'wuwei', '-n', NAMESPACE,
                               '-s', str(signature)], input=manifest.read_bytes(), capture_output=True, timeout=30)
    problems = [] if done.returncode == 0 else ['manifest signature does not match the release key']
    expected = dict(reversed(line.split('  ', 1)) for line in manifest.read_text(encoding='utf-8').splitlines() if line)
    actual = inventory(plugin)
    problems += [f'changed: {name}' for name in sorted(expected.keys() | actual.keys()) if expected.get(name) != actual.get(name)]
    return problems
