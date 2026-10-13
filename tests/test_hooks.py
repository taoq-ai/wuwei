"""Hook tables run in-process; fixture replays exercise the executable shim."""

import io
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = sorted((ROOT / 'tests/payloads').glob('*/*.json'))
EVENTS = ('PreToolUse', 'PostToolUse', 'SubagentStop', 'SessionStart', 'Stop')


@pytest.fixture
def subprocess_plugin(tmp_path):
    root = tmp_path / "plugin's $literal `path`"
    root.mkdir()
    for directory in ('cli', 'bin', '.claude-plugin', 'adapters'):
        shutil.copytree(ROOT / directory, root / directory)
    path = tmp_path / 'path'
    path.mkdir()
    (path / 'python3').symlink_to(sys.executable)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    return root, {**os.environ, 'PATH': str(path) + os.pathsep + os.environ['PATH'],
                  'PYTHONPATH': '/unused/inherited/path', 'WUWEI_WORKSPACE': str(tmp_path)}


def subprocess_replay(plugin, event, payload):
    root, env = plugin
    config = json.loads((ROOT / 'hooks/hooks.json').read_text())
    entry, = config['hooks'][event]
    hook, = entry['hooks']
    command = hook['command'].replace('${CLAUDE_PLUGIN_ROOT}', str(root))
    return subprocess.run([command, *hook['args']], input=payload, text=True,
                          capture_output=True, cwd=root.parent, env=env)


@pytest.fixture
def plugin(tmp_path, monkeypatch, capsys):
    import wuwei.guards
    from wuwei import workspace
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: tmp_path)
    path = tmp_path / 'cli/wuwei/guards'
    path.mkdir(parents=True)
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setattr(wuwei.guards, '__path__', [str(path)])
    yield tmp_path, monkeypatch, capsys
    forget_guards()  # the package attributes too, or a later import gets a stale guard module


def replay(plugin, event, payload):
    from wuwei.commands.hook import run
    _, monkeypatch, capsys = plugin
    monkeypatch.setattr(sys, 'stdin', io.StringIO(payload))
    code = run(SimpleNamespace(event=event))
    out = capsys.readouterr()
    return SimpleNamespace(returncode=code, stdout=out.out, stderr=out.err)


def fixture(event):
    return json.loads(next(p for p in PAYLOADS if p.parent.name == event).read_text())


def install(plugin, source, name='fake'):
    path = plugin[0] / 'cli/wuwei/guards'
    path.mkdir(exist_ok=True)
    (path / (name + '.py')).write_text(source)


def test_hook_configuration():
    path = ROOT / 'hooks/hooks.json'
    assert path.exists(), 'four hook mappings must exist'
    config = json.loads(path.read_text())
    assert set(config['hooks']) == set(EVENTS)
    for event, entries in config['hooks'].items():
        entry, = entries
        hook, = entry['hooks']
        assert hook == {'type': 'command', 'command': '${CLAUDE_PLUGIN_ROOT}/bin/wuwei',
                        'args': ['hook', event]}
        assert entry.get('matcher', '') in ('', '*')


@pytest.mark.parametrize('payload_path', PAYLOADS, ids=lambda p: str(p.relative_to(ROOT / 'tests/payloads')))
def test_clean_replay(subprocess_plugin, payload_path):
    result = subprocess_replay(subprocess_plugin, payload_path.parent.name, payload_path.read_text())
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ''


@pytest.mark.parametrize('inside', [True, False], ids=['workspace', 'outside'])
@pytest.mark.parametrize('command', [
    '/bin/ls -la', '/bin/echo hi', '/usr/bin/python3 -m pytest -q',
    'python3 -m pytest -q', 'for i in 1; do echo ok; done', 'export X=1',
])
def test_harmless_commands_through_shim(subprocess_plugin, tmp_path, inside, command):
    root, env = subprocess_plugin
    if inside:
        from fakes.integrity import seed
        seed(tmp_path)
    else:
        shutil.rmtree(tmp_path / '.wuwei')
        env.pop('WUWEI_WORKSPACE')
    payload = fixture('PreToolUse')
    payload.update(cwd=str(tmp_path), tool_name='Bash', tool_input={'command': command})
    result = subprocess_replay((root, env), 'PreToolUse', json.dumps(payload))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('payload_path', PAYLOADS, ids=lambda p: str(p.relative_to(ROOT / 'tests/payloads')))
def test_payloads_use_neutral_paths(payload_path):
    payload = json.loads(payload_path.read_text())
    assert payload['cwd'] == '/workspace/project'
    assert payload['transcript_path'] == '/workspace/.claude/projects/example/session.jsonl'
    if 'agent_transcript_path' in payload:
        assert payload['agent_transcript_path'] == '/workspace/.claude/projects/example/subagents/agent-def456.jsonl'


def test_scratchpad_fixtures_use_neutral_paths():
    for path in PAYLOADS:
        payload = json.loads(path.read_text())
        if 'scratchpad_dir' in payload:
            assert payload['scratchpad_dir'] == '/tmp/scratch/example', path


def test_discovery_returns_plain_list():
    from wuwei.guards import discover
    from wuwei.guards.outward import GUARDS
    assert type(discover()) is list
    assert all(guard in discover() for guard in GUARDS)
    assert any(g.event == 'PostToolUse' and g.matcher is None
               and g.check.__module__ == 'wuwei.guards.traces' for g in discover())
    assert any(guard.event == 'PreToolUse' and guard.matcher == 'Agent' for guard in discover())
    assert any(record.event == 'PreToolUse' and record.matcher == 'Bash'
               and record.check.__module__ == 'wuwei.guards.edges' for record in discover())


def test_import_map_matches_guard_tables():
    from importlib import import_module
    import pkgutil
    import wuwei.guards
    derived = {}
    for module in pkgutil.iter_modules(wuwei.guards.__path__, 'wuwei.guards.'):
        name = module.name.rsplit('.', 1)[-1]
        if name.startswith('_'):
            continue
        events = {}
        for guard in import_module(module.name).GUARDS:
            events.setdefault(guard.event, []).append(guard.matcher)
        derived[name] = {event: None if None in matchers else '|'.join(dict.fromkeys(matchers))
                         for event, matchers in events.items()}
    assert wuwei.guards.MODULES == derived


@pytest.mark.parametrize('event', EVENTS)
@pytest.mark.parametrize('tool', ['', 'Bash', 'Write', 'Edit', 'Agent', 'AskUserQuestion',
                                  'mcp__example__operation', 5])
def test_selected_guards_match_full_discovery(event, tool):
    from wuwei.guards import SELECTION, discover

    def runnable(guards):
        return [g for g in guards if g.event == event and (
            not isinstance(tool, str) or g.matcher is None or re.fullmatch(g.matcher, tool))]

    token = SELECTION.set((event, tool))
    try:
        selected = discover()
    finally:
        SELECTION.reset(token)
    assert runnable(selected) == runnable(discover())


