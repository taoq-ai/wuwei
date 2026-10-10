"""Plain-module adapter contracts and honest unavailable results."""

import importlib
import inspect
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CALLS = [
    ('editor', 'edit', ('path', 'command'), False),
    ('tts', 'speak', ('text', 'rate', 'out'), False),
    ('calendar', 'events', ('since', 'until'), True),
    ('transcripts', 'recent', ('since',), True),
    ('inbound', 'poll', ('since',), True),
    ('redactor', 'redact', ('text',), True),
    ('integrity', 'sign', ('manifest', 'key'), False),
    ('integrity', 'verify', ('manifest', 'signature', 'key'), True),
    ('host', 'free_memory', (), True),
    ('checks', 'run', ('path', 'command'), True),
    ('code_host', 'auth_status', (), True),
    ('code_host', 'viewer_login', (), True),
    ('code_host', 'pr', ('ref',), True),
    ('code_host', 'checks', ('ref', 'sha'), True),
    ('code_host', 'reviews', ('ref',), True),
    ('code_host', 'commits', ('ref',), True),
    ('code_host', 'threads', ('ref',), True),
    ('code_host', 'protection', ('repo', 'branch'), True),
    ('code_host', 'files', ('ref',), True),
    ('code_host', 'history', ('repo', 'start', 'branch', 'patches'), True),
    ('code_host', 'author_login', ('repo', 'email'), True),
    ('code_host', 'token_scopes', ('variable',), True),
    ('code_host', 'create_pr', ('draft',), False),
    ('code_host', 'request_reviewers', ('ref', 'logins'), False),
    ('code_host', 'comment', ('ref', 'text', 'thread'), False),
    ('code_host', 'merge', ('ref', 'sha'), False),
    ('code_host', 'revert_pr', ('ref',), False),
    ('code_host', 'merged_prs', ('repo',), True),
    ('code_host', 'open_prs', ('repo',), True),
    ('code_host', 'probe', ('ref', 'tags'), True),
    ('code_host', 'default_branch', ('repo',), True),
    ('code_host', 'deployments', ('repo', 'since'), True),
    ('code_host', 'issue', ('repo', 'title', 'body'), False),
    ('code_host', 'label', ('ref', 'name', 'present'), False),
    ('vcs', 'workspace_init', ('repo',), False),
    ('vcs', 'workspace_changes', ('repo',), True),
    ('vcs', 'workspace_commit', ('repo', 'paths'), False),
    ('vcs', 'workspace_owner_commit', ('repo', 'paths'), False),
    ('vcs', 'resolve', ('repo', 'sha'), True),
    ('vcs', 'identity', ('repo',), True),
    ('vcs', 'remote_url', ('repo',), True),
    ('vcs', 'head', ('repo',), True),
    ('vcs', 'merge_base', ('repo', 'ref'), True),
    ('vcs', 'fetch', ('repo', 'remote', 'branch', 'expected'), False),
    ('vcs', 'rebase', ('repo', 'ref'), False),
    ('vcs', 'push', ('repo', 'remote', 'branch', 'expected'), False),
    ('vcs', 'status', ('repo',), True),
    ('vcs', 'diff_stat', ('repo', 'base', 'head'), True),
    ('vcs', 'log_since', ('repo', 'sha'), True),
    ('vcs', 'worktree_add', ('repo', 'branch', 'path'), False),
    ('vcs', 'changes_on', ('repo', 'day'), True),
    ('vcs', 'read_tree', ('repo', 'ref', 'paths'), True),
    ('vcs', 'branches', ('repo', 'pattern'), True),
    ('vcs', 'pushed_branches', ('repo',), True),
    ('vcs', 'authorship', ('repo', 'branch', 'paths', 'days'), True),
    ('vcs', 'branch', ('repo',), True),
    ('vcs', 'repo_context', ('repo',), True),
    ('vcs', 'commit_context', ('repo', 'settings', 'env'), True),
    ('vcs', 'push_context', ('repo', 'remote', 'refspecs'), True),
    ('vcs', 'hooks_path', ('repo', 'path', 'mode'), False),
    ('vcs', 'hooks_target', ('repo',), True),
    ('vcs', 'worktree_identity', ('repo', 'name', 'email'), False),
    ('vcs', 'push_commits', ('repo', 'remote', 'destination', 'local_sha', 'remote_sha', 'default_branch'), True),
    ('vcs', 'recent_commits', ('repo',), True),
    ('vcs', 'default_branch', ('repo',), True),
    ('vcs', 'worktrees', ('repo',), True),
    ('vcs', 'worktree_checkout', ('repo', 'branch', 'path'), False),
    ('vcs', 'rehearse_revert', ('path',), False),
    ('tracker', 'backlog', ('filter',), True),
    ('tracker', 'claim', ('item',), False),
    ('tracker', 'transition', ('item', 'state'), False),
    ('tracker', 'create', ('draft',), False),
    ('tracker', 'history', ('item',), True),
    ('tracker', 'created', ('item',), True),
    ('tracker', 'comment', ('item', 'text', 'category'), False),
    ('chat', 'post', ('channel', 'text', 'thread'), False),
    ('chat', 'dm', ('text',), False),
    ('chat', 'sent', ('channel', 'owner'), True),
    ('review_bot', 'score', ('pr',), True),
    ('review_bot', 'open_findings', ('pr',), True),
    ('runtime', 'dispatch', ('role', 'brief_path', 'worktree', 'write'), False),
    ('runtime', 'status', ('job',), True),
    ('runtime', 'result', ('job',), True),
    ('runtime', 'continue_job', ('job', 'feedback'), False),
    ('scanner', 'audit', ('path',), True),
    ('scanner', 'gate', ('result', 'threshold'), True),
    ('scanner', 'traces', ('file',), True),
    ('scanner', 'mcp', ('servers',), True),
    ('docs', 'read', ('ref',), True),
    ('docs', 'write', ('draft',), False),
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
    assert api.PARAMETERS == {
        kind: {call: params for group, call, params, _ in CALLS if group == kind}
        for kind in api.INTERFACES
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
    none = importlib.import_module('adapters.tracker.none')

    monkeypatch.setattr(none, 'claim', operation)
    with pytest.raises(AssertionError):
        test_module_contracts()


def test_module_contracts_allow_extra_import(monkeypatch):
    none = importlib.import_module('adapters.tracker.none')

    monkeypatch.setattr(none, 'Result', registry().Result, raising=False)
    test_module_contracts()


@pytest.mark.parametrize('kind,call,parameters,measurement', [c for c in CALLS if c[0] not in ('editor', 'vcs', 'tts', 'calendar', 'transcripts', 'redactor')])
def test_none_call(tmp_path, monkeypatch, capsys, kind, call, parameters, measurement):
    api = registry()
    module = importlib.import_module(f'adapters.{kind}.none')
    operation = inspect.unwrap(getattr(module, call))
    assert tuple(inspect.signature(operation).parameters) == (*parameters, 'root')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    directory = tmp_path / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True)
    (directory / 'state.json').write_text('unchanged')
    reason = ('tracker adapter is none' if kind == 'tracker' else
              'unmeasured' if measurement else 'no adapter configured')
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
    none = importlib.import_module('adapters.scanner.none')
    from wuwei import state

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(state, 'append_event', fail)
    result = none.audit('secret path', root=tmp_path)
    assert result.exit == 2 and result.data is None
    assert str(failure) in result.reason
    assert result.reason in capsys.readouterr().err


def test_none_port_without_workspace_creates_nothing(tmp_path):
    none = importlib.import_module('adapters.scanner.none')
    result = none.audit('probe', root=tmp_path)
    assert result.exit == 2
    assert 'could not record adapter event' in result.reason
    assert list(tmp_path.iterdir()) == []


def test_registry_loads_config_selection(tmp_path):
    api = registry()
    from wuwei.workspace import load_config

    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\nruntime = "none"\n')
    config = load_config(tmp_path)
    assert hasattr(api, 'known'), 'adapter discovery is missing'
    for kind in api.INTERFACES:
        if kind in ('integrity', 'editor'):
            continue  # Fixed host mechanisms, not owner-selectable config.
        expected = {'code_host': 'github', 'vcs': 'git', 'host': 'local',
                    'checks': 'local', 'redactor': 'builtin',
                    'tts': 'say' if sys.platform == 'darwin' else 'none'}.get(kind, 'none')
        assert expected in api.known(kind)
        assert config['adapters'][kind] == expected
        assert api.load(kind, config) is importlib.import_module(f'adapters.{kind}.{expected}')


@pytest.mark.parametrize('kind,name', [('missing', 'none'), ('../scanner', 'none'),
                                      ('scanner', '../none'), ('scanner', '_private'),
                                      ('scanner', 'missing'), ('scanner', 'none.audit')])
def test_registry_rejects_unknown_selection(kind, name):
    api = registry()
    assert hasattr(api, 'load'), 'adapter loading is missing'
    with pytest.raises(ValueError, match=kind.replace('../', '') if kind != 'scanner' else 'scanner'):
        api.load(kind, {'adapters': {kind: name}})


def test_runtime_default_is_available(tmp_path):
    api = registry()
    from wuwei.workspace import load_config

    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    assert hasattr(api, 'load'), 'adapter loading is missing'
    assert api.load('runtime', load_config(tmp_path)).__name__ == 'adapters.runtime.claude'


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


@pytest.mark.parametrize('kind', ['code_host', 'vcs'])
def test_recording_fake(kind, monkeypatch, tmp_path):
    from copy import deepcopy
    import subprocess
    from fakes.replay import recordings

    def forbidden(*args, **kwargs):
        pytest.fail('fake spawned a tool')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    fake_type = importlib.import_module(f'fakes.{kind}').Fake
    first = recordings(kind)[0]
    assert getattr(fake_type(), first['operation'])(*first['args']).data == first['data']
    for case in recordings(kind):
        fake = fake_type({case['operation']: registry().Result(0, case['data'])})
        operation = getattr(fake, case['operation'])
        assert tuple(inspect.signature(operation).parameters) == (
            *registry().PARAMETERS[kind][case['operation']], 'root')
        result = operation(*case['args'], root=tmp_path)
        expected = deepcopy(case['data'])
        assert result.exit == 0 and result.data == expected
        result.data.clear()
        assert operation(*case['args'], root=tmp_path).data == expected
        assert fake.calls == [(case['operation'], tuple(case['args']), tmp_path)] * 2
    empty = fake_type({})
    case = recordings(kind)[0]
    result = getattr(empty, case['operation'])(*case['args'])
    assert result.exit == 2 and result.data is None
    failed = fake_type({case['operation']: registry().Result(2, None, 'offline')})
    assert getattr(failed, case['operation'])(*case['args']).reason == 'offline'


def _process_access(source):
    """Core modules cannot import process launchers or reference launch APIs."""
    import ast

    # ponytail: static imports/references only; importlib, __import__, getattr and
    # sys.modules can evade this scan. Use runtime isolation for hostile code.
    tree = ast.parse(source)
    module_names = {'os': 'os', 'asyncio': 'asyncio'}
    violations = []

    def forbidden(name):
        return (name.split('.')[0] in ('subprocess', 'pty') or
                name == 'asyncio.subprocess' or name.startswith('asyncio.subprocess.') or
                name in ('asyncio.create_subprocess_exec', 'asyncio.create_subprocess_shell',
                         'os.*', 'asyncio.*') or
                name in ('os.system', 'os.popen') or
                name.startswith(('os.exec', 'os.spawn', 'os.posix_spawn')))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ('os', 'asyncio'):
                    module_names[alias.asname or alias.name] = alias.name
                if forbidden(alias.name):
                    violations.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if forbidden(node.module or '') or any(
                    forbidden(f'{node.module}.{alias.name}') for alias in node.names):
                violations.append(node.lineno)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and
                node.value.id in module_names and
                forbidden(f'{module_names[node.value.id]}.{node.attr}')):
            violations.append(node.lineno)
    return violations


