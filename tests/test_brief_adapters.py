"""Minimal port extensions needed for brief evidence."""

import importlib

import pytest

from fakes.replay import install_replay
from wuwei import registry


@pytest.mark.parametrize('output,exit_code', [('x-old\nx-new\n', 0), ('', 0), ('bad name\n', 2)])
def test_branches(monkeypatch, output, exit_code):
    adapter = registry.load('vcs', {'adapters': {'vcs': 'git'}})
    install_replay(monkeypatch, 'git', [{'stdout': output}])
    result = adapter.branches('tree', 'x-*')
    assert result.exit == exit_code
    if not exit_code:
        assert result.data == output.splitlines()


@pytest.mark.parametrize('content,expected', [
    ('MemFree: 10 kB\nMemAvailable: 2048 kB\n', 2048 * 1024),
    ('MemAvailable: 0 kB\n', 0), ('MemFree: 10 kB\n', None),
    ('MemAvailable: -1 kB\n', None), ('MemAvailable: 10 MB\n', None),
])
def test_host_memavailable(monkeypatch, content, expected):
    from pathlib import Path
    adapter = importlib.import_module('adapters.host.local')
    monkeypatch.setattr(adapter.sys, 'platform', 'linux')
    def read(path, **kwargs):
        assert str(path) == '/proc/meminfo'
        return content
    monkeypatch.setattr(Path, 'read_text', read)
    result = adapter.free_memory()
    assert (result.exit, result.data) == ((0, expected) if expected is not None else (2, None))


@pytest.mark.parametrize('stdout,exit_code,expected', [
    ('Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 100.\nPages inactive: 200.\nPages speculative: 3.\n', 0, 4964352),
    ('Mach Virtual Memory Statistics: (page size of 4096 bytes)\nPages free: 100.\n', 0, None),
    ('malformed', 0, None), ('', 1, None),
])
def test_host_vm_stat(monkeypatch, stdout, exit_code, expected):
    adapter = importlib.import_module('adapters.host.local')
    monkeypatch.setattr(adapter.sys, 'platform', 'darwin')
    calls = install_replay(monkeypatch, 'vm_stat', [{'stdout': stdout, 'exit': exit_code}])
    result = adapter.free_memory()
    assert (result.exit, result.data) == ((0, expected) if expected is not None else (2, None))
    assert len(calls) == 1


@pytest.mark.parametrize('platform,source,expected', [
    # #898: the share of the host free, as the owner reads it
    ('darwin', 'The system has 34359738368 (2097152 pages with a page size of 16384).\n'
               'System-wide memory free percentage: 38%\n', 38),
    ('darwin', 'System-wide memory free percentage: 100%\n', 100),
    ('darwin', 'malformed', None), ('darwin', '', None),
    ('linux', 'MemTotal: 1000 kB\nMemFree: 10 kB\nMemAvailable: 385 kB\n', 38),
    ('linux', 'MemAvailable: 385 kB\n', None), ('linux', 'MemTotal: 0 kB\nMemAvailable: 0 kB\n', None),
    ('linux', 'MemTotal: 100 kB\nMemAvailable: 200 kB\n', None),
])
def test_host_free_percent(monkeypatch, platform, source, expected):
    from pathlib import Path
    adapter = importlib.import_module('adapters.host.local')
    monkeypatch.setattr(adapter.sys, 'platform', platform)
    if platform == 'darwin':
        calls = install_replay(monkeypatch, 'memory_pressure', [{'stdout': source, 'exit': 0 if source else 1}])
    else:
        monkeypatch.setattr(Path, 'read_text', lambda path, **kwargs: str(path) == '/proc/meminfo' and source)
    result = adapter.free_percent()
    assert (result.exit, result.data) == ((0, expected) if expected is not None else (2, None))
    assert expected is not None or 'free memory percentage unmeasured' in result.reason
    if platform == 'darwin':
        assert calls == [['memory_pressure']]


def test_branches_exact_command_and_failure(monkeypatch):
    adapter = registry.load('vcs', {'adapters': {'vcs': 'git'}})
    calls = install_replay(monkeypatch, 'git', [{'argv': ['-C', 'tree', 'branch', '--list',
        '--format=%(refname:short)', '--', 'team/x-*'], 'exit': 128}])
    result = adapter.branches('tree', 'team/x-*')
    assert result.exit == 2 and result.data is None
    assert len(calls) == 1


@pytest.mark.parametrize('failure', [FileNotFoundError(), ValueError('unreadable meminfo')])
def test_host_unavailable(monkeypatch, failure):
    adapter = registry.load('host', {'adapters': {'host': 'local'}})
    monkeypatch.setattr(adapter.sys, 'platform', 'linux')
    def fail(*args):
        raise failure
    from pathlib import Path
    monkeypatch.setattr(Path, 'read_text', fail)
    assert adapter.free_memory().exit == 2
