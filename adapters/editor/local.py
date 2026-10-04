"""Run the owner's selected editor without a shell."""

from pathlib import Path
import shlex
import subprocess

from wuwei.registry import Result


def edit(path, command, root=None):
    try:
        argv = shlex.split(command)
        if not argv or not Path(path).is_file():
            raise ValueError('editor command or edit file is missing')
        result = subprocess.run([*argv, str(path)], check=False)
        if result.returncode:
            return Result(2, reason=f'editor exited {result.returncode}')
        return Result(0)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, reason=f'editor could not run: {exc}')
