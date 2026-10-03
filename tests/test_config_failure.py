"""Issue 326: a config.toml that does not load can be read and fixed from the session."""

import io
import json
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei import workspace

ROOT = Path(__file__).resolve().parents[1]
BROKEN = 'cap = 1\nrepos = []\n[[repos]]\nname = "example/app"\npath = "app"\ndefault_branch = "main"\n'
HINT = 'repos is assigned on line 2; delete that line before using [[repos]] tables'
TABLE = '\n[[repos]]\nname = "example/app"\npath = "app"\ndefault_branch = "main"\n'


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from fakes.integrity import seed
    root = tmp_path / 'ws'
    (root / '.wuwei/charters').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text(BROKEN)
    (root / '.wuwei/charters/builder.md').write_text('# Builder\n')
    seed(root)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    return root


def replay(monkeypatch, capsys, root, event, tool=None, inputs=None, cwd=None):
    from wuwei.commands import hook
    payload = {'session_id': 'test', 'transcript_path': str(root / 'transcript.jsonl'),
               'cwd': str(cwd or root), 'hook_event_name': event}
    if event == 'PreToolUse':
        payload.update(tool_name=tool, tool_input=inputs or {})
    else:
        payload['stop_hook_active'] = False
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    code = hook.run(SimpleNamespace(event=event))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_load_config_names_the_repos_line(ws):
    with pytest.raises(workspace.ConfigError) as caught:
        workspace.load_config(ws)
    assert str(caught.value).startswith("config.toml: Cannot mutate immutable namespace ('repos',)")
    assert HINT in str(caught.value)


def test_config_check_prints_the_fix(ws, monkeypatch, capsys):
    from wuwei.commands import config
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    assert config.run(SimpleNamespace()) == 1
    assert HINT in capsys.readouterr().err


def test_other_config_errors_have_no_repos_hint(ws):
    (ws / '.wuwei/config.toml').write_text('nonsense = 1\n')
    with pytest.raises(workspace.ConfigError) as caught:
        workspace.load_config(ws)
    assert 'unknown key nonsense' in str(caught.value)
    assert 'repos is assigned' not in str(caught.value)


def test_template_has_no_repos_key_and_takes_tables(ws):
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    assert 'repos' not in tomllib.loads(template)
    (ws / '.wuwei/config.toml').write_text(template + TABLE)
    assert workspace.load_config(ws)['repos'][0]['name'] == 'example/app'


@pytest.mark.parametrize('tool,inputs', [
    ('Read', {'file_path': 'ABS'}),
    ('Read', {'file_path': '.wuwei/charters/builder.md'}),
    ('Grep', {'pattern': 'repos', 'path': '.wuwei/config.toml'}),
    ('Glob', {'pattern': '*.md', 'path': '.wuwei/charters'}),
    ('ToolSearch', {'query': 'select:Read'}),
])
def test_repair_reads_pass(ws, monkeypatch, capsys, tool, inputs):
    if inputs.get('file_path') == 'ABS':
        inputs = {'file_path': str(ws / '.wuwei/config.toml')}
    code, out, _ = replay(monkeypatch, capsys, ws, 'PreToolUse', tool, inputs)
    assert (code, out) == (0, '')


def deny_reason(out):
    return json.loads(out)['hookSpecificOutput']['permissionDecisionReason']


def test_bash_is_refused_with_one_reason_and_recorded(ws, monkeypatch, capsys):
    code, out, _ = replay(monkeypatch, capsys, ws, 'PreToolUse', 'Bash', {'command': 'ls'})
    reason = deny_reason(out)
    assert code == 2 and reason.startswith('config.toml:') and HINT in reason
    assert 'outward:' not in reason
    events = (workspace.day_dir(ws) / 'events.jsonl').read_text().splitlines()
    refusals = [json.loads(line) for line in events if json.loads(line)['kind'] == 'hook.refusal']
    assert refusals[-1]['payload']['reason'] == reason


@pytest.mark.parametrize('tool,inputs', [
    ('Write', {'file_path': '.wuwei/config.toml', 'content': 'cap = 1\n'}),
    ('Read', {'file_path': 'notes.md'}),
    ('Grep', {'pattern': 'repos'}),
    ('Agent', {'prompt': 'go'}),
    ('mcp__example__send_message', {'text': 'hi'}),
])
def test_everything_else_is_refused(ws, monkeypatch, capsys, tool, inputs):
    code, out, _ = replay(monkeypatch, capsys, ws, 'PreToolUse', tool, inputs)
    reason = deny_reason(out)
    assert code == 2 and reason.startswith('config.toml:') and HINT in reason


def test_outside_cwd_reads_the_config_and_runs_unrelated_bash(ws, tmp_path, monkeypatch, capsys):
    outside = tmp_path / 'outside'
    outside.mkdir()
    code, _, _ = replay(monkeypatch, capsys, ws, 'PreToolUse', 'Read',
                        {'file_path': str(ws / '.wuwei/config.toml')}, cwd=outside)
    assert code == 0
    code, _, _ = replay(monkeypatch, capsys, ws, 'PreToolUse', 'Bash', {'command': 'ls'}, cwd=outside)
    assert code == 0


def test_stop_prints_the_error_once_and_ends_the_turn(ws, monkeypatch, capsys):
    code, out, err = replay(monkeypatch, capsys, ws, 'Stop')
    assert (code, out) == (0, '')
    assert HINT in err and err.count('config.toml:') == 1
