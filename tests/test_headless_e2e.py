"""Offline checks for the opt-in paid integration runner."""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / 'scripts' / (name + '.py')
    assert path.is_file(), f'{name} is not implemented'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_no_key_skips_before_any_external_call(monkeypatch, capsys):
    runner = load('headless_e2e')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr(runner, 'exercise', lambda *a, **kw: pytest.fail('must skip'))
    assert runner.main([]) == 0
    assert 'ANTHROPIC_API_KEY is not set; skipping headless e2e' in capsys.readouterr().out


@pytest.mark.parametrize('message', [
    'OAuth token has expired. Please obtain a new token or refresh your existing token.',
    'Your OAuth session has expired. Please run /login.',
])
def test_expired_oauth_is_unmeasured_even_when_claude_exits_zero(message, capsys, monkeypatch):
    runner = load('headless_e2e')
    def exercise(*args, **kwargs):
        runner.check_result(SimpleNamespace(returncode=0, stderr='', stdout=json.dumps(
            {'type': 'result', 'is_error': True, 'result': message})))
    monkeypatch.setattr(runner, 'exercise', exercise)
    assert runner.main(['--local-login']) == 2
    output = capsys.readouterr().out
    assert 'unmeasured' in output and 'expired OAuth' in output and 'claude auth login' in output


@pytest.mark.parametrize('output,code', [
    ('not json', 0), ('{}', 0), ('[]', 0),
    ('{"type":"result","is_error":true,"result":"invalid API key"}', 1),
    ('{"type":"result","is_error":false,"subtype":"error_max_turns"}', 0),
    ('{"type":"result","is_error":false,"subtype":"error_max_budget_usd"}', 0),
])
def test_bad_runtime_results_are_unmeasured(output, code):
    runner = load('headless_e2e')
    with pytest.raises(RuntimeError, match='unmeasured'):
        runner.check_result(SimpleNamespace(returncode=code, stdout=output, stderr=''))


def evidence():
    names = ['builder', 'sentinel-arch', 'sentinel-quality', 'sentinel-security', 'steward']
    state = {'gate_approved': True, 'approved_items': ['A'], 'close_requested': True,
             'builds': {'A': {'status': 'done'}}, 'items': {'A': {'phase': 'parked'}},
             'seats': {n: {'role': n, 'item': 'A', 'status': 'stopped'} for n in names}}
    events = [{'kind': 'plan.approved', 'payload': {}}]
    events += [{'kind': k, 'payload': {'name': 'builder', 'item': 'A'}}
               for k in ('seat launched', 'seat stopped', 'seat.usage', 'build.checked')]
    events += [{'kind': 'gate.received', 'payload': {'item': 'A', 'role': r,
                'round': 'initial', 'verdict': 'PASS'}} for r in ('arch', 'quality', 'security')]
    events += [{'kind': 'retro.captured', 'payload': {}},
               {'kind': 'day.close_requested', 'payload': {}}]
    hooks = [{'event': e, 'exit': code, 'tool': tool, 'input': inputs}
             for e, code, tool, inputs in [
                 ('SessionStart', 0, '', {}),
                 ('PreToolUse', 2, 'Agent', {'description': 'headless refusal probe'}),
                 ('PreToolUse', 0, 'Agent', {'subagent_type': 'wuwei:builder'}),
                 ('PostToolUse', 0, 'Skill', {'skill': 'wuwei:wuwei-plan'}),
                 ('SubagentStop', 0, '', {}), ('Stop', 2, '', {}), ('Stop', 0, '', {})]]
    state['planner_session_id'] = 'planner'
    action = {'action': 'launch', 'agent_type': 'wuwei:builder',
              'prompt': 'WUWEI brief: .wuwei/days/2026-09-29/briefs/builder.md\nRead instructions.'}
    hooks.insert(2, {'event': 'cli', 'args': ['build', 'next', 'A'], 'exit': 0, 'result': action})
    for row in hooks:
        if row.get('tool') == 'Agent' and row['exit'] == 0:
            row['input']['prompt'] = action['prompt']
        if row['event'] == 'SubagentStop':
            row['agent_type'] = 'wuwei:builder'
        if row['event'] == 'Stop':
            row['session'] = 'planner'
    for role in names[1:]:
        hooks.insert(-1, {'event': 'PreToolUse', 'exit': 0, 'tool': 'Agent',
                         'input': {'subagent_type': 'wuwei:' + role}})
        hooks.insert(-1, {'event': 'SubagentStop', 'exit': 0, 'agent_type': 'wuwei:' + role})
    hooks.insert(-1, {'event': 'cli', 'args': ['close'], 'exit': 0})
    return state, events, hooks


