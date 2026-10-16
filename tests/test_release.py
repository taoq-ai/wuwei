import ast
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_release', REPO / 'scripts' / 'build-release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

needs_ssh_keygen = pytest.mark.skipif(shutil.which('ssh-keygen') is None, reason='ssh-keygen is absent')


@pytest.fixture
def signed(tmp_path, monkeypatch):
    """A copy of the shipped tree whose release key is a throwaway ed25519 key, built and signed."""
    key = tmp_path / 'key'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'test', '-f', str(key)], check=True)
    root = tmp_path / 'root'
    for name in release.SHIPPED:
        shutil.copytree(REPO / name, root / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'LICENSE'):
        shutil.copyfile(REPO / name, root / name)
    shutil.copyfile(key.with_suffix('.pub'), root / release.KEY)
    monkeypatch.setattr(release, 'ROOT', root)
    output = tmp_path / 'out'
    archive = release.build(output, key)
    return archive, key, output / 'wuwei'


@needs_ssh_keygen
def test_build_writes_an_archive_whose_manifest_verifies_and_lists_every_shipped_file(signed, tmp_path):
    archive, key, _ = signed
    assert archive.name == 'wuwei.tar.gz'
    unpacked = tmp_path / 'unpacked'
    with tarfile.open(archive) as tar:
        tar.extractall(unpacked, filter='data')
    plugin = unpacked / 'wuwei'
    signers = tmp_path / 'allowed_signers'
    signers.write_text('wuwei ' + key.with_suffix('.pub').read_text().strip() + '\n')
    manifest = (plugin / release.MANIFEST).read_bytes()
    done = subprocess.run(['ssh-keygen', '-Y', 'verify', '-f', str(signers), '-I', 'wuwei', '-n', release.NAMESPACE,
                           '-s', str(plugin / (release.MANIFEST + '.sig'))], input=manifest, capture_output=True)
    assert done.returncode == 0, done.stderr
    listed = {line.split('  ', 1)[1] for line in manifest.decode().splitlines()}
    shipped = {p.relative_to(plugin).as_posix() for p in plugin.rglob('*') if p.is_file()} - release.EXCLUDED
    assert listed == shipped
    assert 'cli/wuwei/hook.py' in listed and 'README.md' in listed
    assert release.measure(plugin) == []


@needs_ssh_keygen
def test_the_measure_names_a_file_changed_after_signing(signed):
    _, _, stage = signed
    (stage / 'README.md').write_text('tampered\n')
    assert release.measure(stage) == ['changed: README.md']


def test_the_inventory_refuses_a_symlink(tmp_path):
    (tmp_path / 'real.txt').write_text('x')
    os.symlink(tmp_path / 'real.txt', tmp_path / 'link.txt')
    with pytest.raises(ValueError, match='symlink in plugin: link.txt'):
        release.inventory(tmp_path)


def test_no_runtime_module_is_or_imports_integrity():
    runtime = REPO / 'cli' / 'wuwei'
    assert not (runtime / 'integrity.py').exists()
    for path in runtime.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ''] + [a.name for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            assert not any('integrity' in name for name in names), path.name
