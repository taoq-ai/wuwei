"""Execute a configured fast check in its checkout, without storing output."""

import os
import re
import subprocess

from wuwei.registry import Result


def run(path, command, root=None):
    try:
        if not isinstance(command, str) or not command.strip():
            raise ValueError('empty fast check')
        result = subprocess.run(['/bin/sh', '-c', command], cwd=path, timeout=300,
                                capture_output=True, text=True,
                                env={key: value for key, value in os.environ.items()
                                     if not key.startswith('GIT_')})
        if result.returncode == 0:
            return Result(0)
        output = ((result.stdout or "") + "\n" + (result.stderr or ""))[-8192:]
        ids = re.findall(r'^FAILED\s+(\S+?::\S+)(?:\s|$)', output, re.M)
        return Result(1, {'test_ids': ids, 'error': output})
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'fast check could not run: {type(exc).__name__}')