@pytest.mark.parametrize('source', [
    "import subprocess\nsubprocess.run(['git', 'status'])",
    "import subprocess as sp\nsp.Popen(args=['gh', 'api'])",
    "from subprocess import check_output as run\nargv = ['git', '-C', '/repo']\nrun(argv)",
    "import subprocess\nsubprocess.run('gh pr view 7', shell=True)",
    "import subprocess\nsubprocess.call(['anything'], executable='/usr/bin/git')",
    "import os\nos.system('git status')",
    "import subprocess\nsubprocess.run(['env', 'git', 'status'])",
    "import subprocess\nsubprocess.run(['sh', '-c', 'git status'])",
    "import subprocess\nargv = make_args()\nsubprocess.run(argv)",
    "import subprocess, shutil\nsubprocess.run([shutil.which('git'), 'status'])",
    "import subprocess\ndef run(tool): subprocess.run([tool, 'status'])",
    "import asyncio.subprocess\nasyncio.subprocess.create_subprocess_exec('git', 'status')",
    "import os\nos.execvp('git', ['git', 'status'])",
    "import pty",
    "from asyncio import subprocess as sp",
    "from os import popen as spawn",
    "import os as operating\noperating.posix_spawn('git', [], {})",
    "import asyncio\nasyncio.create_subprocess_exec('git', 'status')",
    "import asyncio as aio\naio.create_subprocess_shell('git status')",
    "from asyncio import create_subprocess_exec as spawn",
    "from asyncio import create_subprocess_shell as spawn",
    "from os import *\nsystem('git status')",
    "from subprocess import *\nrun(['git', 'status'])",
    "from asyncio import *\ncreate_subprocess_exec('git', 'status')",
])
def test_core_boundary_scan_detects_tool_spawn(source):
    assert _process_access(source)