@pytest.mark.parametrize('event, name, unloaded', [
    ('SubagentStop', 'example', {'edges', 'protect_state'}),
    ('PostToolUse', 'example', {'edges', 'protect_state'}),
])
def test_hook_imports_only_needed_guards(tmp_path, event, name, unloaded):
    # A fresh interpreter: loaded modules are process state and other tests import every guard.
    from fakes.integrity import seed
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    seed(tmp_path)
    payload = {**json.loads((ROOT / f'tests/payloads/{event}/{name}.json').read_text()),
               'cwd': str(tmp_path)}
    if event == 'SubagentStop':
        payload['stop_hook_active'] = False
    out = tmp_path / 'modules.json'
    script = ('import json, sys\nsys.path.insert(0, sys.argv[1])\n'
              'from wuwei.__main__ import main\ncode = main(["hook", sys.argv[2]])\n'
              'names = [n.rsplit(".", 1)[-1] for n in sys.modules if n.startswith("wuwei.guards.")]\n'
              'open(sys.argv[3], "w").write(json.dumps(sorted(names)))\nsys.exit(code)\n')
    result = subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), event, str(out)],
                            input=json.dumps(payload), text=True, capture_output=True, cwd=tmp_path,
                            env={**os.environ, 'WUWEI_WORKSPACE': str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert unloaded & set(json.loads(out.read_text())) == set()


def test_subagent_stop_skips_lifecycle_watch_and_memory(tmp_path):
    # #847: SubagentStop records no session; the lifecycle, watch and memory modules (and their
    # imports) are SessionStart's. lifecycle keeps watch's error tuple itself.
    from wuwei import watch
    from wuwei.guards import lifecycle
    from fakes.integrity import seed
    assert lifecycle.ERRORS == watch.ERRORS
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    seed(tmp_path)
    today = tmp_path / '.wuwei/days/2026-09-28'
    today.mkdir(parents=True)
    (today / 'state.json').write_text('{"items": {}, "cap": 1}\n')
    payload = {**fixture('SubagentStop'), 'cwd': str(tmp_path)}
    out = tmp_path / 'modules.json'
    script = ('import json, sys\nsys.path[:0] = sys.argv[1:3]\n'
              'from wuwei.__main__ import main\ncode = main(["hook", "SubagentStop"])\n'
              'open(sys.argv[3], "w").write(json.dumps(sorted(sys.modules)))\nsys.exit(code)\n')
    result = subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), str(ROOT), str(out)],
                            input=json.dumps(payload), text=True, capture_output=True, cwd=tmp_path,
                            env={**os.environ, 'WUWEI_WORKSPACE': str(tmp_path), 'WUWEI_NOW': DAY + 'T12:00:00+00:00'})
    assert result.returncode == 0, result.stderr
    assert 'sessions' not in json.loads((today / 'state.json').read_text())
    assert {'wuwei.guards.lifecycle', 'wuwei.watch', 'wuwei.memory', 'tempfile'} & set(
        json.loads(out.read_text())) == set()


@pytest.mark.parametrize('event, name, target, loaded', [
    ('PreToolUse', 'bash', None, False), ('PreToolUse', 'write', 'notes.md', False),
    ('PostToolUse', 'example', None, False), ('PreToolUse', 'write', 'repo/src/app.py', False),
    ('PostToolUse', 'example', 'repo/src/app.py', True)])
def test_spec_helper_loads_only_in_item_worktrees(tmp_path, event, name, target, loaded):
    # #346: the spec recorder reads state and returns before importing wuwei.specmode unless
    # the path lies in an item's recorded worktree; #843: PreToolUse never loads it.
    from fakes.integrity import seed
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[spec]\nmode = "advisory"\n')
    seed(tmp_path)
    day = tmp_path / '.wuwei/days/2026-10-03'
    day.mkdir(parents=True)
    (day / 'state.json').write_text(json.dumps({'items': {'A': {
        'phase': 'implement', 'status': 'running', 'worktree': str(tmp_path / 'repo')}}}))
    (tmp_path / 'repo/src').mkdir(parents=True)
    payload = {**json.loads((ROOT / f'tests/payloads/{event}/{name}.json').read_text()), 'cwd': str(tmp_path)}
    if target:
        payload['tool_input'] = {'file_path': str(tmp_path / target), 'content': 'x'}
    if event == 'PostToolUse' and not target:
        payload.update(tool_name='Bash', tool_input={'command': 'true'})
    out = tmp_path / 'modules.json'
    script = ('import json, sys\nsys.path.insert(0, sys.argv[1])\n'
              'from wuwei.__main__ import main\ncode = main(["hook", sys.argv[2]])\n'
              'open(sys.argv[3], "w").write(json.dumps(sorted(sys.modules)))\nsys.exit(code)\n')
    result = subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), event, str(out)],
                            input=json.dumps(payload), text=True, capture_output=True, cwd=tmp_path,
                            env={**os.environ, 'WUWEI_WORKSPACE': str(tmp_path),
                                 'WUWEI_NOW': '2026-10-03T12:00:00+00:00'})
    assert result.returncode == 0, result.stderr
    assert ('wuwei.specmode' in json.loads(out.read_text())) is loaded

DENY = {'tomllib', 'hashlib', 'argparse', 'dataclasses', 'inspect', 'typing', 'datetime', 'subprocess'}


INSIDE_DENY = {'argparse', 'dataclasses', 'subprocess', 'inspect', 'hashlib',
               'glob', 'copy', 'weakref', 'wuwei.telemetry', 'secrets',
               'wuwei.merge'}


@pytest.mark.parametrize('inside, deny, tool', [
    (False, DENY | {'copy', 'wuwei.telemetry', 'secrets'}, None),
    (True, INSIDE_DENY, None),
    # #469: a noun-first MCP read passes without widening the hook's import graph.
    (True, INSIDE_DENY | {'wuwei.watch'}, 'mcp__slack__conversations_history')],
    ids=['outside', 'workspace', 'mcp-read'])
def test_hook_imports_no_unused_stdlib(tmp_path, inside, deny, tool):
    # A fresh interpreter: a hook pays only for the stdlib modules its path uses.
    cwd = tmp_path / 'project'
    cwd.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('WUWEI_', 'GIT_'))}
    if inside:
        from fakes.integrity import seed
        cwd = tmp_path
        (tmp_path / '.wuwei').mkdir()
        (tmp_path / '.wuwei/config.toml').write_text('')
        seed(tmp_path)
        env['WUWEI_WORKSPACE'] = str(tmp_path)
    payload = {**json.loads((ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()), 'cwd': str(cwd)}
    if tool:
        payload.update(tool_name=tool, tool_input={'channel': 'C1'})
    out = tmp_path / 'modules.json'
    # bin/wuwei's own launcher line, with sys.modules dumped at exit.
    script = ('import atexit, json, runpy, sys; out = sys.argv.pop(3); '
              'atexit.register(lambda: open(out, "w").write(json.dumps(sorted(sys.modules)))); '
              'sys.path[:0] = sys.argv[1:3]; del sys.argv[1:3]; '
              'runpy.run_module("wuwei", run_name="__main__", alter_sys=True)')
    result = subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), str(ROOT), str(out),
                             'hook', 'PreToolUse'],
                            input=json.dumps(payload), text=True, capture_output=True, cwd=cwd, env=env)
    assert result.returncode == 0, result.stderr
    if not inside:
        assert result.stdout == ''
    assert deny & set(json.loads(out.read_text())) == set()


LAUNCHER_MODULES = ('import atexit, json, runpy, sys; out = sys.argv.pop(3); '
                    'atexit.register(lambda: open(out, "w").write(json.dumps(sorted(sys.modules)))); '
                    'sys.path[:0] = sys.argv[1:3]; del sys.argv[1:3]; '
                    'runpy.run_module("wuwei", run_name="__main__", alter_sys=True)')


@pytest.mark.parametrize('shape', ['template', 'empty'])
@pytest.mark.parametrize('args', [('hook', 'PreToolUse'), ('hook', 'PostToolUse'),
                                  ('status', '--line')], ids=' '.join)
