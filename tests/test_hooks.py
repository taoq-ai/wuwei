"""Hook tables run in-process; fixture replays exercise the executable shim."""

from functools import cache
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
EVENTS = ('PreToolUse', 'PostToolUse', 'SubagentStop', 'SessionStart', 'PreCompact', 'Stop')


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
    for name in list(sys.modules):
        if name.startswith('wuwei.guards.'):
            del sys.modules[name]


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
    assert path.exists(), 'six hook mappings must exist'
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
               and record.check.__module__ == 'wuwei.guards.commit_push' for record in discover())
    assert any(guard.check.__module__ == 'wuwei.guards.deploy' for guard in discover())


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


BASH_GUARDS = {'commit_push', 'deploy', 'pr'}


@pytest.mark.parametrize('event, name, unloaded', [
    ('Stop', 'example', BASH_GUARDS | {'protect_state'}),
    ('PostToolUse', 'example', BASH_GUARDS | {'protect_state'}),
    ('PreToolUse', 'write', BASH_GUARDS),
])
def test_hook_imports_only_needed_guards(tmp_path, event, name, unloaded):
    # A fresh interpreter: loaded modules are process state and other tests import every guard.
    from fakes.integrity import seed
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    seed(tmp_path)
    payload = {**json.loads((ROOT / f'tests/payloads/{event}/{name}.json').read_text()),
               'cwd': str(tmp_path)}
    if event == 'Stop':
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


DENY = {'tomllib', 'hashlib', 'argparse', 'dataclasses', 'inspect', 'typing', 'datetime', 'subprocess'}


@pytest.mark.parametrize('inside, deny', [(False, DENY), (True, {'argparse', 'dataclasses', 'subprocess'})],
                         ids=['outside', 'workspace'])
def test_hook_imports_no_unused_stdlib(tmp_path, inside, deny):
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
              'sys.exit(3 if {"wuwei.calibrate", "wuwei.interview", "wuwei.profiles"} & set(sys.modules) else 0)\n')
    result = subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), json.dumps(calls)],
                            text=True, capture_output=True, cwd=tmp_path,
                            env={**os.environ, 'WUWEI_WORKSPACE': str(tmp_path), 'WUWEI_BENCH': '1'})
    assert result.returncode == 0, result.stderr
    assert 'calibrat' not in (ROOT / 'hooks/hooks.json').read_text()


def test_private_guard_module_is_ignored(plugin):
    install(plugin, 'raise RuntimeError("private helper imported")', '_helper')
    result = replay(plugin, 'Stop', json.dumps(fixture('Stop')))
    assert result.returncode == 0, result.stderr


def assert_refusal(result, event, reason, *, malformed=False):
    if event == 'SessionStart':
        assert result.returncode == 0
        assert reason in json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
        assert result.stderr == reason + '\n'
        return
    assert result.returncode == (1 if event == 'PreCompact' and not malformed else 2)
    assert result.stderr == reason + '\n'
    if event == 'PreToolUse':
        assert json.loads(result.stdout) == {'hookSpecificOutput': {
            'hookEventName': event, 'permissionDecision': 'deny',
            'permissionDecisionReason': reason}}
    elif event in ('Stop', 'SubagentStop'):
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
        assert result.stderr == ('guard reason\n' if event == 'Stop' else '')
        expected = {'hookSpecificOutput': {'hookEventName': event,
                                          'additionalContext': 'guard reason'}}
        assert result.stdout == (json.dumps(expected) + '\n' if event == 'SessionStart' else '')


