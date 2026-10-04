"""Fixed SSH manifest signing and verification boundary."""

from pathlib import Path
import subprocess
import shutil
import tempfile

from wuwei.registry import Result


def _run(args, *, data=None):
    match args:
        case ['-Y', 'sign', '-n', 'wuwei-manifest', '-f', key, manifest]:
            allowed = all(Path(p).is_absolute() for p in (key, manifest))
        case ['-Y', 'verify', '-f', allowed_signers, '-I', 'wuwei', '-n', 'wuwei-manifest', '-s', signature]:
            allowed = all(Path(p).is_absolute() for p in (allowed_signers, signature))
        case _:
            allowed = False
    if not allowed:
        raise ValueError('unsupported ssh-keygen command')
    return subprocess.run(['ssh-keygen', *args], input=data, capture_output=True,
                          timeout=30, check=False)


def sign(manifest, key, root=None):
    try:
        result = _run(['-Y', 'sign', '-n', 'wuwei-manifest', '-f',
                       str(Path(key).resolve()), str(Path(manifest).resolve())])
        return Result(0) if result.returncode == 0 else Result(2, reason='manifest signing failed')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'ssh-keygen signing unmeasured: {type(exc).__name__}')


def verify(manifest, signature, key, root=None):
    try:
        if shutil.which('ssh-keygen') is None:
            raise FileNotFoundError('ssh-keygen')
        # Missing files are evidence of an unsigned install; unreadable files are unmeasured.
        if not Path(manifest).exists() or not Path(signature).exists():
            return Result(1, reason='missing MANIFEST.sha256 or signature')
        Path(signature).read_bytes()
        public_key = Path(key).read_text(encoding='utf-8').strip()
        if '\n' in public_key:
            return Result(1, reason='invalid pinned public key')
        with tempfile.TemporaryDirectory() as directory:
            signers = Path(directory) / 'allowed_signers'
            signers.write_text('wuwei ' + public_key + '\n', encoding='utf-8')
            result = _run(['-Y', 'verify', '-f', str(signers), '-I', 'wuwei',
                           '-n', 'wuwei-manifest', '-s', str(Path(signature).resolve())],
                          data=Path(manifest).read_bytes())
        if result.returncode:
            return Result(1, reason='manifest signature does not match pinned key')
        return Result(0)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'ssh-keygen verification unmeasured: {type(exc).__name__}')
