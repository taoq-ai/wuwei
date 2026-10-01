"""Runtime dispatch contracts and Codex workspace refusal."""

import importlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


def setup(tmp_path, monkeypatch, runtime='codex'):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[adapters]\nruntime = "' + runtime + '"\n[codex]\ncommand = ["fake-companion"]\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    return tmp_path


def companion_payloads(root):
    fixture = Path(__file__).parent / 'fixtures/runtime/codex-companion.json'
    return json.loads(fixture.read_text().replace('WORKTREE', str(root)))


def test_claude_returns_plugin_agent_type(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch, 'claude')
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.claude')
    result = adapter.dispatch('builder', str(brief), str(root), True, root=root)
    assert result.exit == 0
    assert result.data['agent_type'].endswith(':builder')
    assert result.data['brief_path'] == str(brief)


def test_codex_wrong_root_cancels(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    calls = []

    payloads = companion_payloads(root)
    payloads['status']['workspaceRoot'] = str(root / 'other')

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert argv[-1] == '--json'
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]] if argv[1] != 'cancel' else {}), stderr='')

    monkeypatch.setattr(adapter.subprocess, 'run', run)
    result = adapter.dispatch('builder', str(brief), str(root), True, root=root)
    assert result.exit == 1 and 'workspace' in result.reason
    assert 'cancel' in calls[-1][0]
    assert calls[-1][1]['cwd'] == str(root)


def test_codex_matches_then_polls_and_validates_result(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[-1] == '--json'
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]]), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    job = adapter.dispatch('builder', str(brief), str(root), True, root=root).data
    payloads['status']['job']['status'] = 'running'
    assert adapter.status(job, root=root).data['status'] == 'running'
    payloads['status']['job']['status'] = 'completed'
    assert adapter.status(job, root=root).data['status'] == 'completed'
    result = adapter.result(job, root=root)
    assert result.exit == 0 and result.data['text'].startswith('Blocked: none')
    assert 'usage' not in result.data