def test_matching_and_all_refusing_reasons(plugin):
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [
    Guard('Stop', None, lambda p: (1, 'wrong event')),
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
    assert_refusal(result, 'PreToolUse', 'npm test\nsecond reason')


@pytest.mark.parametrize('active', [False, True])
def test_stop_active_is_passed_to_guard(plugin, active):
    install(plugin, '''
from wuwei.guards import Guard
GUARDS = [Guard('Stop', None, lambda p: (1, str(p['stop_hook_active'])))]
''')
    payload = fixture('Stop')
    payload['stop_hook_active'] = active
    assert_refusal(replay(plugin, 'Stop', json.dumps(payload)), 'Stop', str(active))


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
                   'Stop': ['stop_hook_active', 'last_assistant_message'],
                   'SubagentStop': ['stop_hook_active', 'last_assistant_message', 'agent_id',
                                    'agent_type', 'agent_transcript_path'],
                   'SessionStart': ['source'], 'PreCompact': ['trigger', 'custom_instructions']}[event]
        fields += ['tool_input.' + field for field in
                   {'Bash': ['command'], 'Write': ['file_path', 'content'],
                    'Edit': ['file_path', 'old_string', 'new_string'],
                    'Agent': ['prompt', 'description', 'subagent_type']}.get(payload.get('tool_name'), [])]
        for field in fields:
            yield path, field


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
GUARDS = [Guard('Stop', None, lambda p: (0, p['last_assistant_message']))]
''')
    payload = fixture('Stop')
    del payload['last_assistant_message']
    result = replay(plugin, 'Stop', json.dumps(payload))
    assert 'KeyError' in result.stderr
    assert_refusal(result, 'Stop', result.stderr.strip())


@pytest.mark.parametrize('raw', ['', '[]', '{}'])
def test_malformed_subprocess_replay(subprocess_plugin, raw):
    result = subprocess_replay(subprocess_plugin, 'PreToolUse', raw)
    assert_refusal(result, 'PreToolUse', result.stderr.strip(), malformed=True)


@pytest.mark.parametrize('source,reason', [
    ('raise RuntimeError("broken registry")', 'broken registry'),
    ('GUARDS = None', 'GUARDS must be a list'),
    ('GUARDS = [None]', 'invalid guard record'),
    ("from wuwei.guards import Guard\nGUARDS = [Guard('Typo', None, lambda p: (0, ''))]", 'unknown guard event'),
    ("from wuwei.guards import Guard\nGUARDS = [Guard('Stop', '[', lambda p: (0, ''))]", 'unterminated character set'),
])
def test_broken_registry(plugin, source, reason):
    install(plugin, source)
    result = replay(plugin, 'Stop', json.dumps(fixture('Stop')))
    assert reason in result.stderr
    assert_refusal(result, 'Stop', result.stderr.strip(), malformed=True)


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

GUARDS = [Guard('Stop', None, check), Guard('Stop', None, lambda p: (1, 'later refusal'))]
''')
    result = replay(plugin, 'Stop', json.dumps(fixture('Stop')))
    assert reason in result.stderr
    assert result.stderr.endswith('later refusal\n')
    assert_refusal(result, 'Stop', result.stderr.strip())


@pytest.mark.parametrize('event', ['PreToolUse', 'Stop', 'SubagentStop', 'PreCompact'])
def test_valid_empty_text_and_extra_fields(plugin, event):
    payload = fixture(event)
    if event == 'PreToolUse':
        payload.update(tool_name='Edit', tool_input={'file_path': '/tmp/file',
                                                   'old_string': '', 'new_string': ''})
    elif event in ('Stop', 'SubagentStop'):
        payload['last_assistant_message'] = ''
        if event == 'SubagentStop':
            payload['agent_type'] = ''
    else:
        payload['custom_instructions'] = ''
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
    ('Stop', '[', 'unterminated character set'),
])
def test_discovery_validates_records(plugin, event, matcher, reason):
    from wuwei.guards import discover
    install(plugin, f"""
from wuwei.guards import Guard
GUARDS = [Guard({event!r}, {matcher!r}, lambda p: (0, ''))]
""")
    with pytest.raises((ValueError, re.error), match=reason):
        discover()


@pytest.mark.parametrize('ci,bench,load,expected,wall_budget', [
    (False, False, 1.0, 'assert', None),
    (False, False, 4.0, 'skip', None),
    (False, False, 8.0, 'skip', None),
    (True, False, 1.0, 'skip', None),
    (True, True, 8.0, 'assert', None),
    (False, True, 8.0, 'assert', None),
    (False, True, 8.0, 'assert', 59),
    (False, True, 8.0, 'pass', 61),
])
def test_latency_budget_decision(monkeypatch, capsys, ci, bench, load, expected, wall_budget):
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.delenv('WUWEI_BENCH', raising=False)
    if ci:
        monkeypatch.setenv('CI', '1')
    if bench:
        monkeypatch.setenv('WUWEI_BENCH', '1')
    monkeypatch.setattr(os, 'getloadavg', lambda: (load, 0, 0))
    monkeypatch.setattr(os, 'cpu_count', lambda: 8)
    monkeypatch.setitem(globals(), 'startup_floor', lambda runs: (20.0, 22.0))
    if expected == 'pass':
        assert_latency_budget('hook', 51.0, 60.0, capsys, wall_budget=wall_budget)
    elif expected == 'assert':
        with pytest.raises(AssertionError, match=r'startup floor CPU 20\.00 ms, wall 22\.00 ms'):
            assert_latency_budget('hook', 51.0, 60.0, capsys, wall_budget=wall_budget)
    else:
        with pytest.raises(pytest.skip.Exception, match=r'CPU 51\.00 ms.*wall 60\.00 ms.*python3 -I startup floor CPU 20\.00 ms, wall 22\.00 ms.*load'):
            assert_latency_budget('hook', 51.0, 60.0, capsys)


