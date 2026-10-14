"""Only executing the configured checks can produce fast-check evidence."""

import importlib
import json
from types import SimpleNamespace

import pytest

from wuwei import fast_checks, registry, state
from wuwei.__main__ import main
from wuwei.registry import Result
from test_commit_push import SHA, OLD, workspace_case  # noqa: F401  (fixture)


def clear(root):
    state._write_state(lambda data: data.pop('fast_checks', None), root)


@pytest.mark.parametrize('exit_code', [0, 1, 2])
def test_recorder_runs_configured_check_and_records_derived_evidence(workspace_case, monkeypatch, exit_code):
    root, vcs = workspace_case
    calls = []

    def run(path, command, timeout=300, root=None):
        assert not state.read_state(root).get('fast_checks', {}).get('example/project')
        calls.append((path, command))
        return Result(exit_code, reason='check unavailable' if exit_code == 2 else '')

    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(run=run) if kind == 'checks' else vcs))
    assert fast_checks.record(root / 'repo') == exit_code
    assert calls == [(str(root / 'repo'), 'unit')]
    recorded = state.read_state(root)['fast_checks']
    assert type(recorded['example/project']['unit'].pop('seconds')) is float  # #579
    assert recorded == {
        'example/project': {'unit': {'sha': SHA, 'exit': exit_code, 'data': None,
            'reason': 'check unavailable' if exit_code == 2 else '',
            'worktree': str(root / 'repo'), 'build': None, 'clean': False}}}


@pytest.mark.parametrize('line,timeout', [('', 300), ('\ncheck_timeout_seconds = 900', 900)])
def test_recorder_passes_the_repository_timeout(workspace_case, monkeypatch, line, timeout):  # #724
    root, vcs = workspace_case
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks = ["unit"]', 'fast_checks = ["unit"]' + line))
    seen = []
    port = SimpleNamespace(run=lambda path, command, timeout=None, root=None: seen.append(timeout) or Result(0))
    monkeypatch.setattr(registry, 'load', lambda kind, config: port if kind == 'checks' else vcs)
    assert fast_checks.record(root / 'repo') == 0
    assert seen == [timeout]
    assert state.read_state(root)['fast_checks']['example/project']['unit']['exit'] == 0


@pytest.mark.parametrize('failure', ['head_changed', 'head_unavailable', 'runner_raised', 'runner_unavailable'])
def test_recorder_failure_cannot_leave_passing_evidence(workspace_case, monkeypatch, failure):
    root, vcs = workspace_case

    def run(path, command, timeout=300, root=None):
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
    with pytest.raises((OSError, ValueError)):  # the CLI reported these as exit 2
        fast_checks.record(root / 'repo')
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


def _case_local_checks_use_the_given_timeout(tmp_path, monkeypatch):  # #724
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')

    def run(argv, **kwargs):  # a 600 s check
        if kwargs['timeout'] < 600:
            raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, 'run', run)
    assert adapter.run(str(tmp_path), 'suite', timeout=900).exit == 0
    assert adapter.run(str(tmp_path), 'suite').exit == 2


def _case_local_checks_timeout_names_command_limit_and_setting(tmp_path, monkeypatch):  # #724
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')

    def run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs['timeout'])

    monkeypatch.setattr(subprocess, 'run', run)
    result = adapter.run(str(tmp_path), 'python3 -m pytest -q', timeout=900)
    assert (result.exit, result.reason) == (2, 'fast check `python3 -m pytest -q` exceeded 900 s '
                                               '(repos.<n>.check_timeout_seconds); raise it with '
                                               'bin/wuwei config set or split the check')

    def broken(argv, **kwargs):
        raise OSError('no shell')

    monkeypatch.setattr(subprocess, 'run', broken)
    assert adapter.run(str(tmp_path), 'suite', timeout=900).reason == 'fast check could not run: OSError'


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


def _case_local_checks_leave_application_import_as_code_failure(tmp_path, monkeypatch):
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, '', "ModuleNotFoundError: No module named 'app'"))
    result = adapter.run(str(tmp_path), 'python3 -m pytest -q')
    assert result.exit == 1
    assert 'environment' not in result.data


