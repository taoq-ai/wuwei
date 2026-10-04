"""Bounded, stdlib-only host memory measurement."""

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
