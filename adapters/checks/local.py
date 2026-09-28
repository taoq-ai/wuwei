"""Execute a configured fast check in its checkout, without storing output."""

import os
import subprocess

from wuwei.registry import Result


def run(path, command, root=None):
    try:
        if not isinstance(command, str) or not command.strip():
            raise ValueError('empty fast check')
        result = subprocess.run(['/bin/sh', '-c', command], cwd=path, timeout=300,
                                env={key: value for key, value in os.environ.items()
                                     if not key.startswith('GIT_')})
        return Result(0 if result.returncode == 0 else 1)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'fast check could not run: {type(exc).__name__}')