@cache
def startup_floor(runs):
    """p95 CPU and wall ms of a bare interpreter start, the floor under every hook figure."""
    from resource import RUSAGE_CHILDREN, getrusage
    from statistics import quantiles
    from time import perf_counter

    cpu, wall = [], []
    for _ in range(runs):
        before = getrusage(RUSAGE_CHILDREN)
        start = perf_counter()
        subprocess.run([sys.executable, '-I', '-c', 'pass'], check=True)
        wall.append(perf_counter() - start)
        after = getrusage(RUSAGE_CHILDREN)
        cpu.append(after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime)
    return quantiles(cpu, n=100)[94] * 1000, quantiles(wall, n=100)[94] * 1000


def assert_latency_budget(name, cpu_ms, wall_ms, capsys, *, wall_budget=None, runs=60):
    load = os.getloadavg()[0]
    cpus = os.cpu_count() or 1
    floor_cpu, floor_wall = startup_floor(runs)
    report = (f'{name} p95 over {runs} runs: CPU {cpu_ms:.2f} ms, wall {wall_ms:.2f} ms, '
              f'python3 -I startup floor CPU {floor_cpu:.2f} ms, wall {floor_wall:.2f} ms, '
              f'load {load:.2f} on {cpus} CPUs')
    with capsys.disabled():
        print('\n' + report)
    # Budgets are enforced only when asked (WUWEI_BENCH=1): wall time on a working host is
    # load-bound, and a load heuristic made the suite red on busy developer machines.
    if os.environ.get('WUWEI_BENCH') == '1':
        if wall_budget is None:
            assert cpu_ms < 50, report
        else:
            assert wall_ms < wall_budget, report
    else:
        pytest.skip(report)


@pytest.mark.parametrize('event', ['PreToolUse', 'PostToolUse'])
def test_hook_latency(subprocess_plugin, capsys, event):
    from resource import RUSAGE_CHILDREN, getrusage
    from statistics import quantiles
    from time import perf_counter

    name = 'bash' if event == 'PreToolUse' else 'example'
    payload = (ROOT / f'tests/payloads/{event}/{name}.json').read_text()
    elapsed = []
    cpu = []
    for _ in range(60):
        before = getrusage(RUSAGE_CHILDREN)
        start = perf_counter()
        result = subprocess_replay(subprocess_plugin, event, payload)
        elapsed.append(perf_counter() - start)
        after = getrusage(RUSAGE_CHILDREN)
        cpu.append(after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime)
        assert result.returncode == 0, result.stderr
    cpu_ms = quantiles(cpu, n=100)[94] * 1000
    wall_ms = quantiles(elapsed, n=100)[94] * 1000
    assert_latency_budget(event, cpu_ms, wall_ms, capsys)


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
    payload.update(tool_name='Bash', tool_input={'command': 'echo "git push"'})
    result = replay(plugin, 'PreToolUse', json.dumps(payload))
    assert result.returncode == 2
    assert 'run git or gh as a plain command' in result.stderr