def test_core_does_not_access_process_launchers():
    for path in (ROOT / 'cli/wuwei').rglob('*.py'):
        assert not _process_access(path.read_text()), path


def test_workspace_template_selects_new_ports():
    import tomllib
    config = tomllib.loads((ROOT / 'templates/workspace/config.toml').read_text())
    assert config['adapters']['code_host'] == 'github'
    assert config['adapters']['vcs'] == 'git'


@pytest.mark.parametrize('tool,port', [('gh', 'code_host'), ('git', 'vcs')])
def test_fixture_replay_never_spawns(tool, port, tmp_path, monkeypatch):
    import subprocess
    from fakes.replay import install_replay, recordings

    def forbidden(*args, **kwargs):
        pytest.fail('fixture replay spawned a process')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    case = recordings(port)[0]
    install_replay(monkeypatch, tool, case['steps'])
    module = importlib.import_module(f'adapters.{port}.{"github" if tool == "gh" else "git"}')
    result = getattr(module, case['operation'])(*case['args'])
    assert result.exit == 0 and result.data == case['data']


def test_watch_probe_refuses_unlisted_commands(tmp_path, monkeypatch):
    import subprocess
    from wuwei.registry import watch_service
    module = watch_service()
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('started a process'))
    with pytest.raises(ValueError, match='unsupported probe command'):
        module.probe([(('hook', 'PreToolUse'), '{}'), (('state', 'set'), '')], tmp_path)