def test_warm_config_cache_skips_tomllib(tmp_path, args, shape):
    # #346: with the parsed copy of config.toml current, no hook or status line parses TOML,
    # in a templated workspace with security material and in the latency script's blank one.
    from fakes.integrity import seed
    from wuwei import security
    (tmp_path / '.wuwei').mkdir()
    if shape == 'template':
        (tmp_path / '.wuwei/config.toml').write_text((ROOT / 'templates/workspace/config.toml').read_text())
        security.initialize(tmp_path / '.wuwei')
    else:
        (tmp_path / '.wuwei/config.toml').write_text('')
    seed(tmp_path)
    env = {**{k: v for k, v in os.environ.items() if not k.startswith(('WUWEI_', 'GIT_'))},
           'WUWEI_WORKSPACE': str(tmp_path), 'HOME': str(tmp_path / 'home'), 'XDG_CONFIG_HOME': str(tmp_path / 'xdg')}
    event = args[1] if args[0] == 'hook' else None
    name = {'PreToolUse': 'bash', 'PostToolUse': 'example'}.get(event)
    source = (ROOT / f'tests/payloads/{event}/{name}.json') if name else next(
        (p for p in PAYLOADS if p.parent.name == event), None)
    payload = json.dumps({**json.loads(source.read_text()), 'cwd': str(tmp_path)}) if source else ''
    out = tmp_path / 'modules.json'
    loaded = []
    for _ in range(2):  # The first run parses and writes the cache; the second reads it.
        result = subprocess.run([sys.executable, '-I', '-P', '-S', '-c', LAUNCHER_MODULES, str(ROOT / 'cli'),
                                 str(ROOT), str(out), *args],
                                input=payload, text=True, capture_output=True, cwd=tmp_path, env=env)
        assert result.returncode == 0, result.stderr
        loaded.append(set(json.loads(out.read_text())))
    assert 'tomllib' in loaded[0] and (tmp_path / '.wuwei/generated/config.cache.json').is_file()
    assert {'tomllib', 'typing', 'string'} & loaded[1] == set()


def test_status_line_skips_parser_and_hashlib(tmp_path):
    # Claude Code runs the status line on every refresh: no argparse (gettext, shutil), no
    # decision ledger without routes and, with no unit file installed, no hashlib.
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    env = {**{k: v for k, v in os.environ.items() if not k.startswith(('WUWEI_', 'GIT_'))},
           'WUWEI_WORKSPACE': str(tmp_path), 'HOME': str(tmp_path / 'home'), 'XDG_CONFIG_HOME': str(tmp_path / 'xdg')}
    out = tmp_path / 'modules.json'
    script = ('import atexit, json, runpy, sys; out = sys.argv.pop(3); '
              'atexit.register(lambda: open(out, "w").write(json.dumps(sorted(sys.modules)))); '
              'sys.path[:0] = sys.argv[1:3]; del sys.argv[1:3]; '
              'runpy.run_module("wuwei", run_name="__main__", alter_sys=True)')
    result = subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), str(ROOT), str(out),
                             'status', '--line'], text=True, capture_output=True, cwd=tmp_path, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'WUWEI no plan yet | pages 0\n'
    assert {'argparse', 'hashlib', 'shutil', 'wuwei.decision', 'copy', 'weakref',
            'wuwei.sessions', 'shlex'} & set(json.loads(out.read_text())) == set()


def test_integrity_import_leaves_registry_out():
    # #562: status --line asks integrity for the version and the restart line only.
    script = 'import sys; sys.path[:0] = sys.argv[1:3]; import wuwei.integrity; print("wuwei.registry" in sys.modules)'
    result = subprocess.run([sys.executable, '-I', '-c', script, str(ROOT / 'cli'), str(ROOT)],
                            text=True, capture_output=True)
    assert result.stdout == 'False\n', result.stderr


def test_together_runs_concurrently_and_raises_in_call_order():
    import threading
    from wuwei.registry import together
    barrier = threading.Barrier(3, timeout=2)
    # Each call returns only once all three wait together.
    assert together(*(lambda value=value: (barrier.wait(), value)[1] for value in 'abc')) == ['a', 'b', 'c']

    def fail(message):
        raise ValueError(message)
    with pytest.raises(ValueError, match='first'):
        together(lambda: 1, lambda: fail('first'), lambda: fail('second'))


def test_guard_modules_defer_heavy_imports():
    import ast
    for path in (ROOT / 'cli/wuwei/guards').glob('*.py'):
        roots = set()
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Import):
                roots.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                roots.add((node.module or '').split('.')[0])
        assert not roots & {'tomllib', 'datetime', 'subprocess', 'hashlib'}, path


def test_calibrate_is_off_every_hook_path(tmp_path):
    from fakes.integrity import seed
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    seed(tmp_path)
    calls = [(path.parent.name, {**json.loads(path.read_text()), 'cwd': str(tmp_path),
                                 'stop_hook_active': False}) for path in PAYLOADS]
    script = ('import io, json, sys\nsys.path.insert(0, sys.argv[1])\n'
              'from wuwei.__main__ import main\n'
              'for event, payload in json.loads(sys.argv[2]):\n'
              '    sys.stdin = io.StringIO(json.dumps(payload))\n    main(["hook", event])\n'
              'sys.exit(3 if {"wuwei.calibrate"} & set(sys.modules) else 0)\n')
    result = subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), json.dumps(calls)],
                            text=True, capture_output=True, cwd=tmp_path,
                            env={**os.environ, 'WUWEI_WORKSPACE': str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert 'calibrat' not in (ROOT / 'hooks/hooks.json').read_text()


def test_private_guard_module_is_ignored(plugin):
    install(plugin, 'raise RuntimeError("private helper imported")', '_helper')
    result = replay(plugin, 'SubagentStop', json.dumps(fixture('SubagentStop')))
    assert result.returncode == 0, result.stderr


def assert_refusal(result, event, reason, *, malformed=False):
    if event == 'Stop':
        assert result.returncode == 0 and result.stdout == ''
        assert result.stderr == reason + '\n'
        return
    if event == 'SessionStart':
        assert result.returncode == 0
        assert reason in json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
        assert result.stderr == reason + '\n'
        return
    assert result.returncode == 2
    assert result.stderr == reason + '\n'
    if event == 'PreToolUse':
        assert json.loads(result.stdout) == {'hookSpecificOutput': {
            'hookEventName': event, 'permissionDecision': 'deny',
            'permissionDecisionReason': reason}}
    elif event == 'SubagentStop':
        assert json.loads(result.stdout) == {'decision': 'block', 'reason': reason}
    else:
        assert result.stdout == ''


@pytest.mark.parametrize('payload_path', PAYLOADS, ids=lambda p: str(p.relative_to(ROOT / 'tests/payloads')))
@pytest.mark.parametrize('code', [0, 1, 2])
def test_guard_results(plugin, payload_path, code):
    event = payload_path.parent.name
    install(plugin, f'''
from wuwei.guards import Guard
GUARDS = [Guard({event!r}, None, lambda payload: ({code}, 'guard reason'))]
''')
    result = replay(plugin, event, payload_path.read_text())
    if event == 'SessionStart':
        assert result.returncode == 0
        assert json.loads(result.stdout)['hookSpecificOutput']['additionalContext'] == 'guard reason'
        assert result.stderr == ('guard reason\n' if code else '')
    elif code:
        assert_refusal(result, event, 'guard reason')
    else:
        assert result.returncode == 0, result.stderr
        assert result.stderr == ''
        expected = {'hookSpecificOutput': {'hookEventName': event,
                                          'additionalContext': 'guard reason'}}
        assert result.stdout == (json.dumps(expected) + '\n' if event == 'SessionStart' else '')


def test_matching_and_all_refusing_reasons(plugin):
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [
    Guard('SubagentStop', None, lambda p: (1, 'wrong event')),
    Guard('PreToolUse', 'Write|Edit', lambda p: (1, 'wrong tool')),
    Guard('PreToolUse', 'Ba', lambda p: (1, 'partial match')),
    Guard('PreToolUse', 'Bash|Agent', lambda p: (1, p['tool_input']['command'])),
    Guard('PreToolUse', None, lambda p: (0, 'clean message')),
]
''', 'first')
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [Guard('PreToolUse', None, lambda p: (2, 'second reason'))]
''', 'second')
    payload = json.loads((ROOT / 'tests/payloads/PreToolUse/bash.json').read_text())
    result = replay(plugin, 'PreToolUse', json.dumps(payload))
    assert_refusal(result, 'PreToolUse', 'npm test')  # #362: the finding, not the could-not-run


