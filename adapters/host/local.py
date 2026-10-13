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


def processes(orphans=False, pid=None, root=None):
    """The current user's process table; only orphans need a cwd lookup."""
    try:
        result = subprocess.run(['ps', '-ww', *(['-p', str(pid)] if pid is not None else ['-u', str(os.getuid())]), '-o',
                                 'pid,ppid,etime,lstart,command'],
                                capture_output=True, text=True, timeout=5, env={**os.environ, 'LC_ALL': 'C'})
        if result.returncode and not (pid is not None and result.returncode == 1 and not result.stderr):
            raise ValueError(f'ps exited {result.returncode}')
        rows = {}
        for line in result.stdout.splitlines()[1:]:
            fields = line.split(None, 8)
            if len(fields) != 9:
                raise ValueError('invalid ps process row')
            pid, ppid = int(fields[0]), int(fields[1])
            rows[pid] = {'pid': pid, 'ppid': ppid, 'etime': fields[2],
                         'identity': ' '.join(fields[3:8]), 'command': fields[8], 'cwd': None}
        if not orphans:
            return Result(0, rows)
        orphans = [pid for pid, row in rows.items() if row['ppid'] == 1]
        if sys.platform == 'linux':
            for pid in orphans:
                try:
                    rows[pid]['cwd'] = os.readlink(f'/proc/{pid}/cwd')
                except FileNotFoundError:
                    pass  # exited processes and zombies have no cwd
                except OSError as exc:
                    rows[pid]['error'] = str(exc)
        elif sys.platform == 'darwin' and orphans:
            try:
                result = subprocess.run(['lsof', '-a', '-p', ','.join(map(str, orphans)), '-d', 'cwd', '-Fpn'],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode not in (0, 1):
                    raise ValueError(f'lsof exited {result.returncode}')
                pid = None
                for line in result.stdout.splitlines():
                    if line.startswith('p'):
                        pid = int(line[1:])
                    elif line.startswith('n') and pid in rows:
                        rows[pid]['cwd'] = line[1:]
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                for pid in orphans:
                    rows[pid]['error'] = str(exc)
        elif sys.platform not in ('linux', 'darwin'):
            raise ValueError('unsupported host platform')
        return Result(0, rows)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Result(2, None, f'processes unmeasured: {exc}')


def terminate_process(record, grace, root=None):
    """Signal one recorded process, checking PID, start and exact command before each signal."""
    import signal
    import time
    try:
        pid = record['pid']
        if type(pid) is not int or pid <= 1 or pid == os.getpid():
            raise ValueError('refusing unsafe process id')
        for sig in (signal.SIGTERM, signal.SIGKILL, None):
            found = processes(pid=pid, root=root)
            if found.exit:
                return found
            row = found.data.get(pid)
            if row is None:
                return Result(0, True)
            if sig != signal.SIGTERM and row.get('identity') == record.get('identity') and 'defunct' in row['command']:
                return Result(0, True, f'pid {pid} signalled; zombie awaits parent reaping')
            if not all(record.get(key) and record[key] == row.get(key) for key in ('command', 'identity')):
                return Result(1, False, f'pid {pid} identity changed; no further signal sent')
            if sig is None:
                return Result(2, False, f'pid {pid} signalled but still visible after SIGKILL; inspect with doctor --section processes')
            os.kill(pid, sig)
            time.sleep(grace if sig == signal.SIGTERM else 0.05)
    except ProcessLookupError:
        return Result(0, True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return Result(2, False, f'process cleanup unmeasured: {exc}')