def test_status_line_latency(subprocess_plugin, capsys):
    from resource import RUSAGE_CHILDREN, getrusage
    from statistics import quantiles
    from time import perf_counter

    root, env = subprocess_plugin
    env['WUWEI_NOW'] = '2026-09-28T12:00:00+02:00'
    directory = root.parent / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True)
    (directory / 'state.json').write_text('{"items":{},"cap":1}\n')
    kinds = ('state.write', 'state.set', 'state.transition', 'seat launched',
             'brief written', 'fast_checks.record', 'seat stopped', 'retro.captured')
    events = ''.join(json.dumps({'kind': kinds[index % len(kinds)],
                                 'payload': {'detail': 'x' * 400},
                                 'ts': '2026-09-28T12:00:00+02:00'}) + '\n'
                     for index in range(10000))
    (directory / 'events.jsonl').write_text(events)
    cpu = []
    wall = []
    for _ in range(60):
        before = getrusage(RUSAGE_CHILDREN)
        start = perf_counter()
        result = subprocess.run([str(root / 'bin/wuwei'), 'status', '--line'],
                                capture_output=True, text=True, cwd=root.parent, env=env)
        wall.append(perf_counter() - start)
        after = getrusage(RUSAGE_CHILDREN)
        cpu.append(after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime)
        assert result.returncode == 0, result.stderr
    cpu_ms = quantiles(cpu, n=100)[94] * 1000
    wall_ms = quantiles(wall, n=100)[94] * 1000
    assert_latency_budget('status --line', cpu_ms, wall_ms, capsys)


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
        '[sessions]\nrotate_after = { turns = 1 }\n')
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
        tmp_path, reserved=False)
    for phase in ('implement', 'gate', 'raised'):
        state.transition('ITEM-1', phase, tmp_path)
    state.record_pr(tmp_path, 'ITEM-1', HEAD_REF, raised=False)
    state._write_state(lambda data: data.update(
        seats={'builder-1': {'id': 'builder-1', 'role': 'builder', 'item': 'ITEM-1', 'brief': relative,
                             'status': 'running', 'started_at': now}},
        fast_checks={'acme/app': {'unit': {'sha': head, 'exit': 0}}},
        watch={'clock_at': now, 'poll_at': now, 'measured_at': now, 'prs': {HEAD_REF: {}},
               'actions': {}}), tmp_path, reserved=False)
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
        'Stop': ('Stop', {'session_id': 'planner', 'cwd': str(tmp_path)}),
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


@pytest.mark.parametrize('path', ['Stop', 'SubagentStop', 'SessionStart', 'commit', 'push'])
def test_workspace_hook_latency(seeded_workspace, capsys, path):
    from resource import RUSAGE_CHILDREN, getrusage
    from statistics import quantiles
    from time import perf_counter

    plugin, payloads, reset, calls = seeded_workspace
    event, fields = payloads[path]
    payload = json.dumps({**fixture(event), **fields})
    runs = 60 if os.environ.get('WUWEI_BENCH') == '1' else 20
    elapsed, cpu = [], []
    for _ in range(runs):
        reset()
        before = getrusage(RUSAGE_CHILDREN)
        start = perf_counter()
        result = subprocess_replay(plugin, event, payload)
        elapsed.append(perf_counter() - start)
        after = getrusage(RUSAGE_CHILDREN)
        cpu.append(after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime)
        assert result.returncode == 0, result.stderr
        if event != 'SessionStart':
            assert result.stdout == '', result.stdout
    assert not calls.exists(), calls.read_text()
    cpu_ms = quantiles(cpu, n=100)[94] * 1000
    wall_ms = quantiles(elapsed, n=100)[94] * 1000
    assert_latency_budget(f'{path} in a workspace', cpu_ms, wall_ms, capsys,
                          wall_budget=100, runs=runs)


@pytest.mark.parametrize('session_id, recorded', [('wuwei-heartbeat', 0), ('a-session', 1)])
def test_heartbeat_refusals_are_not_recorded(plugin, session_id, recorded):
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


def test_no_hook_path_imports_heartbeat():
    import ast
    paths = [*(ROOT / 'cli/wuwei/guards').glob('*.py'), ROOT / 'cli/wuwei/commands/hook.py']
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([alias.name for alias in node.names] if isinstance(node, (ast.Import, ast.ImportFrom)) else [])
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or '')
            assert not any('heartbeat' in name for name in names), path