def test_complete_structured_evidence_passes():
    assert load('headless_e2e').validate(*evidence()) == []


@pytest.mark.parametrize('mutation', [
    'no-launch', 'no-stop', 'no-skill', 'no-hooks', 'no-block', 'no-close',
    'no-gate', 'live-seat', 'incomplete-build', 'unapproved',
])
def test_missing_contract_evidence_fails_despite_success_prose(mutation):
    runner = load('headless_e2e')
    data, events, hooks = evidence()
    if mutation == 'no-launch':
        events = [e for e in events if e['kind'] != 'seat launched']
    elif mutation == 'no-stop':
        hooks = [h for h in hooks if h['event'] != 'SubagentStop']
    elif mutation == 'no-skill':
        hooks = [h for h in hooks if h.get('tool') != 'Skill']
    elif mutation == 'no-hooks':
        hooks = []
    elif mutation == 'no-block':
        hooks = [h for h in hooks if h['exit'] != 2]
    elif mutation == 'no-close':
        data['close_requested'] = False
    elif mutation == 'no-gate':
        events = [e for e in events if e['payload'].get('role') != 'security']
    elif mutation == 'live-seat':
        data['seats']['builder']['status'] = 'running'
    elif mutation == 'incomplete-build':
        data['builds']['A']['status'] = 'running'
    else:
        data['gate_approved'] = False
    assert runner.validate(data, events, hooks)


def test_adapter_timeout_and_missing_binary_are_unmeasured(tmp_path):
    adapter = load('headless_adapter')
    with pytest.raises(RuntimeError, match='timeout'):
        adapter.run([sys.executable, '-c', 'import time; time.sleep(5)'], cwd=tmp_path, timeout=.02)
    with pytest.raises(RuntimeError, match='unmeasured'):
        adapter.run(['claude'], cwd=tmp_path, env={'PATH': str(tmp_path)})


def test_claude_argv_is_bounded_and_isolated(tmp_path):
    adapter = load('headless_adapter')
    argv = adapter.claude_command(tmp_path / 'plugin')
    assert argv[0] == 'claude'
    for flag, value in [('--max-turns', '48'), ('--max-budget-usd', '3'),
                        ('--output-format', 'json'), ('--setting-sources', 'project')]:
        assert argv[argv.index(flag) + 1] == value
    assert '-p' in argv and '--plugin-dir' in argv
    assert '--strict-mcp-config' in argv


def test_scratch_build_and_observer_preserve_hook_results(tmp_path, monkeypatch):
    runner = load('headless_e2e')
    adapter = load('headless_adapter')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path / 'wrong-workspace'))
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / 'wrong-config'))
    monkeypatch.setenv('SYSTEMROOT', str(tmp_path / 'unused-windows-root'))
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    root, plugin, env = runner.prepare(tmp_path)
    assert env['HOME'] == str(tmp_path / 'home')
    assert env['WUWEI_WORKSPACE'] == str(root)
    assert 'CLAUDE_CONFIG_DIR' not in env
    assert 'SYSTEMROOT' not in env
    assert (plugin / 'MANIFEST.sha256.sig').is_file()
    assert (plugin / 'hooks/hooks.json').read_bytes() == (ROOT / 'hooks/hooks.json').read_bytes()
    assert (plugin / 'bin/wuwei').read_bytes() == (ROOT / 'bin/wuwei').read_bytes()
    cli = plugin / 'bin/wuwei'
    assert adapter.run([cli, 'integrity', 'check'], cwd=root, env=env).returncode == 0
    payload = {'session_id': 'fixture', 'transcript_path': str(root / 'transcript.jsonl'),
               'cwd': str(root), 'hook_event_name': 'PreToolUse',
               'tool_name': 'Write', 'tool_input': {'file_path': str(root / '.wuwei/days' /
                    runner.DAY / 'state.json'), 'content': '{}'}}
    result = adapter.run([cli, 'hook', 'PreToolUse'], cwd=root, env=env, input=json.dumps(payload))
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'] == 'deny'
    row = json.loads((root / 'headless-hooks.jsonl').read_text().splitlines()[-1])
    assert row['event'] == 'PreToolUse' and row['exit'] == 2 and row['tool'] == 'Write'
    for args in (['plan', 'propose', 'proposal.json'],
                 ['plan', 'approve', '--items', 'A', '--goals-confirmed'],
                 ['brief', 'builder', 'A', 'builder', '--worktree', 'repo', '--file', '-']):
        step = adapter.run([cli, *args], cwd=root, env=env, input='Verify README presence.')
        assert step.returncode == 0, step.stderr
    step = adapter.run([cli, 'build', 'next', 'A'], cwd=root, env=env)
    assert step.returncode == 0, step.stderr
    assert json.loads(step.stdout)['action'] == 'launch'
    payload.update(cwd=str(tmp_path), tool_name='Bash', tool_input={'command': 'export X=1'})
    assert adapter.run([cli, 'hook', 'PreToolUse'], cwd=tmp_path, env=env,
                       input=json.dumps(payload)).returncode == 0