@pytest.mark.parametrize('active', [False, True])
def test_subagent_stop_active_is_passed_to_guard(plugin, active):
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [Guard('SubagentStop', None, lambda p: (1, str(p['stop_hook_active'])))]
''')
    payload = fixture('SubagentStop')
    payload['stop_hook_active'] = active
    assert_refusal(replay(plugin, 'SubagentStop', json.dumps(payload)), 'SubagentStop', str(active))


def test_session_context_is_combined_and_safe_json(plugin):
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [Guard('SessionStart', None, lambda p: (0, '{"decision":"block"}')),
          Guard('SessionStart', None, lambda p: (0, 'memory context'))]
''')
    result = replay(plugin, 'SessionStart', json.dumps(fixture('SessionStart')))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': '{"decision":"block"}\nmemory context'}}


def test_session_start_guards_run_together_in_guard_order(plugin):
    # #346: SessionStart's guards wait on git, ssh-keygen and fsync; run together, each one's
    # waits overlap the others' work. Each guard below returns only once both are running.
    install(plugin, '''
import threading
from wuwei.guards import Guard
both = threading.Barrier(2, timeout=5)
def first(payload):
    both.wait()
    return 0, 'first'
def second(payload):
    both.wait()
    raise ValueError('second failed')
def other(payload):
    return 1, 'not this event'
GUARDS = [Guard('SessionStart', None, first), Guard('SubagentStop', None, other),
          Guard('SessionStart', 'NoSuchTool', other), Guard('SessionStart', None, second)]
''')
    result = replay(plugin, 'SessionStart', json.dumps(fixture('SessionStart')))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['hookSpecificOutput']['additionalContext'] == (
        'first\nValueError: second failed')


@pytest.mark.parametrize('event', EVENTS)
@pytest.mark.parametrize('raw', ['', '{', '[]', 'null', '42', 'true', '{}', '{"x":NaN}'])
def test_malformed_payload(plugin, event, raw):
    result = replay(plugin, event, raw)
    reason = result.stderr.strip()
    assert reason and 'Traceback' not in reason
    assert_refusal(result, event, reason, malformed=True)


COMMON_FIELDS = ('session_id', 'transcript_path', 'cwd', 'hook_event_name')


def payload_field_cases():
    for path in PAYLOADS:
        payload = json.loads(path.read_text())
        fields = ['session_id', 'transcript_path', 'cwd', 'hook_event_name']
        event = path.parent.name
        fields += {'PreToolUse': ['tool_name', 'tool_use_id', 'tool_input'],
                   'PostToolUse': ['tool_name', 'tool_use_id', 'tool_input', 'tool_response'],
                   'SubagentStop': ['stop_hook_active', 'last_assistant_message', 'agent_id',
                                    'agent_type', 'agent_transcript_path'],
                   'SessionStart': ['source']}[event]
        fields += ['tool_input.' + field for field in
                   {'Bash': ['command'], 'Write': ['file_path', 'content'],
                    'Edit': ['file_path', 'old_string', 'new_string'],
                    'Agent': ['prompt', 'description', 'subagent_type']}.get(payload.get('tool_name'), [])]
        for field in fields:
            if field.split('.')[-1] in (payload['tool_input'] if field.startswith('tool_input.') else payload):
                yield path, field  # handback.json has no last_assistant_message to remove (#473)


@pytest.mark.parametrize('path', PAYLOADS, ids=lambda p: p.name)
@pytest.mark.parametrize('field', COMMON_FIELDS)
def test_missing_required_field(plugin, path, field):
    payload = json.loads(path.read_text())
    del payload[field]
    result = replay(plugin, path.parent.name, json.dumps(payload))
    assert field in result.stderr
    assert_refusal(result, path.parent.name, result.stderr.strip(), malformed=True)


@pytest.mark.parametrize('event,field,value', [
    ('PreToolUse', 'session_id', ''), ('PreToolUse', 'cwd', 1),
    ('PreToolUse', 'hook_event_name', 'Stop'),
])
def test_invalid_field_type_or_value(plugin, event, field, value):
    payload = fixture(event)
    payload[field] = value
    result = replay(plugin, event, json.dumps(payload))
    assert field in result.stderr
    assert_refusal(result, event, result.stderr.strip(), malformed=True)


@pytest.mark.parametrize('path,field', [(p, f) for p, f in payload_field_cases() if f not in COMMON_FIELDS])
def test_optional_fields_may_be_absent(plugin, path, field):
    payload = json.loads(path.read_text())
    container = payload['tool_input'] if field.startswith('tool_input.') else payload
    del container[field.split('.')[-1]]
    result = replay(plugin, path.parent.name, json.dumps(payload))
    assert result.returncode == 0, result.stderr


def test_guard_missing_field_still_fails_closed(plugin):
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [Guard('SubagentStop', None, lambda p: (0, p['last_assistant_message']))]
''')
    payload = fixture('SubagentStop')
    del payload['last_assistant_message']
    result = replay(plugin, 'SubagentStop', json.dumps(payload))
    assert 'KeyError' in result.stderr
    assert_refusal(result, 'SubagentStop', result.stderr.strip())


@pytest.mark.parametrize('raw', ['', '[]', '{}'])
def test_malformed_subprocess_replay(subprocess_plugin, raw):
    result = subprocess_replay(subprocess_plugin, 'PreToolUse', raw)
    assert_refusal(result, 'PreToolUse', result.stderr.strip(), malformed=True)


@pytest.mark.parametrize('source,reason', [
    ('raise RuntimeError("broken registry")', 'broken registry'),
    ('GUARDS = None', 'GUARDS must be a list'),
    ('GUARDS = [None]', 'invalid guard record'),
    ("from wuwei.guards import Guard\nGUARDS = [Guard('Typo', None, lambda p: (0, ''))]", 'unknown guard event'),
    ("from wuwei.guards import Guard\nGUARDS = [Guard('SubagentStop', '[', lambda p: (0, ''))]", 'unterminated character set'),
])
def test_broken_registry(plugin, source, reason):
    install(plugin, source)
    result = replay(plugin, 'SubagentStop', json.dumps(fixture('SubagentStop')))
    assert reason in result.stderr
    assert_refusal(result, 'SubagentStop', result.stderr.strip(), malformed=True)


@pytest.mark.parametrize('body,reason', [
    ('raise RuntimeError("guard unavailable")', 'guard unavailable'),
    ('raise SystemExit(0)', 'SystemExit'),
    ('raise KeyboardInterrupt()', 'KeyboardInterrupt'),
    ('return None', 'invalid guard result'),
    ('return (False, "bad")', 'invalid guard result'),
    ('return (3, "bad")', 'invalid guard result'),
    ('return (1, None)', 'invalid guard result'),
    ('return (1, "")', 'invalid guard result'),
])
def test_guard_errors_do_not_skip_later_guards(plugin, body, reason):
    install(plugin, f'''
from wuwei.guards import Guard

def check(payload):
    {body}

GUARDS = [Guard('SubagentStop', None, check), Guard('SubagentStop', None, lambda p: (1, 'later refusal'))]
''')
    result = replay(plugin, 'SubagentStop', json.dumps(fixture('SubagentStop')))
    # #362: the later guard ran; its finding is the one reason printed.
    assert result.stderr == 'later refusal\n'
    assert_refusal(result, 'SubagentStop', 'later refusal')
    install(plugin, f'''
from wuwei.guards import Guard

def check(payload):
    {body}

