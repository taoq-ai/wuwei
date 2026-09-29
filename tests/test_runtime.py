"""Runtime dispatch contracts and Codex workspace refusal."""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace


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