def test_heartbeat_latency(seeded_workspace, capsys, monkeypatch, quiet_heartbeat):
    from resource import RUSAGE_CHILDREN, RUSAGE_SELF, getrusage
    from statistics import quantiles
    from time import perf_counter
    from wuwei import heartbeat, integrity, registry

    from fakes.integrity import seed
    (root, env), _, reset, calls = seeded_workspace
    seed(root.parent)  # after the fixture signed the copy, so the verdict is fresh
    monkeypatch.setenv('PATH', env['PATH'])
    monkeypatch.setattr(integrity, 'PLUGIN', root)
    module = registry.watch_service()
    module.LAUNCHER = root / 'bin/wuwei'
    monkeypatch.setattr(registry, 'watch_service', lambda: module)
    monkeypatch.setattr(heartbeat, 'beat', quiet_heartbeat)  # the real beat, ping off
    runs = 60 if os.environ.get('WUWEI_BENCH') == '1' else 20
    elapsed, cpu = [], []
    for _ in range(runs):
        reset()
        before = [getrusage(who) for who in (RUSAGE_SELF, RUSAGE_CHILDREN)]
        start = perf_counter()
        heartbeat.beat(root.parent)
        elapsed.append(perf_counter() - start)
        after = [getrusage(who) for who in (RUSAGE_SELF, RUSAGE_CHILDREN)]
        cpu.append(sum(a.ru_utime - b.ru_utime + a.ru_stime - b.ru_stime for a, b in zip(after, before)))
    assert not calls.exists(), calls.read_text()
    cpu_ms = quantiles(cpu, n=100)[94] * 1000
    wall_ms = quantiles(elapsed, n=100)[94] * 1000
    assert_latency_budget('heartbeat tick', cpu_ms, wall_ms, capsys, wall_budget=200, runs=runs)


def test_seat_question_without_record_blocks_subagent_stop(subprocess_plugin, tmp_path):
    payload = json.loads((ROOT / 'tests/payloads/SubagentStop/example.json').read_text())
    payload.update(cwd=str(tmp_path), agent_type='wuwei:builder',
                   agent_transcript_path=str(tmp_path / 'missing.jsonl'),
                   last_assistant_message='Should I add a cache?\nBlocked: none\nGap: none\nChange: none')
    result = subprocess_replay(subprocess_plugin, 'SubagentStop', json.dumps(payload))
    assert result.returncode == 2, result.stderr
    output = json.loads(result.stdout)
    assert output['decision'] == 'block' and 'Cite a decision D-n' in output['reason']


def shadow_mode(plugin, mode='shadow'):
    (plugin[0] / '.wuwei/config.toml').write_text(f'[guards]\nmode = "{mode}"\n')


def set_posture(plugin, raw):
    (plugin[0] / '.wuwei/config.toml').write_text(raw)


def warns(plugin, name='fake', area='publish'):
    """Give a stub guard module an area so the posture can relax it (#331)."""
    import wuwei.guards
    plugin[1].setitem(wuwei.guards.AREAS, name, area)


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


@pytest.mark.parametrize('event', ['PreToolUse', 'PostToolUse', 'Stop'])
def test_shadow_mode_records_and_allows(plugin, event):
    shadow_mode(plugin)
    warns(plugin)
    install(plugin, refusing(event))
    payload = (json.loads((ROOT / 'tests/payloads/PreToolUse/bash.json').read_text())
               if event == 'PreToolUse' else fixture(event))
    result = replay(plugin, event, json.dumps(payload))
    assert (result.returncode, result.stdout) == (0, ''), result.stderr
    recorded, = events_of(plugin, 'guard.would_refuse')
    assert recorded['guard'] == 'fake' and recorded['reason'] == 'guard reason'
    assert (recorded['area'], recorded['level'], recorded['posture']) == ('publish', 'warn', 'observe')
    assert recorded['session'] == payload['session_id'] and recorded['item'] is None
    if event == 'PreToolUse':
        assert recorded['target'] == 'npm test'
    assert events_of(plugin, 'hook.refusal') == []


def test_shadow_mode_does_not_shadow_the_heartbeat(plugin):
    shadow_mode(plugin)
    warns(plugin)
    install(plugin, refusing('PreToolUse'))
    payload = {**fixture('PreToolUse'), 'session_id': 'wuwei-heartbeat'}
    assert_refusal(replay(plugin, 'PreToolUse', json.dumps(payload)), 'PreToolUse', 'guard reason')
    assert events_of(plugin, 'guard.would_refuse') == []


def test_shadow_mode_enforces_when_it_cannot_record(plugin):
    from wuwei import state
    shadow_mode(plugin)
    warns(plugin)
    install(plugin, refusing('PreToolUse'))
    plugin[1].setattr(state, 'append_event', lambda *a, **k: (_ for _ in ()).throw(OSError('disk')))
    result = replay(plugin, 'PreToolUse', json.dumps(fixture('PreToolUse')))
    assert result.returncode == 2
    assert json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert 'could not record shadow refusal' in result.stderr


