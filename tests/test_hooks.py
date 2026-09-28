"""Hook tables run in-process; fixture replays exercise the executable shim."""

import io
import json
import os
import re
from pathlib import Path
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
    for directory in ('cli', 'bin', '.claude-plugin'):
        shutil.copytree(ROOT / directory, root / directory)
    path = tmp_path / 'path'
    path.mkdir()
    (path / 'python3').symlink_to(sys.executable)
    return root, {**os.environ, 'PATH': str(path) + os.pathsep + os.environ['PATH'],
                  'PYTHONPATH': '/unused/inherited/path'}


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
    path = tmp_path / 'cli/wuwei/guards'
    path.mkdir(parents=True)
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
    assert type(discover()) is list
    assert discover() == []


def test_private_guard_module_is_ignored(plugin):
    install(plugin, 'raise RuntimeError("private helper imported")', '_helper')
    result = replay(plugin, 'Stop', json.dumps(fixture('Stop')))
    assert result.returncode == 0, result.stderr


def assert_refusal(result, event, reason, *, malformed=False):
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
    if code:
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


def test_hook_latency(subprocess_plugin, capsys):
    from resource import RUSAGE_CHILDREN, getrusage
    from statistics import quantiles
    from time import perf_counter

    payload = (ROOT / 'tests/payloads/PreToolUse/bash.json').read_text()
    elapsed = []
    cpu = []
    for _ in range(60):
        before = getrusage(RUSAGE_CHILDREN)
        start = perf_counter()
        result = subprocess_replay(subprocess_plugin, 'PreToolUse', payload)
        elapsed.append(perf_counter() - start)
        after = getrusage(RUSAGE_CHILDREN)
        cpu.append(after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime)
        assert result.returncode == 0, result.stderr
    cpu_ms = quantiles(cpu, n=100)[94] * 1000
    wall_ms = quantiles(elapsed, n=100)[94] * 1000
    with capsys.disabled():
        print(f'\nHook p95 over 60 runs: CPU {cpu_ms:.2f} ms, wall {wall_ms:.2f} ms')
    if 'CI' not in os.environ:
        assert cpu_ms < 50


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
