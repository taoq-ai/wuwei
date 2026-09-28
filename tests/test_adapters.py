"""Plain-module adapter contracts and honest unavailable results."""

import importlib
import inspect
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CALLS = [
    ('tracker', 'claim', ('item',), False),
    ('tracker', 'transition', ('item', 'state'), False),
    ('tracker', 'create', ('draft',), False),
    ('tracker', 'history', ('item',), True),
    ('chat', 'post', ('channel', 'text', 'thread'), False),
    ('chat', 'dm', ('text',), False),
    ('review_bot', 'score', ('pr',), True),
    ('review_bot', 'open_findings', ('pr',), True),
    ('runtime', 'dispatch', ('role', 'brief_path', 'worktree', 'write'), False),
    ('runtime', 'status', ('job',), True),
    ('runtime', 'result', ('job',), True),
    ('scanner', 'audit', ('path',), True),
    ('scanner', 'gate', ('result', 'threshold'), True),
    ('scanner', 'traces', ('file',), True),
    ('scanner', 'mcp', ('servers',), True),
]


def registry():
    assert (ROOT / 'cli/wuwei/registry.py').is_file(), 'adapter registry is missing'
    return importlib.import_module('wuwei.registry')


def test_module_contracts():
    api = registry()
    assert api.INTERFACES == {
        kind: tuple(call for group, call, _, _ in CALLS if group == kind)
        for kind in {row[0] for row in CALLS}
    }
    for kind, names in api.INTERFACES.items():
        paths = list((ROOT / 'adapters' / kind).glob('*.py'))
        assert paths
        for path in paths:
            if path.stem.startswith('_'):
                continue
            module = importlib.import_module(f'adapters.{kind}.{path.stem}')
            for call in names:
                operation = getattr(module, call)
                assert inspect.isfunction(operation)
                parameters = next(params for group, name, params, _ in CALLS
                                  if (group, name) == (kind, call))
                assert tuple(inspect.signature(operation).parameters) == (*parameters, 'root')


@pytest.mark.parametrize('operation', [lambda item: None, lambda wrong, root=None: None])
def test_module_contracts_reject_wrong_signature(monkeypatch, operation):
    from adapters.tracker import none

    monkeypatch.setattr(none, 'claim', operation)
    with pytest.raises(AssertionError):
        test_module_contracts()


def test_module_contracts_allow_extra_import(monkeypatch):
    from adapters.tracker import none

    monkeypatch.setattr(none, 'Result', registry().Result, raising=False)
    test_module_contracts()


@pytest.mark.parametrize('kind,call,parameters,measurement', CALLS)
def test_none_call(tmp_path, monkeypatch, capsys, kind, call, parameters, measurement):
    api = registry()
    module = importlib.import_module(f'adapters.{kind}.none')
    operation = getattr(module, call)
    assert tuple(inspect.signature(operation).parameters) == (*parameters, 'root')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    directory = tmp_path / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True)
    (directory / 'state.json').write_text('unchanged')
    reason = 'unmeasured' if measurement else 'no adapter configured'
    for kwargs in ({}, {'root': tmp_path}):
        result = operation(*['private argument'] * len(parameters), **kwargs)
        assert isinstance(result, api.Result)
        assert (result.exit, result.data, result.reason) == (2, None, reason)
    events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
    assert len(events) == 2
    for event in events:
        assert event['kind'] == 'adapter: none'
        assert event['payload'] == {
            'adapter': 'none', 'kind': kind, 'call': call,
            'exit': 2, 'reason': reason, 'performed': False,
        }
    assert 'private argument' not in (directory / 'events.jsonl').read_text()
    assert (directory / 'state.json').read_text() == 'unchanged'
    assert reason in capsys.readouterr().err


@pytest.mark.parametrize('failure', [OSError('disk unavailable'), ValueError('invalid clock')])
def test_none_event_failure(tmp_path, monkeypatch, capsys, failure):
    registry()
    from adapters.scanner import none
    from wuwei import state

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(state, 'append_event', fail)
    result = none.audit('secret path', root=tmp_path)
    assert result.exit == 2 and result.data is None
    assert str(failure) in result.reason
    assert result.reason in capsys.readouterr().err


