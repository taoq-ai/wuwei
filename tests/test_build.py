"""Builder iteration backpressure and usage records."""

import json
from pathlib import Path

import pytest

from wuwei import registry, state


def setup(tmp_path, monkeypatch, checks):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname="app"\npath="repo"\ndefault_branch="main"\nfast_checks=["test"]\n'
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
        def run(self, path, command, *, root=None):
            return checks.pop(0)

    def load(kind, config):
        return runtime if kind == 'runtime' else FakeChecks()

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
    assert list((day / 'decisions').glob('*.md'))


def test_green_on_second_iteration_records_two_usages(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [
        registry.Result(1, {'test_ids': ['test_a'], 'error': 'assert 1 == 2'}),
        registry.Result(0)])
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    assert len([e for e in events(day) if e['kind'] == 'seat.usage']) == 2
    assert state.read_state(tmp_path)['items']['A']['phase'] == 'implement'


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


def test_build_accepts_unreported_usage_and_records_duration(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    monkeypatch.setattr(runtime, 'result', lambda job, *, root=None: registry.Result(0, {'text': 'done'}))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 0
    usage = next(e['payload']['usage'] for e in events(day) if e['kind'] == 'seat.usage')
    assert usage['input_tokens'] is None and usage['output_tokens'] is None
    assert usage['model'] == 'unreported' and usage['duration'] >= 0


def test_build_rejects_malformed_reported_usage(tmp_path, monkeypatch):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [registry.Result(0)])
    monkeypatch.setattr(runtime, 'result', lambda job, *, root=None: registry.Result(0, {'usage': {'input_tokens': 'bad'}}))
    assert build.run_loop('A', str(brief), str(repo), root=tmp_path) == 2


def test_build_reports_unknown_item(tmp_path, monkeypatch, capsys):
    from wuwei.commands import build
    repo, brief, day, runtime = setup(tmp_path, monkeypatch, [])
    assert build.run_loop('missing', str(brief), str(repo), root=tmp_path) == 1
    assert 'build: unknown item missing' in capsys.readouterr().err


@pytest.mark.parametrize('maximum', [False, True])
def test_build_park_is_recorded_lintable_decision(tmp_path, monkeypatch, capsys, maximum):
    from wuwei import decision
    from wuwei.__main__ import main
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
    assert ('maximum build iterations reached' if maximum else 'same fast-check failure repeated') in capsys.readouterr().err
    path = decisions / 'D-2.md'
    assert path.exists()
    monkeypatch.chdir(tmp_path)
    assert main(['decision', 'lint', str(path)]) == 0
    assert (decisions / 'D-1.md').read_text() == 'preserve existing record'
    fields, _ = decision.evaluate(path.read_text())
    assert fields['Outcome'] == 'parked A'
    assert decision.route(fields) == 'seat'
    data = state.read_state(tmp_path)
    assert data['decision_outcomes']['D-2']['decided_by'] == 'seat'
    record = data['builds']['A']
    assert record['status'] == 'parked'
    assert tmp_path / record['action']['decision'] == path