def test_codex_result_preserves_stored_usage(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    usage = {'input_tokens': 17, 'output_tokens': 9, 'cost': 0.04,
             'model': 'codex-test', 'duration': 2.5}
    payloads['result']['storedJob']['result']['usage'] = usage
    monkeypatch.setattr(adapter.subprocess, 'run', lambda argv, **kw:
                        SimpleNamespace(returncode=0, stdout=json.dumps(payloads['result']), stderr=''))
    result = adapter.result({'id': 'j1', 'worktree': str(root)}, root=root)
    assert result.exit == 0
    assert result.data['usage'] == usage


def test_codex_rejects_conflicting_nested_workspace_root(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    payloads['status']['job']['workspaceRoot'] = str(root / 'other')
    calls = []
    def run(argv, **kwargs):
        calls.append(argv[1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads.get(argv[1], {})), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    result = adapter.dispatch('builder', str(brief), str(root), True, root=root)
    assert result.exit == 1
    assert calls == ['task', 'status', 'cancel']


def test_codex_error_body_is_unrun(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    monkeypatch.setattr(adapter.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='{"error":"no job"}', stderr=''))
    result = adapter.status({'id': 'j1', 'worktree': str(root)}, root=root)
    assert result.exit == 2 and 'no job' in result.reason


def test_codex_result_captures_retro_outside_workspace_tree(tmp_path, monkeypatch):
    (tmp_path / 'workspace').mkdir()
    root = setup(tmp_path / 'workspace', monkeypatch)
    tree = tmp_path / 'tree'
    tree.mkdir()
    adapter = importlib.import_module('adapters.runtime.codex')
    monkeypatch.setattr(adapter, '_call', lambda *args, **kwargs: adapter.registry.Result(
        0, companion_payloads(tree)['result']))
    result = adapter.result({'id': 'j1', 'worktree': str(tree), 'role': 'builder'}, root=root)
    assert result.exit == 0
    event = json.loads((root / '.wuwei/days/2026-09-28/events.jsonl').read_text().splitlines()[0])
    assert event['kind'] == 'retro.captured'


def test_codex_result_lints_verdict(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    verdict = root / '.wuwei/days/2026-09-28/decisions/gate-goal.md'
    verdict.parent.mkdir(parents=True)
    verdict.write_text('Verdict: PASS\n')
    adapter = importlib.import_module('adapters.runtime.codex')
    monkeypatch.setattr(adapter, '_call', lambda *args, **kwargs: adapter.registry.Result(
        0, companion_payloads(root)['result']))
    result = adapter.result({'id': 'j1', 'worktree': str(root), 'role': 'sentinel-goal', 'started_at': 0}, root=root)
    assert result.exit == 1
    assert 'REJECT' in result.reason


def test_codex_rejects_role_path_traversal(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    result = adapter.dispatch('../README', str(brief), str(root), True, root=root)
    assert result.exit == 1


SID = '0f8fad5b-d9cb-469f-a165-70867728950e'


def headless_case(tmp_path, monkeypatch, payload=None, returncode=0, raises=None):
    root = setup(tmp_path, monkeypatch, 'claude')
    adapter = importlib.import_module('adapters.runtime.claude')
    calls = []
    payload = {'session_id': SID, 'result': 'done', 'is_error': False,
               'permission_denials': [{'tool_name': 'Bash', 'tool_use_id': 'x', 'tool_input': {}}]
               } if payload is None else payload

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if raises:
            raise raises
        return SimpleNamespace(returncode=returncode, stderr='boom secret',
                               stdout=payload if isinstance(payload, str) else json.dumps(payload))
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    return root, adapter, calls


def test_claude_headless_starts_a_session(tmp_path, monkeypatch):
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'xoxb-secret')
    root, adapter, calls = headless_case(tmp_path, monkeypatch)
    result = adapter.headless('plan the day', None, ['Read', 'Glob'], root=root)
    assert result.exit == 0
    assert result.data == {'session_id': SID, 'result': 'done', 'denials': ['Bash']}
    [(argv, kwargs)] = calls
    assert argv == ['claude', '-p', '--output-format', 'json', '--permission-mode', 'dontAsk',
                    '--tools', 'Read,Glob', '--allowedTools', 'Read,Glob', '--strict-mcp-config']
    assert kwargs['input'] == 'plan the day'
    assert kwargs['cwd'] == str(root)
    assert 'SLACK_BOT_TOKEN' not in kwargs['env']


def test_claude_headless_resumes_the_same_session(tmp_path, monkeypatch):
    root, adapter, calls = headless_case(tmp_path, monkeypatch)
    assert adapter.headless('Decision D-1: option B.', SID, ['Read'], root=root).exit == 0
    assert calls[0][0][-3:] == ['--strict-mcp-config', '--resume', SID]
    assert '--mcp-config' not in calls[0][0]
    other = SID.replace('0f8f', '1f8f')
    assert adapter.headless('Decision D-1: option B.', other, ['Read'], root=root).exit == 2


@pytest.mark.parametrize('payload, returncode', [
    ({'session_id': SID, 'result': 'x', 'is_error': True, 'permission_denials': []}, 0),
    ({'session_id': SID, 'result': 'x', 'is_error': False, 'permission_denials': []}, 1),
])
def test_claude_headless_error_run_keeps_data(tmp_path, monkeypatch, payload, returncode):
    root, adapter, _ = headless_case(tmp_path, monkeypatch, payload, returncode)
    result = adapter.headless('p', None, ['Read'], root=root)
    assert result.exit == 1 and result.data['session_id'] == SID


@pytest.mark.parametrize('payload, raises', [
    ('not json secret', None),
    ({'result': 'x', 'is_error': False, 'permission_denials': []}, None),
    ({'session_id': 'abc', 'result': 'x', 'is_error': False, 'permission_denials': []}, None),
    ({'session_id': SID, 'result': 'x', 'is_error': False, 'permission_denials': [{'tool_name': 3}]}, None),
    (None, subprocess.TimeoutExpired('claude', 1800)),
    (None, FileNotFoundError('claude')),
])
def test_claude_headless_fails_closed(tmp_path, monkeypatch, payload, raises):
    root, adapter, _ = headless_case(tmp_path, monkeypatch, payload, raises=raises)
    result = adapter.headless('p', None, ['Read'], root=root)
    assert result.exit == 2 and 'secret' not in result.reason and result.reason


@pytest.mark.parametrize('prompt, session, tools', [
    ('', None, ['Read']), ('p', 'not-a-uuid', ['Read']), ('p', None, ['Read Write']),
    ('p', None, ['Read,Bash']), ('p', None, []),
])
def test_claude_headless_refuses_invalid_calls(tmp_path, monkeypatch, prompt, session, tools):
    root, adapter, calls = headless_case(tmp_path, monkeypatch)
    assert adapter.headless(prompt, session, tools, root=root).exit == 2
    assert calls == []


def test_claude_headless_passes_seat_variables(tmp_path, monkeypatch):
    root, adapter, calls = headless_case(tmp_path, monkeypatch)
    assert adapter.headless('p', None, ['Read'], root=root, variables={'WUWEI_SEAT_ROLE': 'shepherd'}).exit == 0
    assert calls[0][1]['env']['WUWEI_SEAT_ROLE'] == 'shepherd'
    for bad in ({'PATH': 'x'}, {'WUWEI_SEAT_ROLE': 1}, ['WUWEI_SEAT_ROLE']):
        assert adapter.headless('p', None, ['Read'], root=root, variables=bad).exit == 2
    assert len(calls) == 1