def test_watch_probe_runs_calls_together_and_times_out(tmp_path):
    import time
    from wuwei.registry import watch_service
    module = watch_service()
    script = tmp_path / 'wuwei'
    script.write_text('#!/bin/sh\ncat > /dev/null\n[ "$1" = status ] && exec sleep 5\n'
                      'echo "first line" >&2\necho second >&2\nexit 3\n')
    script.chmod(0o755)
    module.LAUNCHER = script
    ran = []
    start = time.monotonic()
    results, during = module.probe([(('status', '--line'), ''), (('hook', 'PreToolUse'), '{}')],
                                   tmp_path, during=lambda: ran.append(1) or 'measured', timeout=1)
    assert time.monotonic() - start < 3
    assert ran == [1] and during == 'measured'
    (timed, reason, _), (code, line, ms) = results
    assert (timed, reason) == (None, 'timeout')
    assert (code, line) == (3, 'first line') and ms >= 0


def test_watch_ping_requires_https(monkeypatch):
    import urllib.request
    from wuwei.registry import watch_service
    module = watch_service()
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k: pytest.fail('opened a connection'))
    with pytest.raises(ValueError, match='ping URL must be https'):
        module.ping('http://example.test/x')


def test_watch_post_sends_json_over_https_and_returns_the_status(monkeypatch):
    # #422: telemetry posts; a 409 comes back as a status, never an exception.
    import io
    import urllib.error
    import urllib.request
    from wuwei.registry import watch_service
    module, sent = watch_service(), []

    class Response(io.BytesIO):
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        sent.append((request.full_url, request.get_method(), request.data, dict(request.header_items()), timeout))
        if len(sent) == 2:
            raise urllib.error.HTTPError(request.full_url, 409, 'Conflict', {}, io.BytesIO(b''))
        return Response(b'ok')
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', lambda self, request, data=None, timeout=None: urlopen(request, timeout))
    assert module.post('https://example.test/v1', {'a': 1}, {'Authorization': 'x'}) == 202
    assert module.post('https://example.test/v1', {'a': 1}) == 409
    url, method, data, headers, timeout = sent[0]
    assert (url, method, json.loads(data), timeout) == ('https://example.test/v1', 'POST', {'a': 1}, 5)
    assert headers['Content-type'] == 'application/json' and headers['Authorization'] == 'x'
    with pytest.raises(ValueError, match='https'):
        module.post('http://example.test/v1', {})
    assert len(sent) == 2


def test_watch_post_does_not_follow_a_redirect(monkeypatch):
    # A 302 must not carry the Authorization header to the Location host.
    import email.message
    import io
    import urllib.request
    import urllib.response
    from wuwei.registry import watch_service
    headers = email.message.Message()
    headers['Location'] = 'http://other.test/'

    def https_open(self, request):
        response = urllib.response.addinfourl(io.BytesIO(b''), headers, request.full_url, 302)
        response.msg = 'Found'
        return response
    monkeypatch.setattr(urllib.request.HTTPSHandler, 'https_open', https_open)
    monkeypatch.setattr(urllib.request.HTTPHandler, 'http_open', lambda self, request: pytest.fail('followed'))
    assert watch_service().post('https://example.test/v1', {}, {'Authorization': 'x'}) == 302
