"""Only executing the configured checks can produce fast-check evidence."""

import importlib
import json
from types import SimpleNamespace

import pytest

from wuwei import registry, state
from wuwei.__main__ import main
from wuwei.registry import Result
from test_commit_push import SHA, OLD, guard, payload, workspace_case
from test_git_hook import invoke
from test_state import cli


def clear(root):
    state._write_state(lambda data: data.pop('fast_checks', None), root, reserved=False)


@pytest.mark.parametrize('anchor', ['bash', 'pre-push'])
def test_only_forged_evidence_cannot_authorize_push(workspace_case, monkeypatch, anchor):
    root, _ = workspace_case
    clear(root)
    forged = {'example/project': {'unit': {'sha': SHA, 'exit': 0}}}
    result = cli('state', 'set', 'fast_checks', json.dumps(forged))
    if anchor == 'bash':
        code = guard().check(payload(root, 'git push origin feature'))[0]
    else:
        code = invoke(workspace_case, monkeypatch, anchor,
                      f'refs/heads/feature {SHA} refs/heads/feature {OLD}\n')
    assert code == 1
    assert result.returncode == 1


@pytest.mark.parametrize('exit_code', [0, 1, 2])
def test_recorder_runs_configured_check_and_records_derived_evidence(workspace_case, monkeypatch, exit_code):
    root, vcs = workspace_case
    calls = []

    def run(path, command, root=None):
        assert not state.read_state(root).get('fast_checks', {}).get('example/project')
        calls.append((path, command))
        return Result(exit_code, reason='check unavailable' if exit_code == 2 else '')

    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(run=run) if kind == 'checks' else vcs))
    assert main(['fast-checks', str(root / 'repo')]) == exit_code
    assert calls == [(str(root / 'repo'), 'unit')]
    assert state.read_state(root)['fast_checks'] == {
        'example/project': {'unit': {'sha': SHA, 'exit': exit_code, 'data': None,
            'reason': 'check unavailable' if exit_code == 2 else '',
            'worktree': str(root / 'repo'), 'build': None, 'clean': False}}}
    assert guard().check(payload(root, 'git push origin feature'))[0] == (0 if exit_code == 0 else 1)


@pytest.mark.parametrize('failure', ['head_changed', 'head_unavailable', 'runner_raised', 'runner_unavailable'])
def test_recorder_failure_cannot_leave_passing_evidence(workspace_case, monkeypatch, failure):
    root, vcs = workspace_case

    def run(path, command, root=None):
        if failure == 'runner_raised':
            raise OSError('unavailable')
        if failure == 'head_changed':
            vcs.results['head'].data['sha'] = OLD
        else:
            vcs.results['head'] = Result(2, reason='unavailable')
        return Result(0)

    def load(kind, config):
        if kind == 'checks' and failure == 'runner_unavailable':
            raise ValueError('runner unavailable')
        return SimpleNamespace(run=run) if kind == 'checks' else vcs

    monkeypatch.setattr(registry, 'load', load)
    assert main(['fast-checks', str(root / 'repo')]) == 2
    assert not state.read_state(root).get('fast_checks', {}).get('example/project')


@pytest.mark.parametrize('returncode,expected', [(0, 0), (1, 1), (42, 1), (-9, 1), (None, 2)])
def test_local_checks_execute_configured_shell_command(tmp_path, monkeypatch, returncode, expected):
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['cwd'] == str(tmp_path)
        assert kwargs['timeout'] > 0
        assert 'GIT_DIR' not in kwargs['env']
        if returncode is None:
            raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
        return subprocess.CompletedProcess(argv, returncode)

    monkeypatch.setenv('GIT_DIR', 'unrelated/.git')
    monkeypatch.setattr(subprocess, 'run', run)
    result = adapter.run(str(tmp_path), 'unit && lint')
    assert result.exit == expected
    assert calls == [['/bin/sh', '-c', 'unit && lint']]


@pytest.mark.parametrize('command,output,reason', [
    ('python3 -m pytest -q', 'python3: No module named pytest', 'pytest not found'),
    ('pytest -q', '/bin/sh: pytest: command not found', 'pytest not found'),
    ('pytest -q', '/bin/sh: 1: pytest: not found', 'pytest not found'),
    ('python3 -m pytest -q', '/bin/sh: python3: not found', 'python3 not found'),
    ('python3 -m pytest -q', "ModuleNotFoundError: No module named 'hypothesis'", 'hypothesis not found'),
])
def test_local_checks_classify_missing_environment(tmp_path, monkeypatch, command, output, reason):
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, '', output))
    result = adapter.run(str(tmp_path), command)
    assert result.exit == 1
    assert result.data['environment'] == reason


def test_local_checks_leave_application_import_as_code_failure(tmp_path, monkeypatch):
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, '', "ModuleNotFoundError: No module named 'app'"))
    result = adapter.run(str(tmp_path), 'python3 -m pytest -q')
    assert result.exit == 1
    assert 'environment' not in result.data


def test_local_checks_leave_application_not_found_message_as_code_failure(tmp_path, monkeypatch):
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, '', 'item: not found'))
    result = adapter.run(str(tmp_path), 'python3 -m pytest -q')
    assert result.exit == 1
    assert 'environment' not in result.data


@pytest.mark.parametrize('exit_code,identity', [(0, True), (1, True), (2, True), (0, False)])
def test_build_check_writes_the_record_the_push_guard_reads(workspace_case, monkeypatch, exit_code, identity):
    root, vcs = workspace_case
    clear(root)
    if not identity:
        # A runner with no commit identity: only the commit guard needs one, and it fails closed.
        vcs.results['commit_context'] = Result(2, None, 'git.commit_context: could not run: git exited 128')
    (root / 'brief.md').write_text('Build it')
    tree = str(root / 'repo')
    state._write_state(lambda data: data['items'].update(A={'phase': 'planned'}), root, reserved=False)
    state.transition('A', 'implement', root)
    state._write_state(lambda data: data.setdefault('builds', {}).update(A={
        'brief': 'brief.md', 'worktree': tree, 'runtime': 'claude', 'repo': 'example/project',
        'commands': ['unit'], 'iteration': 1, 'repeats': 0, 'signature': None,
        'status': 'check', 'action': {'action': 'check'}}), root, reserved=False)
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(run=lambda *args, **kwargs: Result(
            exit_code, {'error': 'broken'} if exit_code == 1 else None,
            'check unavailable' if exit_code == 2 else '')) if kind == 'checks' else vcs))
    assert main(['build', 'check', 'A']) == exit_code
    assert state.read_state(root)['fast_checks']['example/project']['unit']['sha'] == SHA
    assert guard().check(payload(root, 'git push origin feature'))[0] == (
        2 if not identity else 0 if exit_code == 0 else 1)
