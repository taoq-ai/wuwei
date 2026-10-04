"""Offline checks for the opt-in paid integration runner."""

import importlib.util
import json
import os
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
    assert runner.main([]) == 2
    assert 'headless e2e unmeasured: ANTHROPIC_API_KEY is not set' in capsys.readouterr().out


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
    events += [{'kind': 'spec.skipped', 'payload': {'item': 'A', 'reason': 'lead tier light'}},
               {'kind': 'retro.captured', 'payload': {}},
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
    'no-gate', 'live-seat', 'incomplete-build', 'unapproved', 'no-spec-skip',
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
    elif mutation == 'no-spec-skip':
        events = [e for e in events if e['kind'] != 'spec.skipped']
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
    assert '--resume' not in argv
    argv = adapter.claude_command(tmp_path / 'plugin', turns=150, budget=15, resume='s1')
    for flag, value in [('--max-turns', '150'), ('--max-budget-usd', '15'), ('--resume', 's1')]:
        assert argv[argv.index(flag) + 1] == value


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


def test_observer_reads_the_launcher_flags(tmp_path, monkeypatch):
    # The shim observes whatever interpreter flags bin/wuwei passes (#346 added -S).
    import io
    adapter = load('headless_adapter')
    monkeypatch.setattr(sys, 'stdin', io.StringIO('{}'))
    monkeypatch.setattr(adapter, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout='', stderr=''))
    flags = (ROOT / 'bin/wuwei').read_text().split('exec python3 ', 1)[1].split(' -c ', 1)[0].split()
    argv = [*flags, '-c', 'run_module("wuwei")', 'cli', 'plugin', 'hook', 'Stop']
    assert adapter.observe(sys.executable, tmp_path / 'hooks.jsonl', argv) == 0
    assert json.loads((tmp_path / 'hooks.jsonl').read_text())['args'] == ['hook', 'Stop']


KEYS = {'verdict', 'interventions', 'elapsed_seconds', 'cost_usd', 'refusals', 'findings', 'pr'}


def last_json(output):
    fields = json.loads(output.strip().splitlines()[-1])
    assert set(fields) == KEYS
    return fields


@pytest.mark.parametrize('missing,reason', [
    ('ANTHROPIC_API_KEY', 'ANTHROPIC_API_KEY'), ('WUWEI_REHEARSAL_REPO', 'WUWEI_REHEARSAL_REPO'),
    ('invalid-repo', 'WUWEI_REHEARSAL_REPO'), ('GH_TOKEN', 'GH_TOKEN'), ('tty', 'terminal')])
def test_rehearsal_preconditions_are_unmeasured_before_any_external_call(
        missing, reason, monkeypatch, capsys):
    runner = load('headless_e2e')
    env = {'ANTHROPIC_API_KEY': 'key', 'WUWEI_REHEARSAL_REPO': 'acme/rehearsal', 'GH_TOKEN': 'token'}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    if missing == 'invalid-repo':
        monkeypatch.setenv('WUWEI_REHEARSAL_REPO', 'not-a-repo')
    elif missing != 'tty':
        monkeypatch.delenv(missing)
    monkeypatch.setattr(runner, 'host_terminal', lambda: missing != 'tty')
    for name in ('exercise', 'prepare'):
        monkeypatch.setattr(runner, name, lambda *a, **kw: pytest.fail('must not run'))
    monkeypatch.setattr(runner.adapter, 'run', lambda *a, **kw: pytest.fail('must not run'))
    assert runner.main(['--rehearsal']) == 2
    output = capsys.readouterr().out
    assert output.startswith('rehearsal unmeasured: ') and reason in output.splitlines()[0]
    fields = last_json(output)
    assert fields['verdict'] == 'unmeasured' and fields['cost_usd'] is None


def rehearsal_evidence():
    data = {'items': {'A': {'phase': 'merged'}}, 'raised_prs': ['acme/rehearsal#1'],
            'close_requested': True,
            'seats': {'builder': {'status': 'stopped'}, 'quality': {'status': 'stopped'}}}
    events = [{'kind': 'gate.received', 'payload': {'item': 'A', 'role': 'quality', 'round': r,
               'verdict': v}} for r, v in (('initial', 'FIX'), ('delta', 'PASS'))]
    events += [{'kind': 'pr.raised', 'payload': {}},
               {'kind': 'decision.decided', 'payload': {'id': 'D-1', 'option': 'A'}},
               {'kind': 'merge.auto', 'payload': {}}]
    events += [{'kind': 'state.transition', 'payload': {'phase_changes': {'A': phase}}}
               for phase in ('implement', 'gate', 'fix', 'delta', 'raised', 'merged')]
    hooks = [{'event': 'cli', 'args': ['build', 'next', 'A'], 'exit': 0, 'result': {'action': 'continue'}}]
    return data, events, hooks