def _case_local_checks_leave_application_not_found_message_as_code_failure(tmp_path, monkeypatch):
    import subprocess
    adapter = importlib.import_module('adapters.checks.local')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, '', 'item: not found'))
    result = adapter.run(str(tmp_path), 'python3 -m pytest -q')
    assert result.exit == 1
    assert 'environment' not in result.data


@pytest.mark.parametrize("scenario_fn", [
    _case_local_checks_use_the_given_timeout,
    _case_local_checks_timeout_names_command_limit_and_setting,
    _case_local_checks_leave_application_import_as_code_failure,
    _case_local_checks_leave_application_not_found_message_as_code_failure,
])
def test_local_checks_cases_100(tmp_path, monkeypatch, scenario_fn):
    scenario_fn(tmp_path, monkeypatch)


@pytest.mark.parametrize('exit_code,identity', [(0, True), (1, True), (2, True), (0, False)])
def test_build_check_writes_the_record(workspace_case, monkeypatch, exit_code, identity):
    root, vcs = workspace_case
    clear(root)
    if not identity:
        # A runner with no commit identity: the record needs none.
        vcs.results['commit_context'] = Result(2, None, 'git.commit_context: could not run: git exited 128')
    (root / 'brief.md').write_text('Build it')
    tree = str(root / 'repo')
    state._write_state(lambda data: data['items'].update(A={'phase': 'planned'}), root)
    state.transition('A', 'implement', root)
    state._write_state(lambda data: data.setdefault('builds', {}).update(A={
        'brief': 'brief.md', 'worktree': tree, 'runtime': 'claude', 'repo': 'example/project',
        'commands': ['unit'], 'iteration': 1, 'repeats': 0, 'signature': None,
        'status': 'check', 'action': {'action': 'check'}}), root)
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(run=lambda *args, **kwargs: Result(
            exit_code, {'error': 'broken'} if exit_code == 1 else None,
            'check unavailable' if exit_code == 2 else '')) if kind == 'checks' else vcs))
    assert main(['build', 'check', 'A']) == exit_code
    assert state.read_state(root)['fast_checks']['example/project']['unit']['sha'] == SHA