GUARDS = [Guard('SubagentStop', None, check)]
''', 'alone')
    (plugin[0] / 'cli/wuwei/guards/fake.py').unlink()
    result = replay(plugin, 'SubagentStop', json.dumps(fixture('SubagentStop')))
    assert reason in result.stderr
    assert_refusal(result, 'SubagentStop', result.stderr[:-1])


@pytest.mark.parametrize('event', ['PreToolUse', 'SubagentStop'])
def test_valid_empty_text_and_extra_fields(plugin, event):
    payload = fixture(event)
    if event == 'PreToolUse':
        payload.update(tool_name='Edit', tool_input={'file_path': '/tmp/file',
                                                   'old_string': '', 'new_string': ''})
    else:
        payload['last_assistant_message'] = ''
        payload['agent_type'] = ''
    payload['future_field'] = {'value': 42}
    install(plugin, f'''
from wuwei.guards import Guard
GUARDS = [Guard({event!r}, None, lambda p: (0 if p['future_field']['value'] == 42 else 1, ''))]
''')
    result = replay(plugin, event, json.dumps(payload))
    assert result.returncode == 0, result.stderr


def test_unknown_tool_is_extensible(plugin):
    payload = fixture('PreToolUse')
    payload.update(tool_name='mcp__example__operation', tool_input={'future': 1})
    result = replay(plugin, 'PreToolUse', json.dumps(payload))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('event,matcher,reason', [
    ('Typo', None, 'unknown guard event'),
    ('SubagentStop', '[', 'unterminated character set'),
])
def test_discovery_validates_records(plugin, event, matcher, reason):
    from wuwei.guards import discover
    install(plugin, f"""
from wuwei.guards import Guard
GUARDS = [Guard({event!r}, {matcher!r}, lambda p: (0, ''))]
""")
    with pytest.raises((ValueError, re.error), match=reason):
        discover()


def test_unaccounted_shell_mention_blocks_hook(plugin):
    install(plugin, '''
from wuwei.guards import Guard
from wuwei.shell import normalize

def check(payload):
    normalize(payload['tool_input']['command'])
    return 0, ''