@pytest.mark.parametrize('raw', [None, '[guards]\nmode = "enforce"\n', '[security]\nposture = "strict"\n',
                                 '[security]\nposture = "observe"\n'])
def test_enforce_mode_refuses_as_before(plugin, raw):
    # A guard module with no area (a stub) blocks with no posture line in every posture.
    if raw:
        set_posture(plugin, raw)
    install(plugin, refusing('PreToolUse'))
    assert_refusal(replay(plugin, 'PreToolUse', json.dumps(fixture('PreToolUse'))),
                   'PreToolUse', 'guard reason')
    assert events_of(plugin, 'guard.would_refuse') == []


@pytest.mark.parametrize('command,target', [
    ("sh -c 'git push --force origin main'", 'git push --force origin main'),
    ('echo $(', 'echo $('),
])
def test_shadow_target_is_the_normalised_command(plugin, command, target):
    shadow_mode(plugin)
    warns(plugin)
    install(plugin, refusing('PreToolUse'))
    payload = {**fixture('PreToolUse'), 'tool_name': 'Bash', 'tool_input': {'command': command}}
    assert replay(plugin, 'PreToolUse', json.dumps(payload)).returncode == 0
    assert events_of(plugin, 'guard.would_refuse')[0]['target'] == target


def test_shadow_target_is_redacted(plugin):
    from wuwei import report, security, workspace
    security.initialize(plugin[0] / '.wuwei')
    canary = json.loads((plugin[0] / '.wuwei/security.json').read_text())['canary']
    shadow_mode(plugin)
    warns(plugin)
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


def test_posture_levels_at_the_hook(plugin):
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    set_posture(plugin, '[security]\nposture = "observe"\n')
    owner = 'posture: publish = block (owner-only action; no setting lowers it)'
    blocked = {'protect_state': 'posture: records = block (floor; no setting lowers it)',
               'deploy': owner, 'pr': owner}
    try:
        for name, line in blocked.items():
            forget_guards()
            install(plugin, refusing('PreToolUse', 'kept'), name)
            assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', f'kept\n{line}')
            assert events_of(plugin, 'guard.would_refuse') == []
            assert events_of(plugin, 'hook.refusal')[-1]['refusals'] == [{'guard': name, 'reason': 'kept'}]
            (plugin[0] / f'cli/wuwei/guards/{name}.py').unlink()
        for name in ('commit_push', 'integrity'):
            forget_guards()
            install(plugin, refusing('PreToolUse', 'kept'), name)
            result = replay(plugin, 'PreToolUse', payload)
            assert (result.returncode, result.stdout, result.stderr) == (0, '', '')
            (plugin[0] / f'cli/wuwei/guards/{name}.py').unlink()
        assert [(row['guard'], row['area'], row['level'], row['posture'])
                for row in events_of(plugin, 'guard.would_refuse')] == [
            ('commit_push', 'publish', 'warn', 'observe'), ('integrity', 'integrity', 'warn', 'observe')]
        forget_guards()
        install(plugin, refusing('PreToolUse', 'kept'), 'commit_push')
        set_posture(plugin, '[security]\nposture = "strict"\n')
        assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse',
                       'kept\nposture: publish = block (set security.areas.publish)')
        set_posture(plugin, '[security]\nposture = "strict"\n[security.areas]\npublish = "off"\n')
        result = replay(plugin, 'PreToolUse', payload)
        assert (result.returncode, result.stdout, result.stderr) == (0, '', '')
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
        {'reason': FORCE, 'refusals': [{'guard': 'fake', 'reason': FORCE}], 'target': 'npm test'}]
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
        {'reason': FORCE, 'refusals': [{'guard': 'fake', 'reason': FORCE}]}]


def test_refusal_from_two_guards_lists_both_in_order(plugin):
    install(plugin, refusing('PreToolUse', 'first; a'), 'first')
    install(plugin, refusing('PreToolUse', 'second'), 'second')
    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    assert_refusal(replay(plugin, 'PreToolUse', payload), 'PreToolUse', 'first; a\nsecond')
    recorded, = events_of(plugin, 'hook.refusal')
    assert recorded['reason'] == 'first; a\nsecond'
    assert recorded['refusals'] == [{'guard': 'first', 'reason': 'first; a'},
                                    {'guard': 'second', 'reason': 'second'}]
