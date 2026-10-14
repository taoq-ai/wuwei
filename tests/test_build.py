"""Builder iteration backpressure and usage records."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei import registry, state


def setup(tmp_path, monkeypatch, checks, spec='[spec]\nengine="none"\n'):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname="app"\npath="repo"\ndefault_branch="main"\nfast_checks=["test"]\n' + spec +
        '[adapters]\nruntime="codex"\n[build]\nmax_iterations=8\nstuck_after=3\npoll_interval_seconds=0\n')
    repo = tmp_path / 'repo'
    repo.mkdir()
    brief = tmp_path / 'brief.md'
    brief.write_text('Build it')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    day = tmp_path / '.wuwei/days/2026-09-28'
    day.mkdir(parents=True)
    (day / 'state.json').write_text(json.dumps({'items': {'A': {'phase': 'implement', 'status': 'running'}}}))

    class FakeRuntime:
        calls = []

        def dispatch(self, role, brief_path, worktree, write, *, root=None):
            self.calls.append(('dispatch', brief_path))
            return registry.Result(0, {'id': str(len(self.calls)), 'worktree': worktree})

        def continue_job(self, job, feedback, *, root=None):
            self.calls.append(('continue', feedback))
            return registry.Result(0, job)

        def status(self, job, *, root=None):
            return registry.Result(0, {'status': 'completed'})

        def result(self, job, *, root=None):
            return registry.Result(0, {'text': 'Blocked: none\nGap: none\nChange: none',
                                       'usage': {'input_tokens': 2, 'output_tokens': 3,
                                                 'model': 'fake', 'duration': 1}})

    runtime = FakeRuntime()

    class FakeChecks:
        def run(self, path, command, *, timeout=None, root=None):
            return checks.pop(0)

    vcs = SimpleNamespace(head=lambda *a, **kw: registry.Result(0, {'sha': 'a' * 40}),
                          merge_base=lambda *a, **kw: registry.Result(0, {'sha': 'a' * 40}),
                          diff_stat=lambda *a, **kw: registry.Result(0, [{'path': 'app.py'}]),
                          status=lambda *a, **kw: registry.Result(0, []),
                          repo_context=lambda *a, **kw: registry.Result(0, {
                              'path': str(repo), 'common_dir': str(repo / '.git')}),
                          touched=lambda *a, **kw: registry.Result(0, []), commits=[])
    vcs.commit_all = lambda *a, **kw: vcs.commits.append(a) or registry.Result(0, {})
    runtime.vcs = vcs

    def load(kind, config):
        return {'runtime': runtime, 'vcs': vcs}.get(kind) or FakeChecks()

    monkeypatch.setattr(registry, 'load', load)
    return repo, brief, day, runtime


def events(day):
    return [json.loads(line) for line in (day / 'events.jsonl').read_text().splitlines()]


def test_stuck_after_three_same_failures(tmp_path, monkeypatch):
    from wuwei.commands import build
    failure = lambda: registry.Result(1, {'test_ids': ['test_a'], 'error': 'ValueError at line 1'})
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [failure(), failure(), failure()])
    code = build.run_loop('A', str(brief), str(repo), root=tmp_path)
    assert code == 1
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 3
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'parked'
    assert not list((day / 'decisions').glob('D-*.md'))


def test_environment_failure_holds_after_first_check_without_feedback(tmp_path, monkeypatch):
    # #904: a hold with a recheck action; the loop stops for the repair, the item does not park.
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [
        registry.Result(1, {'test_ids': [], 'error': 'No module named pytest',
                            'environment': 'pytest not found'})])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    record = state.read_state(tmp_path)['builds']['A']
    assert record['iteration'] == 1
    assert (record['status'], record['action']['action']) == ('check', 'check')
    assert record['action']['reason'].startswith('environment: pytest not found')
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'implement'
    assert runtime.calls == [('dispatch', str(brief))]
    assert not any(event['kind'] == 'build.checked' for event in events(day))


def test_green_on_second_iteration_records_two_usages(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [
        registry.Result(1, {'test_ids': ['test_a'], 'error': 'assert 1 == 2'}),
        registry.Result(0)])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 2
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'gate'


def test_zero_diff_measurement_finishes_without_fast_check_or_commit(tmp_path, monkeypatch):
    from wuwei import dispatch
    from wuwei.commands import build

    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [], spec='')
    state._write_state(lambda data: data['items']['A'].update(kind='measure'), tmp_path)
    monkeypatch.setattr(dispatch, '_changes', lambda root, config, row: ({}, []))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    record = state.read_state(tmp_path)['builds']['A']
    assert record['status'] == 'done' and record['commands'] == []
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'gate'
    assert not [row for row in events(day) if row['kind'] == 'build.check_started']
    assert runtime.vcs.commits == []


def test_measurement_with_dirty_worktree_does_not_commit_it(tmp_path, monkeypatch):
    from wuwei import dispatch
    from wuwei.commands import build

    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [], spec='')
    state._write_state(lambda data: data['items']['A'].update(kind='measure'), tmp_path)
    monkeypatch.setattr(dispatch, '_changes', lambda root, config, row: ({}, []))
    runtime.vcs.status = lambda *args, **kwargs: registry.Result(0, [{'path': 'src/probe.py'}])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    assert runtime.vcs.commits == []
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'parked'
    assert not [row for row in events(day) if row['kind'] == 'build.check_started']


def test_measurement_on_existing_pr_branch_does_not_own_prior_diff(tmp_path, monkeypatch):
    from wuwei import derive, dispatch
    from wuwei.commands import build

    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [], spec='')
    monkeypatch.setattr(derive, 'head', lambda path: 'a' * 40)
    state._write_state(lambda data: data['items']['A'].update(kind='measure'), tmp_path)
    monkeypatch.setattr(dispatch, '_changes', lambda root, config, row: (
        {}, [{'path': 'src/pr.py', 'additions': 1, 'deletions': 0}]))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'gate'


def test_unmeasured_check_exits_two(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(2, reason='tool missing')])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 2


def test_codex_rerun_resumes_job_after_poll_timeout(tmp_path, monkeypatch, capsys):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    with (tmp_path / '.wuwei/config.toml').open('a') as config:
        config.write('poll_timeout_seconds=1\n')
    with monkeypatch.context() as patch:
        clock = iter([0, 2])
        patch.setattr(build.time, 'monotonic', lambda: next(clock))
        patch.setattr(runtime, 'status', lambda job, *, root=None:
                      registry.Result(0, {'status': 'running'}))
        assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 2
    assert 'runtime seat timed out' in capsys.readouterr().err
    record = state.read_state(tmp_path)['builds']['A']
    assert record['status'] == 'running'

    def completed(job, *, root=None):
        assert job == record['job']
        return registry.Result(0, {'status': 'completed'})

    monkeypatch.setattr(runtime, 'status', completed)
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert state.read_state(tmp_path)['builds']['A']['status'] == 'done'
    assert runtime.calls == [('dispatch', str(brief))]
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 1


def test_codex_failed_job_frees_the_build_and_the_rerun_relaunches(tmp_path, monkeypatch, capsys):
    # #871: a failed job names the companion's error, and the record is ready again
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    with monkeypatch.context() as patch:
        patch.setattr(runtime, 'status', lambda job, *, root=None: registry.Result(0, {
            'status': 'failed', 'error': 'failed to initialize sqlite state runtime'}))
        assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 2
    assert 'failed to initialize sqlite state runtime' in capsys.readouterr().err
    record = state.read_state(tmp_path)['builds']['A']
    assert record['status'] == 'ready' and record['action']['action'] == 'launch'
    [failed] = [e['payload'] for e in events(day) if e['kind'] == 'build.failed']
    assert 'sqlite' in failed['reason']
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert runtime.calls == [('dispatch', str(brief))] * 2


IDENTITY = 'identity = { name = "Builder", email = "builder@example.test" }\n'


def test_codex_build_is_committed_by_wuwei_with_the_repo_identity(tmp_path, monkeypatch):
    # #871 L2: the sandboxed job cannot write the worktree's git metadata, so WUWEI commits
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks=["test"]\n', 'fast_checks=["test"]\n' + IDENTITY))
    vcs = runtime.vcs
    vcs.status = lambda *a, **kw: registry.Result(0, [] if vcs.commits else [
        {'path': 'C.txt', 'index': '?', 'worktree': '?', 'original_path': None}])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert vcs.commits == [(str(repo.resolve()), 'A', 'Builder', 'builder@example.test')]
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'gate'


def test_codex_build_commit_needs_the_repo_identity(tmp_path, monkeypatch, capsys):
    # #871 L2: no identity, no commit; the build keeps its completed job, so the rerun commits
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    runtime.vcs.status = lambda *a, **kw: registry.Result(0, [
        {'path': 'C.txt', 'index': '?', 'worktree': '?', 'original_path': None}])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 2
    assert 'config set repos.0.identity' in capsys.readouterr().err
    assert runtime.vcs.commits == [] and state.read_state(tmp_path)['builds']['A']['status'] == 'running'


@pytest.mark.parametrize('path,committed', [
    ('.env', False), ('config/.env.local', False), ('deploy.pem', False), ('.ssh/id_rsa', False),
    ('.env.example', True), ('secret_scanner.py', True), ('docs/credentials.md', True)])
def test_codex_build_never_commits_a_private_file(tmp_path, monkeypatch, path, committed):
    # #871 B1: a private file the job left is not committed; the builder is told to remove it
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)] * 3)
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks=["test"]\n', 'fast_checks=["test"]\n' + IDENTITY))
    vcs = runtime.vcs
    vcs.status = lambda *a, **kw: registry.Result(0, [] if vcs.commits else [
        {'path': row, 'index': '?', 'worktree': '?', 'original_path': None} for row in (path, 'code.py')])
    code = build.run_loop('A', str(brief), str(repo), root=tmp_path)
    feedback = [call[1] for call in runtime.calls if call[0] == 'continue']
    if committed:
        assert (code, len(vcs.commits), feedback) == (0, 1, [])
    else:
        assert vcs.commits == [] and code == 1
        assert feedback and f'private files {path}' in feedback[0] and '.gitignore' in feedback[0]
        # round 3: a repeat parks with its own cause, not the fast-check reason
        assert state.read_state(tmp_path)['builds']['A']['action']['reason'] == 'private files repeated'


@pytest.mark.parametrize('deleted', [False, True])
def test_a_private_file_the_builder_committed_is_not_done(tmp_path, monkeypatch, deleted):
    # #871 round 3, A16: a .env the job committed itself is caught before the gates, even when a
    # later commit deletes it, because the push sends every commit since the start head
    import importlib
    import subprocess
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)] * 3)
    git = ['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@e']
    subprocess.run([*git, 'init', '-q'], check=True)
    subprocess.run([*git, 'commit', '-q', '--allow-empty', '-m', 'init'], check=True)
    runtime.vcs.touched = importlib.import_module('adapters.vcs.git').touched
    done, rounds = runtime.result, []

    def result(job, *, root=None):
        rounds.append(job)
        (repo / '.env').write_text('KEY=1\n')
        (repo / 'code.py').write_text(f'x = {len(rounds)}\n')
        subprocess.run([*git, 'add', '--all'], check=True)
        subprocess.run([*git, 'commit', '-q', '-m', 'change'], check=True)
        if deleted:
            subprocess.run([*git, 'rm', '-q', '.env'], check=True)
            subprocess.run([*git, 'commit', '-q', '-m', 'drop it'], check=True)
        return done(job, root=root)
    runtime.result = result
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    record = state.read_state(tmp_path)['builds']['A']
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'parked'
    assert record['action']['reason'] == 'private files repeated'
    feedback = [call[1] for call in runtime.calls if call[0] == 'continue']
    assert feedback and 'private files .env' in feedback[0]
    assert f'git reset --soft {record["start"]}' in feedback[0] and 'not pushed yet' in feedback[0]


def test_a_repeated_commit_refusal_parks_with_its_cause(tmp_path, monkeypatch):
    # #871 round 3: a hook that keeps rejecting parks as a commit refusal
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)] * 3)
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks=["test"]\n', 'fast_checks=["test"]\n' + IDENTITY))
    runtime.vcs.status = lambda *a, **kw: registry.Result(0, [
        {'path': 'code.py', 'index': '?', 'worktree': '?', 'original_path': None}])
    runtime.vcs.commit_all = lambda *a, **kw: registry.Result(2, None, 'git exited 1: lint failed')
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    assert state.read_state(tmp_path)['builds']['A']['action']['reason'] == 'commit refused repeated'


def test_failed_codex_commit_goes_back_to_the_builder(tmp_path, monkeypatch):
    # #871 B2: a rejecting pre-commit hook is the builder's to fix, not a dead end
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks=["test"]\n', 'fast_checks=["test"]\n' + IDENTITY))
    vcs, tries = runtime.vcs, []
    vcs.status = lambda *a, **kw: registry.Result(0, [] if vcs.commits else [
        {'path': 'code.py', 'index': '?', 'worktree': '?', 'original_path': None}])

    def commit_all(*args, **kwargs):
        tries.append(args)
        if len(tries) == 1:
            return registry.Result(2, None, 'git.commit_all: could not run: git exited 1: lint failed: ruff')
        vcs.commits.append(args)
        return registry.Result(0, {})
    vcs.commit_all = commit_all
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    feedback = [call[1] for call in runtime.calls if call[0] == 'continue']
    assert len(feedback) == 1 and 'commit: ' in feedback[0] and 'lint failed: ruff' in feedback[0]
    assert len(tries) == 2 and state.read_state(tmp_path)['items']['A']['phase'] == 'gate'


def test_a_build_with_a_dirty_tree_is_not_done(tmp_path, monkeypatch):
    # #871 L2: uncommitted changes after a build never reach the gates
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)] * 3)
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('fast_checks=["test"]\n', 'fast_checks=["test"]\n' + IDENTITY))
    runtime.vcs.status = lambda *a, **kw: registry.Result(0, [
        {'path': 'C.txt', 'index': '?', 'worktree': '?', 'original_path': None}])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'parked'
    feedback = [call[1] for call in runtime.calls if call[0] == 'continue']
    assert feedback and 'uncommitted changes: C.txt' in feedback[0]


@pytest.mark.parametrize('commits', [False, True])
def test_a_build_with_no_new_commit_is_not_done(tmp_path, monkeypatch, commits):
    # #871 L2: a build whose HEAD is still its start head never sends that head to the gates
    import subprocess
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)] * 3)
    git = ['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@e']
    subprocess.run([*git, 'init', '-q'], check=True)
    subprocess.run([*git, 'commit', '-q', '--allow-empty', '-m', 'init'], check=True)
    if commits:
        done = runtime.result
        runtime.result = lambda job, *, root=None: subprocess.run(
            [*git, 'commit', '-q', '--allow-empty', '-m', 'change'], check=True) and done(job, root=root)
    code = build.run_loop('A', str(brief), str(repo), root=tmp_path)
    phase = state.read_state(tmp_path)['items']['A']['phase']
    feedback = [call[1] for call in runtime.calls if call[0] == 'continue']
    if commits:
        assert (code, phase, feedback) == (0, 'gate', [])
    else:  # #871 B5: parks on the first repeat, with its own reason
        assert (code, phase, len(feedback)) == (1, 'parked', 1)
        assert 'no change over the start head' in feedback[0]
        assert state.read_state(tmp_path)['builds']['A']['action']['reason'] == 'no change over the start head'


def test_local_check_exposes_failing_ids_and_error(monkeypatch):
    from adapters.checks import local
    from types import SimpleNamespace
    monkeypatch.setattr(local.subprocess, 'run', lambda *a, **kw: SimpleNamespace(
        returncode=1, stdout='FAILED tests/test_a.py::test_one - AssertionError\n', stderr='trace\n'))
    result = local.run('checkout', 'pytest -q')
    assert result.exit == 1
    assert result.data['test_ids'] == ['tests/test_a.py::test_one']
    assert 'AssertionError' in result.data['error']


def test_signature_ignores_pytest_duration_and_tmp_path():
    from wuwei.commands.build import _signature
    first = [('test', {'test_ids': ['tests/test_a.py::test_one'],
                       'error': 'FAILED tests/test_a.py::test_one - AssertionError\n'
                                '/tmp/pytest-of-user/pytest-42/test_one0\n1 failed in 0.41s'})]
    second = [('test', {'test_ids': ['tests/test_a.py::test_one'],
                        'error': 'FAILED tests/test_a.py::test_one - AssertionError\n'
                                 '/tmp/pytest-of-user/pytest-43/test_one0\n1 failed in 0.52s'})]
    assert _signature(first) == _signature(second)


@pytest.mark.parametrize('first_path,second_path', [
    ('/tmp/run-a/result', '/tmp/run-b/result'),
    ('/private/var/folders/aa/bb/T/run-a/result',
     '/private/var/folders/cc/dd/T/run-b/result'),
])
def test_signature_normalizes_variable_text_in_failed_summary_lines(first_path, second_path):
    from wuwei.commands.build import _signature
    first = [('test', {'test_ids': ['tests/test_a.py::test_one'],
                       'error': 'FAILED tests/test_a.py::test_one - AssertionError: '
                                f'<object object at 0x1abc> in {first_path} pytest-42 0.41s'})]
    second = [('test', {'test_ids': ['tests/test_a.py::test_one'],
                        'error': 'FAILED tests/test_a.py::test_one - AssertionError: '
                                 f'<object object at 0x2def> in {second_path} pytest-43 0.52s'})]
    assert _signature(first) == _signature(second)


def test_build_marks_missing_usage_unmeasured(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    monkeypatch.setattr(runtime, 'result', lambda job, *, root=None: registry.Result(0, {'text': 'done'}))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    usage = next(e['payload']['usage'] for e in events(day) if e['kind'] == 'seat.usage')
    assert usage == {'input_tokens': 'unmeasured', 'output_tokens': 'unmeasured',
                     'cost': 'unmeasured', 'model': 'unmeasured', 'duration': 'unmeasured'}


def test_build_records_reported_usage(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    reported = {'input_tokens': 12, 'output_tokens': 7, 'cost': 0.03,
                'model': 'codex-test', 'duration': 4.5}
    monkeypatch.setattr(runtime, 'result', lambda job, *, root=None:
                        registry.Result(0, {'text': 'done', 'usage': reported}))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    usage = next(e['payload']['usage'] for e in events(day) if e['kind'] == 'seat.usage')
    assert usage == reported


def test_build_rejects_malformed_reported_usage(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    monkeypatch.setattr(runtime, 'result', lambda job, *, root=None: registry.Result(0, {'usage': {'input_tokens': 'bad'}}))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 2


def test_builder_policy_overrides_workspace_runtime(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('runtime="codex"', 'runtime="claude"'))
    state._write_state(lambda data: data.update(seat_policy={
        'builder': {'runtime': 'codex', 'model': 'test'}}), tmp_path)
    selected = []
    original = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, settings:
                        selected.append((kind, settings['adapters']['runtime'])) or original(kind, settings))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert ('runtime', 'codex') in selected


def test_build_reports_unknown_item(tmp_path, monkeypatch, capsys):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [])
    assert build.run_loop('missing', str(brief), str(repo), root=tmp_path) == 2
    assert 'build: unknown item missing' in capsys.readouterr().err


@pytest.mark.parametrize('maximum', [False, True])
def test_build_park_names_plan_resume_and_writes_no_record(tmp_path, monkeypatch, capsys, maximum):
    from wuwei.commands import build
    failure = lambda: registry.Result(1, {'test_ids': ['test_a'], 'error': 'failed'})
    repo, brief, day, _ = setup(tmp_path, monkeypatch, [failure(), failure(), failure()])
    if maximum:
        config = tmp_path / '.wuwei/config.toml'
        config.write_text(config.read_text().replace('max_iterations=8', 'max_iterations=1'))
    decisions = day / 'decisions'
    decisions.mkdir()
    (decisions / 'D-1.md').write_text('preserve existing record')
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    err = capsys.readouterr().err
    assert ('maximum build iterations reached' if maximum else 'same fast-check failure repeated') in err
    # Part 14: the parked line names plan resume, which asks the owner; never a host terminal.
    assert 'run wuwei plan resume A after revising its brief' in err and 'host terminal' not in err
    assert sorted(path.name for path in decisions.glob('D-*.md')) == ['D-1.md']
    assert (decisions / 'D-1.md').read_text() == 'preserve existing record'
    data = state.read_state(tmp_path)
    assert 'decision_outcomes' not in data
    record = data['builds']['A']
    assert record['status'] == 'parked' and 'decision' not in record['action']
    assert data['items']['A']['disposition'] == {'kind': 'parked', 'reason': record['action']['reason']}


def test_spec_gap_is_a_failing_check_that_parks_when_stuck(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)] * 3, spec='')
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'parked'
    feedback = runtime.calls[1][1]
    assert feedback.startswith('spec: ') and 'specify first: /speckit.specify' in feedback


def test_spec_complete_moves_to_gate(tmp_path, monkeypatch):
    import shutil
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)], spec='')
    shutil.copytree(Path(__file__).parent / 'fixtures/spec/speckit/specs', repo / 'specs')
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'gate'


def test_light_tier_spec_skip_is_rechecked_against_the_diff(tmp_path, monkeypatch):
    from wuwei import dispatch
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)] * 3, spec='')
    data = json.loads((day / 'state.json').read_text())
    data['items']['A']['tier'] = 'light'
    (day / 'state.json').write_text(json.dumps(data))
    monkeypatch.setattr(dispatch, 'tier', lambda root, config, row: {'computed': 'standard'})
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 1
    assert runtime.calls[1][1].startswith('spec: ')


def test_advisory_spec_gap_warns_once_and_moves_to_gate(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)], spec='[spec]\nmode="advisory"\n')
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'gate'
    assert [e['payload'] for e in events(day) if e['kind'] == 'spec.warned'] == [
        {'item': 'A', 'engine': 'speckit', 'step': 'specify', 'where': 'gates'}]
