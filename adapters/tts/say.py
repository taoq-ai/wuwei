"""macOS speech adapter."""

from pathlib import Path
import subprocess
import sys

from wuwei.registry import Result


def speak(text, rate, out, root=None):
    if sys.platform != 'darwin':
        return Result(2, reason='say is available only on macOS')
    if not isinstance(text, str) or not text or len(text.split()) > 600:
        return Result(2, reason='speech text invalid or longer than five minutes')
    if not isinstance(rate, int) or not 120 <= rate <= 240:
        return Result(2, reason='speech rate invalid')
    try:
        result = subprocess.run(['say', '-r', str(rate), '-o', str(out), text],
                                capture_output=True, timeout=330, check=False)
        if result.returncode:
            return Result(2, reason='say failed')
        return Result(0, {'performed': True, 'path': str(Path(out))})
    except (OSError, subprocess.SubprocessError):
        return Result(2, reason='say unavailable')
