"""Execute a configured fast check in its checkout, without storing output."""

import re
import subprocess

from wuwei import env
from wuwei.registry import Result


def _environment(output):
    missing = re.search(r"(?:No module named|ModuleNotFoundError: No module named) ['\"]?([\w.-]+)", output)
    if missing:
        module = missing.group(1).split('.')[0]
        if module in ('pytest', 'hypothesis', 'coverage', 'pluggy', 'ruff', 'mypy', 'tox'):
            return f'{module} not found'
    missing = re.search(r'(?:^|\n)(?:/bin/)?sh: (?:(?:line )?\d+: )?([\w.-]+): (?:command )?not found', output)
    if missing:
        return f'{missing.group(1)} not found'
    return None


def run(path, command, timeout=300, root=None):
    try:
        if not isinstance(command, str) or not command.strip():
            raise ValueError('empty fast check')
        result = subprocess.run(['/bin/sh', '-c', command], cwd=path, timeout=timeout,
                                capture_output=True, text=True,
                                env={key: value for key, value in env.child_environment().items()
                                     if not key.startswith('GIT_')})
        if result.returncode == 0:
            return Result(0)
        output = ((result.stdout or "") + "\n" + (result.stderr or ""))[-8192:]
        ids = re.findall(r'^FAILED\s+(\S+?::\S+)(?:\s|$)', output, re.M)
        data = {'test_ids': ids, 'error': output}
        environment = _environment(output)
        if environment:
            data['environment'] = environment
        return Result(1, data)
    except subprocess.TimeoutExpired:  # #724
        return Result(2, reason=f'fast check `{command}` exceeded {timeout} s '
                                '(repos.<n>.check_timeout_seconds); raise it with '
                                'bin/wuwei config set or split the check')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'fast check could not run: {type(exc).__name__}')