def test_complete_rehearsal_evidence_passes():
    assert load('headless_e2e').rehearsal_findings(*rehearsal_evidence()) == []


@pytest.mark.parametrize('mutation,step', [
    ('no-continue', 'continue'), ('fix-round-continue', 'continue'), ('no-fix', 'FIX'), ('no-delta', 'delta'), ('no-raise', 'pr'),
    ('no-decision', 'D-1'), ('no-merge', 'merge'), ('not-merged', 'merged'),
    ('no-close', 'close'), ('live-seat', 'seat'), ('manual', 'manual repair: state transition A fix')])
def test_missing_rehearsal_step_is_a_finding(mutation, step):
    runner = load('headless_e2e')
    data, events, hooks = rehearsal_evidence()
    if mutation == 'no-continue':
        hooks = []
    elif mutation == 'fix-round-continue':
        # The gate fix round also resumes the builder; only a continue before gates counts.
        hooks.insert(0, {'event': 'cli', 'args': ['dispatch', 'next', 'A'], 'exit': 0})
    elif mutation == 'no-fix':
        events = [e for e in events if e['payload'].get('verdict') != 'FIX']
    elif mutation == 'no-delta':
        events = [e for e in events if e['payload'].get('round') != 'delta']
    elif mutation == 'no-raise':
        events = [e for e in events if e['kind'] != 'pr.raised']
    elif mutation == 'no-decision':
        events = [e for e in events if e['kind'] != 'decision.decided']
    elif mutation == 'no-merge':
        events = [e for e in events if e['kind'] != 'merge.auto']
    elif mutation == 'not-merged':
        data['items']['A']['phase'] = 'raised'
    elif mutation == 'no-close':
        data['close_requested'] = False
    elif mutation == 'live-seat':
        data['seats']['builder']['status'] = 'running'
    else:
        hooks.append({'event': 'cli', 'args': ['state', 'transition', 'A', 'fix'], 'exit': 0})
    findings = runner.rehearsal_findings(data, events, hooks)
    assert any(step in finding for finding in findings), findings


def test_measure_counts_refusals_interventions_and_cost():
    runner = load('headless_e2e')
    events = [{'kind': 'hook.refusal', 'payload': {'reason': r}} for r in ('first', 'second')]
    hooks = [{'event': 'cli', 'args': ['merge', 'acme/rehearsal#1'], 'exit': 2},
             {'event': 'PreToolUse', 'args': ['hook', 'PreToolUse'], 'exit': 2},
             {'event': 'cli', 'args': ['state', 'set', 'x', '1'], 'exit': 0}]
    planned = ['decision outcome D-1 (planned, host terminal)']
    fields = runner.measure(events, hooks, [{'total_cost_usd': 1.5}, {'total_cost_usd': 2.25}], planned)
    assert fields['refusals'] == ['first', 'second', 'wuwei merge acme/rehearsal#1: exit 2']
    assert fields['interventions'] == [*planned, 'manual repair: state set x 1']
    assert fields['cost_usd'] == 3.75
    assert runner.measure(events, hooks, [{'total_cost_usd': 1.5}, {}], planned)['cost_usd'] is None


@pytest.mark.parametrize('verdict,code', [('pass', 0), ('fail', 1), ('unmeasured', 2)])
def test_report_exit_matches_verdict(verdict, code, capsys):
    runner = load('headless_e2e')
    fields = {'interventions': [], 'cost_usd': None, 'refusals': [], 'findings': [],
              'pr': None, 'elapsed_seconds': 3}
    assert runner.report(verdict, fields) == code
    output = capsys.readouterr().out
    assert output.startswith(f'rehearsal {verdict}: ') and 'cost unmeasured' in output
    assert last_json(output)['verdict'] == verdict