def test_registry_loads_config_selection(tmp_path):
    api = registry()
    from wuwei.workspace import load_config

    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\nruntime = "none"\n')
    config = load_config(tmp_path)
    assert hasattr(api, 'known'), 'adapter discovery is missing'
    for kind in api.INTERFACES:
        assert 'none' in api.known(kind)
        assert api.load(kind, config) is importlib.import_module(f'adapters.{kind}.none')


@pytest.mark.parametrize('kind,name', [('missing', 'none'), ('../scanner', 'none'),
                                      ('scanner', '../none'), ('scanner', '_private'),
                                      ('scanner', 'missing'), ('scanner', 'none.audit')])
def test_registry_rejects_unknown_selection(kind, name):
    api = registry()
    assert hasattr(api, 'load'), 'adapter loading is missing'
    with pytest.raises(ValueError, match=kind.replace('../', '') if kind != 'scanner' else 'scanner'):
        api.load(kind, {'adapters': {kind: name}})


def test_runtime_default_is_explicitly_unavailable(tmp_path):
    api = registry()
    from wuwei.workspace import load_config

    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    assert hasattr(api, 'load'), 'adapter loading is missing'
    with pytest.raises(ValueError, match='runtime.*claude.*#26'):
        api.load('runtime', load_config(tmp_path))


def test_registry_discovers_new_modules(tmp_path, monkeypatch):
    api = registry()
    assert hasattr(api, 'known'), 'adapter discovery is missing'
    import adapters.scanner

    directory = tmp_path / 'scanner'
    directory.mkdir()
    (directory / 'fake.py').write_text('marker = "selected fake"\n')
    (directory / '_private.py').write_text('')
    (directory / 'bad-name.py').write_text('')
    (directory / 'readme.md').write_text('')
    monkeypatch.setattr(api, 'ADAPTERS', tmp_path)
    monkeypatch.setattr(adapters.scanner, '__path__', [str(directory)])
    assert api.known('scanner') == ['fake']
    try:
        assert api.load('scanner', {'adapters': {'scanner': 'fake'}}).marker == 'selected fake'
    finally:
        import sys
        sys.modules.pop('adapters.scanner.fake', None)


@pytest.mark.parametrize('shadow_cli', [False, True])
def test_shim_loads_adapter_outside_plugin(tmp_path, shadow_cli):
    import os
    import shutil
    import subprocess

    plugin = tmp_path / 'plugin with spaces'
    for name in ('bin', 'cli', 'adapters', '.claude-plugin'):
        shutil.copytree(ROOT / name, plugin / name)
    (plugin / 'cli/wuwei/commands/scan_probe.py').write_text('''
from wuwei import registry

def register(subparsers):
    parser = subparsers.add_parser('scan-probe')
    parser.set_defaults(func=run)

def run(args):
    scanner = registry.load('scanner', {'adapters': {'scanner': 'none'}})
    return scanner.audit('private path').exit
''')
    (tmp_path / '.wuwei').mkdir()
    if shadow_cli:
        shadow = tmp_path / 'wuwei'
        shadow.mkdir()
        (shadow / '__init__.py').write_text('')
        (shadow / '__main__.py').write_text('print("SHADOWED")\n')
    result = subprocess.run([str(plugin / 'bin/wuwei'), 'scan-probe'], cwd=tmp_path,
                            env={**os.environ, 'PYTHONPATH': '/unused',
                                 'WUWEI_WORKSPACE': str(tmp_path),
                                 'WUWEI_NOW': '2026-09-28T12:00:00Z'},
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'unmeasured' in result.stderr
    assert (tmp_path / '.wuwei/days/2026-09-28/events.jsonl').is_file()


@pytest.mark.parametrize('regular_package', [False, True])
def test_registry_ignores_workspace_adapter(tmp_path, regular_package):
    import os
    import subprocess
    import sys

    directory = tmp_path / 'adapters/scanner'
    directory.mkdir(parents=True)
    if regular_package:
        (directory.parent / '__init__.py').write_text('')
        (directory / '__init__.py').write_text('')
    (directory / 'none.py').write_text('raise RuntimeError("workspace adapter executed")\n')
    result = subprocess.run(
        [sys.executable, '-S', '-c', '''
from pathlib import Path
from wuwei import registry
module = registry.load('scanner', {'adapters': {'scanner': 'none'}})
assert Path(module.__file__) == registry.ADAPTERS / 'scanner/none.py'
'''], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT / 'cli'), str(ROOT)])},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