def stub(path, code=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/bin/sh\nexit {code}\n')
    path.chmod(0o755)
    return path


VENV = '.venv/bin/python -m pytest -q'


@pytest.mark.parametrize('command,where,setting,expected', [
    ('python3 -m pytest -q', ['tree', 'main'], '', None),
    (VENV, ['tree', 'main'], '', ('tree', 'worktree')),
    (VENV, ['main'], '', ('main', 'main worktree')),
    (VENV, [], '', ('tree', 'missing')),
    (VENV, ['broken', 'main'], '', ('main', 'main worktree')),
    (VENV, ['tree'], 'ABS', ('abs', 'checks.python')),
    (VENV, ['tree'], 'envs/py/bin/python', ('setting', 'checks.python')),
    ('node_modules/.bin/jest', ['main'], 'ABS', ('main', 'main worktree')),
])
def test_interpreter_resolution(tmp_path, command, where, setting, expected):
    from wuwei import fast_checks
    tree, main_tree = tmp_path / 'worktrees/A', tmp_path / 'repo'
    word = command.split()[0]
    tree.mkdir(parents=True)
    main_tree.mkdir()
    if 'tree' in where:
        stub(tree / word)
    if 'main' in where:
        stub(main_tree / word)
    if 'broken' in where:
        (tree / word).parent.mkdir(parents=True)
        (tree / word).symlink_to(tmp_path / 'gone')
    absolute = stub(tmp_path / 'abs/python')
    config = {'checks': {'python': str(absolute) if setting == 'ABS' else setting, 'bootstrap': ''}}
    paths = {'tree': tree / word, 'main': main_tree.resolve() / word, 'abs': absolute,
             'setting': main_tree.resolve() / 'envs/py/bin/python'}
    found = fast_checks.interpreter(command, tree, {'path': 'repo'}, tmp_path, config)
    assert found == (expected and (paths[expected[0]], expected[1]))


def item_worktree(root, vcs, checks):
    """An item worktree without .venv whose build waits for checks."""
    tree = root / 'worktrees/A'
    tree.mkdir(parents=True)
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks = ["unit"]', f'fast_checks = {json.dumps(checks)}'))
    vcs.results['repo_context'] = Result(0, {'path': str(tree), 'common_dir': str(root / 'repo/.git')})
    clear(root)
    (root / 'brief.md').write_text('Build it')
    state._write_state(lambda data: data['items'].update(A={'phase': 'planned'}), root)
    state.transition('A', 'implement', root)
    state._write_state(lambda data: data.setdefault('builds', {}).update(A={
        'brief': 'brief.md', 'worktree': str(tree), 'runtime': 'claude', 'repo': 'example/project',
        'commands': checks, 'iteration': 1, 'repeats': 0, 'signature': None,
        'status': 'check', 'action': {'action': 'check'}}), root)
    return tree


@pytest.mark.parametrize('start,expected_status', [(None, 'done'), (SHA, 'ready')])
def test_build_check_skips_missing_linter_on_clean_empty_diff(workspace_case, monkeypatch,
                                                               start, expected_status):
    from wuwei import derive, workspace

    root, vcs = workspace_case
    item_worktree(root, vcs, ['eslint .'])
    if start:
        state._write_state(lambda data: data['builds']['A'].update(start=start), root)
        monkeypatch.setattr(derive, 'head', lambda path: start)
    vcs.results['diff_stat'] = Result(0, [])
    calls = []
    runner = SimpleNamespace(run=lambda *args, **kwargs: calls.append(args) or Result(
        1, {'error': 'sh: eslint: not found', 'environment': 'eslint not found'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: runner if kind == 'checks' else vcs)

    assert main(['build', 'check', 'A']) == (1 if start else 0)
    assert calls == []
    data = state.read_state(root)
    assert data['builds']['A']['status'] == expected_status
    assert data['items']['A']['phase'] != 'parked'
    assert data['builds']['A']['commands'] == ['eslint .']
    if start:
        assert 'check_result' not in data['builds']['A']
    else:
        assert data['builds']['A']['check_result'] == 'not applicable: no diff'
    events = [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    assert [row['payload']['checks'] for row in events if row['kind'] == 'build.checked'] == [
        'not applicable: no diff']
    assert not data.get('fast_checks', {}).get('example/project')


def test_measure_check_uses_build_start_instead_of_origin_base(workspace_case, monkeypatch):
    root, vcs = workspace_case
    item_worktree(root, vcs, ['eslint .'])
    state._write_state(lambda data: (data['items']['A'].update(kind='measure'),
                                     data['builds']['A'].update(start=SHA)), root)
    bases = []

    def diff_stat(path, base, head, root=None):
        bases.append(base)
        return Result(0, [] if base == SHA else [{'path': 'prior-commit.py'}])

    vcs.diff_stat = diff_stat
    calls = []
    runner = SimpleNamespace(run=lambda *args, **kwargs: calls.append(args) or Result(
        1, {'error': 'eslint missing', 'environment': 'eslint missing'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: runner if kind == 'checks' else vcs)

    assert main(['build', 'check', 'A']) == 0
    assert bases == [SHA]
    assert calls == []
    assert state.read_state(root)['builds']['A']['check_result'] == 'not applicable: no diff'


@pytest.mark.parametrize('changes,dirty', [([{'path': 'app.py'}], []), ([], [{'path': 'app.py'}])])
def test_build_check_runs_linter_for_changed_or_dirty_item(workspace_case, monkeypatch, changes, dirty):
    root, vcs = workspace_case
    item_worktree(root, vcs, ['eslint .'])
    vcs.results['diff_stat'] = Result(0, changes)
    vcs.results['status'] = Result(0, dirty)
    calls = []
    runner = SimpleNamespace(run=lambda *args, **kwargs: calls.append(args) or Result(0))
    monkeypatch.setattr(registry, 'load', lambda kind, config: runner if kind == 'checks' else vcs)

    assert main(['build', 'check', 'A']) == (1 if dirty else 0)
    assert len(calls) == 1
    assert state.read_state(root)['builds']['A']['commands'] == ['eslint .']


@pytest.mark.parametrize('diff', [Result(2, reason='git diff failed'), Result(0, None)])
def test_build_check_fails_closed_when_diff_unmeasured(workspace_case, monkeypatch, capsys, diff):
    root, vcs = workspace_case
    item_worktree(root, vcs, ['eslint .'])
    vcs.results['diff_stat'] = diff
    calls = []
    runner = SimpleNamespace(run=lambda *args, **kwargs: calls.append(args) or Result(0))
    monkeypatch.setattr(registry, 'load', lambda kind, config: runner if kind == 'checks' else vcs)

    assert main(['build', 'check', 'A']) == 2
    assert not calls
    assert 'diff' in capsys.readouterr().err
    assert state.read_state(root)['builds']['A']['status'] == 'check'


def real_checks(monkeypatch, vcs, calls=None):
    adapter = importlib.import_module('adapters.checks.local')

    def run(path, command, timeout=300, root=None):
        if calls is not None:
            calls.append(command)
        return adapter.run(path, command, timeout, root=root)
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(run=run) if kind == 'checks' else vcs))


def test_build_check_runs_the_main_worktree_interpreter(workspace_case, monkeypatch):
    root, vcs = workspace_case
    item_worktree(root, vcs, [VENV])
    stub(root / 'repo/.venv/bin/python')
    real_checks(monkeypatch, vcs)
    assert main(['build', 'check', 'A']) == 0
    row = state.read_state(root)['fast_checks']['example/project'][VENV]
    assert row['exit'] == 0 and row['interpreter'] == str(root.resolve() / 'repo/.venv/bin/python')


@pytest.mark.parametrize('folder', ['py', 'with space'])
def test_checks_python_wins_in_every_worktree(workspace_case, monkeypatch, folder):
    root, vcs = workspace_case
    tree = item_worktree(root, vcs, [VENV])
    setting = stub(root / folder / 'python')
    stub(root / 'repo/.venv/bin/python', 1)
    stub(tree / '.venv/bin/python', 1)
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + f'[checks]\npython = "{setting}"\n')
    real_checks(monkeypatch, vcs)
    for path, context in ((tree, tree), (root / 'repo', root / 'repo')):
        vcs.results['repo_context'] = Result(0, {'path': str(context), 'common_dir': str(root / 'repo/.git')})
        assert fast_checks.record(path) == 0
        row = state.read_state(root)['fast_checks']['example/project'][VENV]
        assert row['exit'] == 0 and row['interpreter'] == str(setting)


@pytest.mark.parametrize('present', [True, False])
def test_worktree_interpreter_runs_the_command_unchanged(workspace_case, monkeypatch, present):
    root, vcs = workspace_case
    tree = item_worktree(root, vcs, [VENV])
    if present:
        stub(tree / '.venv/bin/python')
    calls = []
    real_checks(monkeypatch, vcs, calls)
    assert fast_checks.record(tree) == (0 if present else 1)
    assert calls == [VENV]
    row = state.read_state(root)['fast_checks']['example/project'][VENV]
    assert row['interpreter'] == (str(tree.resolve() / '.venv/bin/python') if present else None)


def test_record_reads_the_repository_context_at_call_time(tmp_path, monkeypatch):
    # #844 D1: a from-import bound commit_push.context once, so a test that patched it while
    # this module first loaded leaked its stand-in into later days in the same worker.
    from wuwei import commit_push, fast_checks

    def stand_in(*args, **kwargs):
        raise ValueError('the patched context')
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setattr(commit_push, 'context', stand_in)
    with pytest.raises(ValueError, match='the patched context'):
        fast_checks.record(tmp_path)