def test_paid_job_and_local_run_are_documented():
    workflow = (ROOT / '.github/workflows/tests.yml').read_text()
    assert '\n  headless-e2e:' in workflow
    job = workflow.split('\n  headless-e2e:', 1)[1]
    assert 'timeout-minutes: 8' in job
    assert 'secrets.ANTHROPIC_API_KEY' in job
    assert 'ANTHROPIC_API_KEY is not set; skipping headless e2e' in job
    assert "env.ANTHROPIC_API_KEY != '' && github.event_name == 'push'" in job
    assert 'python scripts/headless_e2e.py' in job
    docs = ROOT / 'docs/headless-e2e.md'
    assert docs.is_file()
    text = docs.read_text()
    for phrase in ('python3 scripts/headless_e2e.py --local-login', '--max-budget-usd',
                   '--max-turns', 'unmeasured', 'claude auth login'):
        assert phrase in text


@pytest.mark.parametrize('mutation', ['changed-prompt', 'no-build-next', 'wrong-stop-session',
                                     'no-close-exit', 'late-denial', 'wrong-builder-stop'])
def test_oracle_binds_launch_and_close_to_real_contract(mutation):
    runner = load('headless_e2e')
    data, events, hooks = evidence()
    if mutation == 'changed-prompt':
        for row in hooks:
            if row.get('tool') == 'Agent' and row['exit'] == 0:
                row['input']['prompt'] = 'Reconstructed instructions'
    elif mutation == 'no-build-next':
        hooks = [h for h in hooks if h.get('args') != ['build', 'next', 'A']]
    elif mutation == 'wrong-stop-session':
        for row in hooks:
            if row['event'] == 'Stop':
                row['session'] = 'unrelated'
    elif mutation == 'no-close-exit':
        hooks = [h for h in hooks if h.get('args') != ['close']]
    elif mutation == 'late-denial':
        hooks.append({'event': 'Stop', 'exit': 2, 'session': 'planner'})
    else:
        for row in hooks:
            if row['event'] == 'SubagentStop':
                row['agent_type'] = 'unrelated'
    assert runner.validate(data, events, hooks)


def test_wrong_evidence_shape_reports_unmeasured(monkeypatch, capsys):
    runner = load('headless_e2e')
    monkeypatch.setattr(runner, 'exercise', lambda **kw: runner.validate([], [], []))
    assert runner.main(['--local-login']) == 2
    assert 'unmeasured' in capsys.readouterr().out


def test_success_prose_is_not_an_authentication_signal():
    runner = load('headless_e2e')
    result = SimpleNamespace(returncode=0, stderr='', stdout=json.dumps({
        'type': 'result', 'subtype': 'success', 'is_error': False,
        'result': 'The expired OAuth case is covered by offline tests.'}))
    runner.check_result(result)


@pytest.mark.parametrize('raw', ['broken JSON', '[]'])
def test_observer_preserves_malformed_hook_exit(tmp_path, monkeypatch, capsys, raw):
    import io
    adapter = load('headless_adapter')
    monkeypatch.setattr(sys, 'stdin', io.StringIO(raw))
    monkeypatch.setattr(adapter, 'run', lambda *a, **kw: SimpleNamespace(
        returncode=2, stdout='denied\n', stderr='invalid payload\n'))
    argv = ['-I', '-P', '-c', 'run_module("wuwei")', 'cli', 'plugin', 'hook', 'PreToolUse']
    assert adapter.observe(sys.executable, tmp_path / 'hooks.jsonl', argv) == 2
    output = capsys.readouterr()
    assert output.out == 'denied\n' and output.err == 'invalid payload\n'
    assert json.loads((tmp_path / 'hooks.jsonl').read_text())['exit'] == 2