GUARDS = [Guard('PreToolUse', 'Bash', check)]
''')
    payload = fixture('PreToolUse')
    payload.update(tool_name='Bash', tool_input={'command': '''awk 'BEGIN {system("git push")}' '''})
    result = replay(plugin, 'PreToolUse', json.dumps(payload))
    assert result.returncode == 2
    assert 'run git or gh as a plain command' in result.stderr


DAY = '2026-09-28'
HEAD_REF = 'acme/app#1'


def git(*args, cwd):
    return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def seeded_workspace(subprocess_plugin, tmp_path, monkeypatch):
    """A day as the dry run left it: repo, origin, item worktree, claimed PR and live seats."""
    from fakes.integrity import seed
    from wuwei import state, workspace
    root, env = subprocess_plugin
    shutil.copytree(ROOT / 'keys', root / 'keys')
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    env = {key: value for key, value in env.items() if not key.startswith('GIT_')}
    (tmp_path / '.wuwei/config.toml').write_text(
        '[owner]\nhandles = ["owner"]\n[[repos]]\nname = "acme/app"\npath = "repos/app"\n'
        'default_branch = "main"\nfast_checks = ["unit"]\n'
        'identity = {name = "Builder", email = "builder@example.test"}\n'
        # The running seat keeps every turn dirty, so Stop pays the rotation check and prints nothing.
        '[sessions]\nrotate_after = { turns = 1 }\n'
        # Advisory: the builder stop pays the whole spec check and still ends cleanly.
        '[spec]\nmode = "advisory"\n')
    for name in ('spine.md', 'index.md'):
        (tmp_path / '.wuwei/memory/notes').mkdir(parents=True, exist_ok=True)
        (tmp_path / '.wuwei/memory' / name).write_text('Memory\n')
    (tmp_path / '.wuwei/memory/goals.md').write_text(
        '# Goals\n\n## G-1\noutcome: Ship ITEM-1\nmeasure: merged\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    from wuwei import integrity
    integrity.initialize(tmp_path / '.wuwei')
    seed(tmp_path)
    if shutil.which('ssh-keygen'):
        # Sign the copy so SessionStart pays the full measurement a release install pays.
        key = tmp_path / 'signing'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                       check=True, capture_output=True)
        for target in (root / integrity.KEY, tmp_path / '.wuwei/integrity/pinned.pub'):
            target.chmod(0o644)
            shutil.copyfile(str(key) + '.pub', target)
        integrity.write_manifest(root)
        assert integrity.signature_adapter().sign(root / integrity.MANIFEST, key).exit == 0
    repo = tmp_path / 'repos/app'
    repo.mkdir(parents=True)
    git('init', '-q', '--bare', '-b', 'main', str(tmp_path / 'origin.git'), cwd=tmp_path)
    git('init', '-q', '-b', 'main', cwd=repo)
    git('config', 'user.name', 'Builder', cwd=repo)
    git('config', 'user.email', 'builder@example.test', cwd=repo)
    (repo / 'README.md').write_text('app\n')
    git('add', '-A', cwd=repo)
    git('commit', '-q', '-m', 'start', cwd=repo)
    git('remote', 'add', 'origin', str(tmp_path / 'origin.git'), cwd=repo)
    git('push', '-q', '-u', 'origin', 'main', cwd=repo)
    tree = tmp_path / 'worktrees/ITEM-1'
    git('worktree', 'add', '-q', '-b', 'item-1', str(tree), cwd=repo)
    (tree / 'change.txt').write_text('change\n')
    git('add', '-A', cwd=tree)
    git('commit', '-q', '-m', 'change', cwd=tree)
    head = git('rev-parse', 'HEAD', cwd=tree)

    now = DAY + 'T12:00:00+00:00'
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', now)
    env['WUWEI_NOW'] = now
    directory = workspace.day_dir(tmp_path)
    brief = directory / 'briefs/builder-1.md'
    brief.parent.mkdir(parents=True)
    brief.write_text('Build ITEM-1.\n')
    relative = str(brief.relative_to(tmp_path))
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['ITEM-1'], planner_session_id='planner', goals=['G-1'],
        items={'ITEM-1': {'phase': 'planned', 'status': 'running', 'worktree': 'worktrees/ITEM-1'}}),
        tmp_path)
    for phase in ('implement', 'gate', 'raised'):
        state.transition('ITEM-1', phase, tmp_path)
    state.record_pr(tmp_path, 'ITEM-1', HEAD_REF, raised=False)
    state._write_state(lambda data: data.update(
        seats={'builder-1': {'id': 'builder-1', 'role': 'builder', 'item': 'ITEM-1', 'brief': relative,
                             'status': 'running', 'started_at': now}},
        fast_checks={'acme/app': {'unit': {'sha': head, 'exit': 0}}},
        watch={'clock_at': now, 'poll_at': now, 'measured_at': now, 'prs': {HEAD_REF: {}},
               'actions': {}}), tmp_path)
    rows = [{'kind': 'plan.session', 'payload': {'session_id': 'planner'}, 'ts': now},
            {'kind': 'brief written', 'payload': {'path': relative, 'worktree': str(tree)}, 'ts': now}]
    rows += [{'kind': 'note', 'payload': {'detail': 'x' * 200}, 'ts': now} for _ in range(1000)]
    rows.append({'kind': 'watch: clock', 'payload': {}, 'ts': now})
    events = directory / 'events.jsonl'
    events.chmod(0o644)
    with events.open('a') as stream:
        stream.writelines(json.dumps(row) + '\n' for row in rows)
    events.chmod(0o444)
    transcript = tmp_path / 'builder-1.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {'content': 'WUWEI brief: ' + relative}})
                          + '\n' + json.dumps({'type': 'assistant', 'message': {'content': 'Done.'}}) + '\n')
    calls = tmp_path / 'gh-calls'
    gh = tmp_path / 'path/gh'
    gh.write_text(f'#!/bin/sh\necho "$@" >> {shlex.quote(str(calls))}\nexit 1\n')
    gh.chmod(0o755)
    saved = tmp_path / 'saved-day'
    shutil.copytree(directory, saved)
    payloads = {
        'SubagentStop': ('SubagentStop', {'cwd': str(tmp_path), 'agent_id': 'builder-agent',
                                          'agent_type': 'wuwei:builder', 'last_assistant_message': 'Done.',
                                          'agent_transcript_path': str(transcript)}),
        'SessionStart': ('SessionStart', {'cwd': str(tmp_path)}),
        'commit': ('PreToolUse', {'cwd': str(tree), 'tool_name': 'Bash',
                                  'tool_input': {'command': 'git commit -m change'}}),
        'push': ('PreToolUse', {'cwd': str(tree), 'tool_name': 'Bash',
                                'tool_input': {'command': 'git push origin HEAD:refs/heads/item-1'}}),
    }
    def reset():
        for path in (directory, saved):
            for item in path.rglob('*'):
                item.chmod(0o755 if item.is_dir() else 0o644)
        shutil.rmtree(directory)
        shutil.copytree(saved, directory)
    return (root, env), payloads, reset, calls


# #516: the modules the SubagentStop path runs beyond the PreToolUse Bash call's.
SUBAGENT_STOP_MODULES = {'wuwei.guards.agent_launch',
                         'wuwei.guards.spec', 'wuwei.guards.verdict', 'wuwei.brief', 'wuwei.dispatch',
                         'wuwei.sessions', 'wuwei.specmode',
                         # #839: a git commit's PreToolUse no longer reads the identity (state, registry).
                         'wuwei.registry', 'wuwei.state', 'wuwei.verdict', 'datetime', '_datetime', 'fcntl',
                         'math'}  # datetime imports math on Python 3.11


def run_launcher(seeded_workspace, tmp_path, path, script=LAUNCHER_MODULES, printed=False):
    (root, env), payloads, reset, _ = seeded_workspace
    event, fields = payloads[path]
    out = tmp_path / 'launcher-out.json'
    reset()
    result = subprocess.run([sys.executable, '-I', '-P', '-S', '-c', script, str(root / 'cli'), str(root),
                             str(out), 'hook', event], input=json.dumps({**fixture(event), **fields}),
                            text=True, capture_output=True, cwd=root.parent, env=env)
    assert result.returncode == 0 and (printed or result.stdout == ''), result.stderr + result.stdout
    return json.loads(out.read_text())


def test_subagent_stop_loads_no_more_than_pretooluse(seeded_workspace, tmp_path):
    # #516, in the #346 style: the common SubagentStop path (message present, seat known)
    # loads only PreToolUse's modules and the ones it runs. Second runs: warm caches.
    loaded = {path: [set(run_launcher(seeded_workspace, tmp_path, path)) for _ in range(2)][1]
              for path in ('commit', 'SubagentStop')}
    assert loaded['SubagentStop'] - loaded['commit'] - SUBAGENT_STOP_MODULES == set()


def test_session_start_loads_only_what_it_prints(seeded_workspace, tmp_path):
    # #587: the block needs no promotion writes (shutil, uuid), no digest months (calendar),
    # no temp-file module in the ssh adapter and, with no decision routes, no decision ledger.
    loaded = [set(run_launcher(seeded_workspace, tmp_path, 'SessionStart', printed=True)) for _ in range(2)][1]
    assert loaded & {'shutil', 'tempfile', 'bz2', 'lzma', 'random', 'uuid', 'calendar',
                     'wuwei.decision'} == set()


COUNTING = (
    'import atexit, json, os, runpy, sys\n'
    'out = sys.argv.pop(3); sys.path[:0] = sys.argv[1:3]; del sys.argv[1:3]\n'
    'from wuwei import state\n'
    'counts = {"fsync": 0, "appends": 0}\n'
    'fsync, append = os.fsync, state._append_jsonl\n'
    'def counted_fsync(fd):\n    counts["fsync"] += 1; return fsync(fd)\n'
    'def counted_append(*args):\n    counts["appends"] += 1; return append(*args)\n'
    'os.fsync, state._append_jsonl = counted_fsync, counted_append\n'
    'atexit.register(lambda: open(out, "w").write(json.dumps(counts)))\n'
    'runpy.run_module("wuwei", run_name="__main__", alter_sys=True)\n')


def test_subagent_stop_writes_state_once(seeded_workspace, tmp_path):
    # #516: one state write per seat stop and one directory fsync per state write.
    # #843: the seat-free discovery request is gone, one append fewer. #847: no session row
    # and no snapshot: the file and the directory fsync.
    from wuwei import state, workspace
    root = seeded_workspace[0][0].parent
    run_launcher(seeded_workspace, tmp_path, 'SubagentStop')  # writes the config cache, as on a warm day
    assert run_launcher(seeded_workspace, tmp_path, 'SubagentStop', COUNTING) == {'fsync': 2, 'appends': 2}
    data = state.read_state(root)
    seat = data['seats']['builder-1']
    assert (seat['status'], seat['agent_id']) == ('stopped', 'builder-agent')
    assert 'abc123' not in data.get('sessions', {})
    rows = [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    rows = [row for row in rows if row['kind'] != 'note'][-2:]
    assert [row['kind'] for row in rows] == ['seat stopped', 'spec.warned']
    assert rows[0]['payload'] == {'name': 'builder-1', 'prs_seen': True}


@pytest.mark.parametrize('session_id, recorded', [('wuwei-probe', 0), ('a-session', 1)])
def test_probe_refusals_are_not_recorded(plugin, session_id, recorded):
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [Guard('PreToolUse', None, lambda payload: (1, 'guard reason'))]
''')
    payload = {**fixture('PreToolUse'), 'session_id': session_id, 'cwd': str(plugin[0])}
    result = replay(plugin, 'PreToolUse', json.dumps(payload))
    assert_refusal(result, 'PreToolUse', 'guard reason')
    from wuwei import workspace
    events = workspace.day_dir(plugin[0]) / 'events.jsonl'
    rows = events.read_text().splitlines() if events.exists() else []
    assert sum(json.loads(row)['kind'] == 'hook.refusal' for row in rows) == recorded


def test_seat_question_without_record_stops_freely(subprocess_plugin, tmp_path):
    # Part 14: a seat names a one-way question in its result; nothing asks it for a record.
    payload = json.loads((ROOT / 'tests/payloads/SubagentStop/example.json').read_text())
    payload.update(cwd=str(tmp_path), agent_type='wuwei:builder',
                   agent_transcript_path=str(tmp_path / 'missing.jsonl'),
                   last_assistant_message='Should I add a cache?\nBlocked: none\nGap: none\nChange: none')
    result = subprocess_replay(subprocess_plugin, 'SubagentStop', json.dumps(payload))
    assert result.returncode == 0 and 'decision' not in result.stdout, result.stderr


def enforce(plugin, value=False):
    (plugin[0] / '.wuwei/config.toml').write_text(f'[guards]\nenforce = {str(value).lower()}\n')


