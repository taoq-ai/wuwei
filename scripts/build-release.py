"""Stage, inventory and sign the installable plugin archive."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ('.claude-plugin', 'cli', 'bin', 'hooks', 'charters', 'skills', 'agents', 'keys')
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


def measure(plugin):
    """Problems with the staged plugin against its signed manifest; empty means intact."""
    plugin = Path(plugin)
    manifest, signature = plugin / MANIFEST, plugin / (MANIFEST + '.sig')
    if not manifest.is_file() or not signature.is_file():
        return ['unsigned: no MANIFEST.sha256 or signature']
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


def build(output, key):
    stage = Path(output) / 'wuwei'
    stage.mkdir(parents=True)
    for name in SHIPPED:
        shutil.copytree(ROOT / name, stage / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'LICENSE', 'NOTICE', 'SECURITY.md'):
        if (ROOT / name).is_file():
            shutil.copyfile(ROOT / name, stage / name)
    write_manifest(stage)
    sign(stage, key)
    problems = measure(stage)
    if problems:
        raise ValueError('; '.join(problems))
    return Path(shutil.make_archive(str(Path(output) / 'wuwei'), 'gztar', output, 'wuwei'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(build(args.output, args.key))
        return 0
    except (OSError, ValueError) as exc:
        print(f'release unmeasured: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
