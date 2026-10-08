"""Fixed SSH manifest signing and verification boundary."""

import os
from pathlib import Path
import subprocess

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


def _installed():
    # #587: shutil.which without importing shutil on the SessionStart path.
    return any(os.path.isfile(path) and os.access(path, os.X_OK)
               for path in (os.path.join(directory, 'ssh-keygen') for directory in os.get_exec_path()))


def sign(manifest, key, root=None):
    try:
        result = _run(['-Y', 'sign', '-n', 'wuwei-manifest', '-f',
                       str(Path(key).resolve()), str(Path(manifest).resolve())])
        return Result(0) if result.returncode == 0 else Result(2, reason='manifest signing failed')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'ssh-keygen signing unmeasured: {type(exc).__name__}')


def verify(manifest, signature, key, root=None):
    try:
        if not _installed():
            raise FileNotFoundError('ssh-keygen')
        # Missing files are evidence of an unsigned install; unreadable files are unmeasured.
        if not Path(manifest).exists() or not Path(signature).exists():
            return Result(1, reason='missing MANIFEST.sha256 or signature')
        Path(signature).read_bytes()
        public_key = Path(key).read_text(encoding='utf-8').strip()
        if '\n' in public_key:
            return Result(1, reason='invalid pinned public key')
        # A private 0700 directory and an exclusive, no-follow create, as tempfile would do.
        directory = Path(os.path.abspath(os.environ.get('TMPDIR') or '/tmp')) / f'wuwei-{os.urandom(8).hex()}'
        os.mkdir(directory, 0o700)
        signers = directory / 'allowed_signers'
        try:
            descriptor = os.open(signers, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with open(descriptor, 'w', encoding='utf-8') as handle:
                handle.write('wuwei ' + public_key + '\n')
            result = _run(['-Y', 'verify', '-f', str(signers), '-I', 'wuwei',
                           '-n', 'wuwei-manifest', '-s', str(Path(signature).resolve())],
                          data=Path(manifest).read_bytes())
        finally:
            signers.unlink(missing_ok=True)
            directory.rmdir()
        if result.returncode:
            return Result(1, reason='manifest signature does not match pinned key')
        return Result(0)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'ssh-keygen verification unmeasured: {type(exc).__name__}')