def events_of(plugin, kind):
    from wuwei import workspace
    path = workspace.day_dir(plugin[0]) / 'events.jsonl'
    rows = [json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []
    return [row['payload'] for row in rows if row['kind'] == kind]


def refusing(event, reason='guard reason'):
    return f'''
from wuwei.guards import Guard
GUARDS = [Guard({event!r}, None, lambda payload: (1, {reason!r}))]
'''


@pytest.mark.parametrize('event', ['PreToolUse', 'PostToolUse'])
def test_enforce_off_records_and_allows(plugin, event):
    enforce(plugin)
    install(plugin, refusing(event))
    payload = (json.loads((ROOT / 'tests/payloads/PreToolUse/bash.json').read_text())
               if event == 'PreToolUse' else fixture(event))
    result = replay(plugin, event, json.dumps(payload))
    assert (result.returncode, result.stdout) == (0, ''), result.stderr
    recorded, = events_of(plugin, 'guard.would_refuse')
    assert recorded['guard'] == 'fake' and recorded['reason'] == 'guard reason'
    assert not {'area', 'level', 'posture'} & set(recorded)
    assert recorded['session'] == payload['session_id'] and 'item' not in recorded
    if event == 'PreToolUse':
        assert recorded['target'] == 'npm test'
    assert events_of(plugin, 'hook.refusal') == []


def test_enforce_off_does_not_log_the_doctor_probe(plugin):
    enforce(plugin)
    install(plugin, refusing('PreToolUse'))
    payload = {**fixture('PreToolUse'), 'session_id': 'wuwei-probe'}
    assert_refusal(replay(plugin, 'PreToolUse', json.dumps(payload)), 'PreToolUse', 'guard reason')
    assert events_of(plugin, 'guard.would_refuse') == []


def test_enforce_off_blocks_when_it_cannot_record(plugin):
    from wuwei import state
    enforce(plugin)
    install(plugin, refusing('PreToolUse'))
    plugin[1].setattr(state, 'append_event', lambda *a, **k: (_ for _ in ()).throw(OSError('disk')))
    result = replay(plugin, 'PreToolUse', json.dumps(fixture('PreToolUse')))
    assert result.returncode == 2
    assert json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert 'could not record a logged refusal' in result.stderr


@pytest.mark.parametrize('raw', [None, '[guards]\nenforce = true\n'])
def test_enforce_on_refuses_as_before(plugin, raw):
    if raw:
        (plugin[0] / '.wuwei/config.toml').write_text(raw)
    install(plugin, refusing('PreToolUse'))
    assert_refusal(replay(plugin, 'PreToolUse', json.dumps(fixture('PreToolUse'))),
                   'PreToolUse', 'guard reason')
    assert events_of(plugin, 'guard.would_refuse') == []


@pytest.mark.parametrize('command,target', [
    ("sh -c 'git push --force origin main'", 'git push --force origin main'),
    ('echo $(', 'echo $('),
])
def test_logged_target_is_the_normalised_command(plugin, command, target):
    enforce(plugin)
    install(plugin, refusing('PreToolUse'))
    payload = {**fixture('PreToolUse'), 'tool_name': 'Bash', 'tool_input': {'command': command}}
    assert replay(plugin, 'PreToolUse', json.dumps(payload)).returncode == 0
    assert events_of(plugin, 'guard.would_refuse')[0]['target'] == target


def test_logged_target_is_redacted(plugin):
    from wuwei import report, security, workspace
    security.initialize(plugin[0] / '.wuwei')
    canary = json.loads((plugin[0] / '.wuwei/security.json').read_text())['canary']
    enforce(plugin)
    install(plugin, refusing('PreToolUse'))
    token = 'ghp_' + 'a' * 36
    for command in (f'echo {canary} https://x', f'git push --force https://x:{token}@github.com/o/r'):
        payload = {**fixture('PreToolUse'), 'tool_name': 'Bash', 'tool_input': {'command': command}}
        assert replay(plugin, 'PreToolUse', json.dumps(payload)).returncode == 0
    recorded = json.dumps(events_of(plugin, 'guard.would_refuse'))
    shown = '\n'.join(report.shadow_lines([workspace.day_dir(plugin[0])]))
    for secret in (canary, token):
        assert secret not in recorded and secret not in shown


def forget_guards():
    """Drop loaded guard modules and their package attributes so stubs and real modules reload."""
    import wuwei.guards
    for name in [key for key in sys.modules if key.startswith('wuwei.guards.')]:
        del sys.modules[name]
        vars(wuwei.guards).pop(name.rsplit('.', 1)[-1], None)


def test_floor_at_the_hook(plugin):
    # #837: with guards.enforce = false the floor still blocks, with the reason alone.
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    enforce(plugin)
    try:
        for name in ('protect_state',):
            forget_guards()
            install(plugin, refusing('PreToolUse', 'kept'), name)
            assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', 'kept')
            assert events_of(plugin, 'guard.would_refuse') == []
            assert events_of(plugin, 'hook.refusal')[-1]['refusals'] == [{'guard': name, 'reason': 'kept', 'exit': 1}]
            (plugin[0] / f'cli/wuwei/guards/{name}.py').unlink()
        for name in ('edges', 'fake'):
            forget_guards()
            install(plugin, refusing('PreToolUse', 'kept'), name)
            result = replay(plugin, 'PreToolUse', payload)
            assert (result.returncode, result.stdout, result.stderr) == (0, '', '')
            (plugin[0] / f'cli/wuwei/guards/{name}.py').unlink()
        assert [row['guard'] for row in events_of(plugin, 'guard.would_refuse')] == ['edges', 'fake']
        forget_guards()
        install(plugin, refusing('PreToolUse', 'kept'), 'edges')
        enforce(plugin, True)
        assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', 'kept')
        assert len(events_of(plugin, 'guard.would_refuse')) == 2
    finally:
        forget_guards()


FORCE = 'force-push is refused; push a branch instead'


def test_refusal_records_guard_and_target_for_why(plugin):
    from wuwei.__main__ import main
    install(plugin, refusing('PreToolUse', FORCE))
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', FORCE)
    assert events_of(plugin, 'hook.refusal') == [
        {'reason': FORCE, 'refusals': [{'guard': 'fake', 'reason': FORCE, 'exit': 1}], 'target': 'npm test'}]
    (plugin[0] / '.wuwei/config.toml').write_text('')
    assert main(['why', 'last refusal']) == 0
    lines = plugin[2].readouterr().out.splitlines()
    for line in ('command: npm test', 'guard: fake', 'rule: force-push is refused',
                 'fix: push a branch instead'):
        assert line in lines


def test_refusal_without_a_target_is_still_recorded_and_enforced(plugin):
    from wuwei.commands import hook
    install(plugin, refusing('PreToolUse', FORCE))
    plugin[1].setattr(hook, 'redacted_target', lambda payload, root: 1 / 0)
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', FORCE)
    assert events_of(plugin, 'hook.refusal') == [
        {'reason': FORCE, 'refusals': [{'guard': 'fake', 'reason': FORCE, 'exit': 1}]}]


def test_refusal_from_two_guards_lists_both_in_order(plugin):
    install(plugin, refusing('PreToolUse', 'first; a'), 'first')
    install(plugin, refusing('PreToolUse', 'second'), 'second')
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', 'first; a')
    recorded, = events_of(plugin, 'hook.refusal')
    assert recorded['reason'] == 'first; a'
    assert recorded['refusals'] == [{'guard': 'first', 'reason': 'first; a', 'exit': 1},
                                    {'guard': 'second', 'reason': 'second', 'exit': 1}]


def exiting(code, reason='guard reason'):
    return f'''
from wuwei.guards import Guard
GUARDS = [Guard('PreToolUse', None, lambda payload: ({code}, {reason!r}))]
'''


@pytest.mark.parametrize('code', [1, 2])
def test_refusal_rows_and_warnings_carry_the_exit(plugin, code):
    # #422: a refusal (exit 1) and a guard that could not run (exit 2) are told apart.
    install(plugin, exiting(code))
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', 'guard reason')
    assert events_of(plugin, 'hook.refusal')[-1]['refusals'] == [
        {'guard': 'fake', 'reason': 'guard reason', 'exit': code}]
    enforce(plugin)
    assert replay(plugin, 'PreToolUse', payload).returncode == 0
    recorded, = events_of(plugin, 'guard.would_refuse')
    assert recorded['exit'] == code


def event_count(plugin):
    from wuwei import workspace
    path = workspace.day_dir(plugin[0]) / 'events.jsonl'
    return len(path.read_text().splitlines()) if path.exists() else 0


def test_event_count_per_hook_path(plugin):
    # #422: telemetry adds no record to a hook: allowed 0, refused 1, warned 1, doctor probe 0.
    payload = json.loads((ROOT / 'tests/payloads/PreToolUse/bash.json').read_text())
    install(plugin, exiting(0, ''))
    before = event_count(plugin)
    assert replay(plugin, 'PreToolUse', json.dumps(payload)).returncode == 0
    assert event_count(plugin) - before == 0
    forget_guards()
    install(plugin, exiting(1))
    before = event_count(plugin)
    assert replay(plugin, 'PreToolUse', json.dumps(payload)).returncode == 2
    assert event_count(plugin) - before == 1
    before = event_count(plugin)
    probe = {**payload, 'session_id': 'wuwei-probe'}
    assert replay(plugin, 'PreToolUse', json.dumps(probe)).returncode == 2
    assert event_count(plugin) - before == 0
    enforce(plugin)
    before = event_count(plugin)
    assert replay(plugin, 'PreToolUse', json.dumps(payload)).returncode == 0
    assert event_count(plugin) - before == 1


def returning(reason, code=2):
    return f'''
from wuwei.guards import Guard
from wuwei.shell import {reason}
GUARDS = [Guard('PreToolUse', None, lambda payload: ({code}, {reason}))]
'''


@pytest.mark.parametrize('value', [True, False])
def test_unparsed_and_workspace_root_warn_by_reason(plugin, value):
    # #347: the two reasons are decided by their text, not by the guard or the floor.
    from wuwei.shell import UNPARSED, WORKSPACE_ROOT
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    enforce(plugin, value)
    guards = plugin[0] / 'cli/wuwei/guards'
    try:
        forget_guards()
        install(plugin, returning('UNPARSED'), 'deploy')
        install(plugin, returning('UNPARSED'), 'pr')
        result = replay(plugin, 'PreToolUse', payload)
        assert (result.returncode, result.stdout, result.stderr) == (0, '', '')
        assert [row['reason'] for row in events_of(plugin, 'guard.would_refuse')] == [UNPARSED]
        for module in ('deploy', 'pr'):
            (guards / f'{module}.py').unlink()
        forget_guards()
        install(plugin, returning('WORKSPACE_ROOT', 1), 'protect_state')
        result = replay(plugin, 'PreToolUse', payload)
        assert (result.returncode, result.stdout, result.stderr) == (0, '', '')
        assert events_of(plugin, 'guard.would_refuse')[-1]['reason'] == WORKSPACE_ROOT
        forget_guards()
        install(plugin, refusing('PreToolUse', 'kept'), 'protect_state')
        assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', 'kept')
    finally:
        forget_guards()


def test_terminal_as_bash(tmp_path):
    # #727: a terminal tab's command is the Bash call it types, in the tab's cwd.
    from wuwei.commands.hook import as_bash
    call = {'hook_event_name': 'PreToolUse', 'session_id': 's', 'cwd': str(tmp_path),
            'transcript_path': str(tmp_path / 't.jsonl'), 'tool_name': 'mcp__terminal__run_in_terminal',
            'tool_input': {'command': 'sleep 600', 'cwd': 'demo'}}
    seen = as_bash(call)
    assert (seen['tool_name'], seen['tool_input'], seen['cwd']) == (
        'Bash', {'command': 'sleep 600'}, str(tmp_path / 'demo'))
    assert as_bash({**call, 'tool_input': {'command': 'ls'}})['cwd'] == str(tmp_path)
    for same in ({**call, 'hook_event_name': 'PostToolUse'},
                 {**call, 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}):
        assert as_bash(same) == same
    for inputs in ({'command': 3}, {'command': 'ls', 'cwd': 3}, 'ls'):
        with pytest.raises(ValueError, match='payload'):
            as_bash({**call, 'tool_input': inputs})


def test_stop_is_registered_and_precompact_stays_retired():
    # #949 restores Stop as an advisory planner wake; PreCompact stays retired.
    from wuwei.__main__ import main
    hooks = json.loads((Path(__file__).resolve().parents[1] / 'hooks/hooks.json').read_text())['hooks']
    assert sorted(hooks) == ['PostToolUse', 'PreToolUse', 'SessionStart', 'Stop', 'SubagentStop']
    for event in ('PreCompact',):
        with pytest.raises(SystemExit) as raised:
            main(['hook', event])
        assert raised.value.code == 2


# SessionStart (moved from test_watch.py with the watch, #847): orientation, memory, orphan seats.

@pytest.fixture
def start_case(tmp_path, monkeypatch):
    from fakes.integrity import measured
    from wuwei import state
    measured(monkeypatch)
    (tmp_path / '.wuwei/memory').mkdir(parents=True)
    (tmp_path / '.wuwei/memory/spine.md').write_text('Memory spine\n')
    (tmp_path / '.wuwei/memory/index.md').write_text('Index\n')
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nhandles=["owner"]\n'
        '[[repos]]\nname="example/project"\npath="repo"\ndefault_branch="main"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    state._write_state(lambda data: data.update(raised_prs=['example/project#7']), tmp_path)
    return tmp_path


@pytest.mark.parametrize('condition,expected', [('clean', 0), ('corrupt', 2)])
def test_session_start_table(start_case, condition, expected):
    from wuwei.guards import lifecycle
    root = start_case
    if condition == 'corrupt':  # #844: records that fail their schema (a torn cache rebuilds)
        from fakes import records
        records.write(root, {'cap': 'bad'})
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert code == expected
    if condition != 'corrupt':
        assert 'Memory spine' in message and 'Size:' in message
    assert 'watch' not in message


def test_session_start_names_orphan_seats(start_case):
    from wuwei import state, workspace
    from wuwei.guards import lifecycle
    root = start_case
    prior = workspace.day_dir(root).parent / '2026-09-27'
    state._write_state(lambda data: data.update(seats={
        'old-builder': {'status': 'running'}, 'finished': {'status': 'stopped'}}),
        directory=prior)
    code, message = lifecycle.session_start({'cwd': str(root)})
    assert code == 1
    assert 'orphan' in message and 'old-builder' in message and 'finished' not in message


def test_session_start_outside_scope(start_case):
    from wuwei.guards import lifecycle
    assert lifecycle.session_start({'cwd': str(start_case.parent / 'unrelated')}) == (0, '')


def test_session_start_exports_the_session_id(start_case, monkeypatch, tmp_path):
    from wuwei.guards import lifecycle
    env_file = tmp_path / 'env'
    monkeypatch.setenv('CLAUDE_ENV_FILE', str(env_file))
    lifecycle.session_start({'cwd': str(start_case), 'session_id': 'abc'})
    assert env_file.read_text() == 'export WUWEI_SESSION_ID=abc\n'


def test_session_real_cli_boundary(start_case):
    root = start_case
    project = Path(__file__).resolve().parents[1]
    payload = {'cwd': str(root), 'hook_event_name': 'SessionStart',
               'session_id': 'test', 'transcript_path': str(root / 'transcript')}
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'hook', 'SessionStart'],
        cwd=root, env={**os.environ, 'PYTHONPATH': str(project / 'cli')},
        input=json.dumps(payload), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
    assert 'Memory spine' in context and 'Size:' in context and 'watch' not in context


def test_session_payload_names_why_not_the_records(start_case):
    from wuwei import memory
    content, size, tokens = memory.session_payload(start_case)
    assert 'Full day state: wuwei why <item>' in content and '"raised_prs"' not in content
    assert size == len(content.encode('utf-8'))
    assert tokens == memory.estimated_tokens(content)
