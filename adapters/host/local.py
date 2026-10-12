"""Bounded, stdlib-only host memory measurement."""

import os
from pathlib import Path
import re
import subprocess
import sys

from wuwei.registry import Result


def free_memory(root=None):
    try:
        if sys.platform == 'darwin':
            result = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise ValueError(f'vm_stat exited {result.returncode}')
            size = re.search(r'page size of (\d+) bytes', result.stdout)
            counts = [re.search(r'^Pages ' + name + r':\s+(\d+)\.$', result.stdout, re.M)
                      for name in ('free', 'inactive', 'speculative')]
            if not size or not all(counts):
                raise ValueError('invalid vm_stat output')
            pages, page_size = sum(int(count[1]) for count in counts), int(size[1])
        elif sys.platform == 'linux':
            available = re.search(r'^MemAvailable:\s+(\d+) kB\s*$',
                                  Path('/proc/meminfo').read_text(), re.M)
            if not available:
                raise ValueError('invalid MemAvailable in /proc/meminfo')
            pages, page_size = int(available[1]), 1024
        else:
            raise ValueError('unsupported host platform')
        if pages < 0 or page_size <= 0:
            raise ValueError('invalid page count or size')
        return Result(0, pages * page_size)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, None, f'free memory unmeasured: {exc}')


def free_percent(root=None):
    """#898: the share of the host free, 0-100: macOS memory_pressure's figure, Linux
    MemAvailable over MemTotal."""
    try:
        if sys.platform == 'darwin':
            result = subprocess.run(['memory_pressure'], capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise ValueError(f'memory_pressure exited {result.returncode}')
            found = re.search(r'^System-wide memory free percentage: (\d+)%$', result.stdout, re.M)
            if not found:
                raise ValueError('invalid memory_pressure output')
            percent = int(found[1])
        elif sys.platform == 'linux':
            text = Path('/proc/meminfo').read_text()
            total, available = (re.search(rf'^{name}:\s+(\d+) kB\s*$', text, re.M)
                                for name in ('MemTotal', 'MemAvailable'))
            if not total or not available or not int(total[1]):
                raise ValueError('invalid MemTotal or MemAvailable in /proc/meminfo')
            percent = int(available[1]) * 100 // int(total[1])
        else:
            raise ValueError('unsupported host platform')
        if not 0 <= percent <= 100:
            raise ValueError(f'percentage {percent} out of range')
        return Result(0, percent)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, None, f'free memory percentage unmeasured: {exc}')


def hand_over(target, argv, env, root=None):
    """#645: replace this process with target; returns only when the exec failed."""
    try:
        os.execve(target, argv, env)
    except OSError as exc:  # never the message: the caller names the launcher and the class only
        return Result(2, None, type(exc).__name__)