def bare_repository(tmp_path):
    import os
    import subprocess
    env = {'PATH': os.environ['PATH'], 'HOME': str(tmp_path), 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': os.devnull}
    source, bare = tmp_path / 'source-repo', tmp_path / 'remote.git'
    git = ['git', '-c', 'user.name=Owner', '-c', 'user.email=owner@example.test']
    subprocess.run([*git, 'init', '-q', '-b', 'main', source], check=True, env=env)
    (source / 'README.md').write_text('Rehearsal\n')
    subprocess.run([*git, '-C', source, 'add', 'README.md'], check=True, env=env)
    subprocess.run([*git, '-C', source, 'commit', '-q', '-m', 'init'], check=True, env=env)
    subprocess.run([*git, 'clone', '-q', '--bare', source, bare], check=True, env=env)
    return bare


def test_rehearsal_fixture_targets_the_test_repository(tmp_path, monkeypatch):
    import subprocess
    runner = load('headless_e2e')
    monkeypatch.setenv('GH_TOKEN', 'token')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    bare = bare_repository(tmp_path)
    real = runner.checked
    monkeypatch.setattr(runner, 'checked', lambda argv, **kw: 'octo\n' if argv[0] == 'gh' else real(argv, **kw))
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    root, plugin, env = runner.prepare(scratch, repo='acme/rehearsal', url=str(bare))
    sys.path.insert(0, str(ROOT / 'cli'))
    from wuwei import workspace
    config = workspace.load_config(root)
    repo = config['repos'][0]
    assert config['adapters']['code_host'] == 'github' and config['brief']['remote'] == 'origin'
    assert config['owner']['handles'] == ['octo'] and config['shepherd']['min_reviewers'] == 0
    assert repo['name'] == 'acme/rehearsal' and repo['default_branch'] == 'main'
    assert repo['merge']['auto'] is True and repo['merge']['soak_minutes'] == 0
    assert repo['merge_deploys'] is False
    clone = root / repo['path']
    assert subprocess.run(['git', '-C', clone, 'remote', 'get-url', 'origin'], capture_output=True,
                          text=True, env=env).stdout.strip() == str(bare)
    assert env['GH_TOKEN'] == 'token' and 'WUWEI_NOW' not in env
    assert Path(env['GIT_CONFIG_GLOBAL']) == Path(env['HOME']) / '.gitconfig'
    assert 'gh auth git-credential' in Path(env['GIT_CONFIG_GLOBAL']).read_text()
    check = subprocess.run(['/bin/sh', '-c', repo['fast_checks'][0]], cwd=clone,
                           capture_output=True, text=True)
    assert check.returncode == 1
    line = check.stdout.strip().split(': ', 1)[1]
    assert line.startswith('checked: ') and 'checked:' not in runner.rehearsal_prompt(plugin, 'first', repo='acme/rehearsal', base='main')
    (clone / 'REHEARSAL.md').write_text('status: draft\n' + line + '\n')
    assert subprocess.run(['/bin/sh', '-c', repo['fast_checks'][0]], cwd=clone).returncode == 0


@pytest.mark.parametrize('decision_exit,first_error,code', [(0, False, 0), (1, False, 1), (0, True, 2)])
def test_rehearsal_sessions_and_owner_decision(tmp_path, monkeypatch, capsys,
                                               decision_exit, first_error, code):
    runner = load('headless_e2e')
    monkeypatch.setenv('WUWEI_REHEARSAL_REPO', 'acme/rehearsal')
    monkeypatch.setattr(runner, 'preconditions', lambda local_login: None)
    root, plugin = tmp_path / 'workspace', tmp_path / 'plugin'
    day = root / '.wuwei/days/2026-09-30'
    (day / 'decisions').mkdir(parents=True)
    (day / 'decisions/D-1.md').write_text('Recommendation: B\n')
    (day / 'state.json').write_text(json.dumps({'raised_prs': ['acme/rehearsal#4']}))
    (day / 'events.jsonl').write_text('')
    (root / 'headless-hooks.jsonl').write_text('')
    (root / '.wuwei/config.toml').write_text('[[repos]]\ndefault_branch = "main"\n')
    monkeypatch.setattr(runner, 'prepare', lambda scratch, **kw: (
        root, plugin, {'HOME': 'h', 'PATH': os.pathsep.join(['observer', '/usr/bin'])}))
    monkeypatch.setattr(runner, 'rehearsal_findings', lambda *args: [])
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[0] == 'claude':
            count = sum(call[0][0] == 'claude' for call in calls)
            return SimpleNamespace(returncode=0, stderr='', stdout=json.dumps({
                'type': 'result', 'subtype': 'success', 'is_error': first_error,
                'session_id': f's{count}', 'total_cost_usd': 1.0}))
        return SimpleNamespace(returncode=decision_exit, stdout='', stderr='declined')
    monkeypatch.setattr(runner.adapter, 'run', run)
    assert runner.rehearse() == code
    fields = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    sessions = [argv for argv, _ in calls if argv[0] == 'claude']
    if first_error:
        assert len(calls) == 1 and fields['verdict'] == 'unmeasured'
        return
    assert sessions[0][sessions[0].index('--max-turns') + 1] == str(runner.REHEARSAL['first'][0])
    decision = [(argv, kw) for argv, kw in calls if argv[0] != 'claude']
    assert decision[0][0][1:] == ['decision', 'outcome', 'D-1', 'B']
    assert decision[0][1]['own_group'] is False
    # The owner command bypasses the observer shim, whose 30s bound would cut the digest prompt.
    assert decision[0][1]['env']['PATH'] == '/usr/bin'
    assert fields['interventions'] == ['decision outcome D-1 (planned, host terminal)']
    if decision_exit:
        assert len(sessions) == 1 and fields['verdict'] == 'fail'
    else:
        assert sessions[1][sessions[1].index('--resume') + 1] == 's1'
        assert sessions[1][sessions[1].index('--max-budget-usd') + 1] == str(runner.REHEARSAL['second'][1])
        assert fields == {**fields, 'verdict': 'pass', 'cost_usd': 2.0, 'pr': 'acme/rehearsal#4'}


def test_fixture_item_is_light_so_its_spec_is_skipped(tmp_path):
    (tmp_path / '.wuwei/memory').mkdir(parents=True)
    load('headless_e2e').fixture_plan(tmp_path, 'repo/README.md', 'Verify README exists')
    [candidate] = json.loads((tmp_path / 'proposal.json').read_text())['candidates']
    assert candidate['tier'] == 'light'


def start_evidence():
    """#476: the start-mode day: no refusal probe, no Skill call, no scripted Stop block."""
    data, events, hooks = evidence()
    hooks = [h for h in hooks if h['exit'] != 2 and h.get('tool') != 'Skill']
    hooks.insert(-1, {'event': 'PreToolUse', 'exit': 0, 'tool': 'Bash',
                      'input': {'command': '/plugin/bin/wuwei plan gate'}})
    hooks.insert(-1, {'event': 'PostToolUse', 'exit': 0, 'tool': 'Bash',
                      'input': {'command': '/plugin/bin/wuwei plan gate'}})
    return data, events, hooks


def test_start_prompt_names_no_skill_or_step():
    import re
    text = load('headless_e2e').start_prompt()
    assert text.startswith('Start the day.')
    for phrase in ('Skill', 'skill', 'wuwei-plan', 'wuwei-report', '--'):
        assert phrase not in text
    assert not re.search(r'(?m)^\s*\d+\.', text) and not re.search(r'\bwuwei [a-z]', text)


@pytest.mark.parametrize('mutation', ['refusal', 'help-row', 'help-bash', 'no-plan', 'no-launch',
                                      'no-close-event', 'no-close-row'])
def test_start_mode_validation(mutation):
    runner = load('headless_e2e')
    data, events, hooks = start_evidence()
    assert runner.validate(data, events, hooks, start=True) == []
    assert runner.validate(data, events, hooks) != []
    if mutation == 'refusal':
        events = events + [{'kind': 'hook.refusal', 'payload': {'reason': 'unparsed'}}]
    elif mutation == 'help-row':
        hooks = hooks + [{'event': 'cli', 'args': ['plan', '--help'], 'exit': 0}]
    elif mutation == 'help-bash':
        hooks = hooks + [{'event': 'PreToolUse', 'exit': 0, 'tool': 'Bash',
                          'input': {'command': '/plugin/bin/wuwei close -h'}}]
    elif mutation == 'no-plan':
        events = [e for e in events if e['kind'] != 'plan.approved']
    elif mutation == 'no-launch':
        events = [e for e in events if e['kind'] != 'seat launched']
    elif mutation == 'no-close-event':
        events = [e for e in events if e['kind'] != 'day.close_requested']
    else:
        hooks = [h for h in hooks if h.get('args') != ['close']]
    assert len(runner.validate(data, events, hooks, start=True)) == 1


def test_start_mode_needs_a_key(monkeypatch, capsys):
    runner = load('headless_e2e')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr(runner, 'exercise', lambda *a, **kw: pytest.fail('must skip'))
    assert runner.main(['--start']) == 2
    assert 'ANTHROPIC_API_KEY is not set' in capsys.readouterr().out
