"""#685: the suite runs in parallel, the clock tests share one worker, and a seat can run only the tests a diff touches."""

import ast
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]

TIMING = {
    ('test_invariants.py', 'test_invariants_hold'),
    ('test_traces.py', 'test_large_arguments_record_under_50ms_cpu'),
    ('test_integrity.py', 'test_cached_check_latency'),
    ('test_heartbeat.py', 'test_stuck_state_lock_fails_the_state_probe'),
    ('test_adapters.py', 'test_watch_probe_runs_calls_together_and_times_out'),
    ('test_e2e_day.py', 'test_scripted_day'),
    ('test_path_day.py', 'test_the_day_closes_walking_only_next'),
    ('test_path_day.py', 'test_posture_day'),
    ('test_hooks.py', 'test_hook_latency'),
    ('test_hooks.py', 'test_status_line_latency'),
    ('test_hooks.py', 'test_workspace_hook_latency'),
    ('test_hooks.py', 'test_heartbeat_latency'),
}


WORKFLOW = (ROOT / '.github/workflows/tests.yml').read_text()
JOB = WORKFLOW[WORKFLOW.index('\n  test:'):WORKFLOW.index('\n  ziran-audit:')]


def test_ci_test_job_runs_in_parallel_and_reruns_only_flagged_timing_tests():
    for line in (
        'pip install pytest pytest-xdist',
        'python -m pytest -q -n auto --dist loadgroup',
        'continue-on-error: true',
        "if: steps.suite.outcome == 'failure'",
        "python - <<'EOF'",
    ):
        assert line in JOB
    assert 'needs:' not in WORKFLOW


def rerun(tmp_path, monkeypatch, failed):
    """Run the workflow's rerun step against a lastfailed cache; return its exit and the pytest args it used."""
    lines = JOB.split("python - <<'EOF'\n", 1)[1].splitlines()
    source = textwrap.dedent('\n'.join(lines[:[line.strip() for line in lines].index('EOF')]))
    if failed is not None:
        cache = tmp_path / '.pytest_cache/v/cache'
        cache.mkdir(parents=True)
        (cache / 'lastfailed').write_text(json.dumps(dict.fromkeys(failed, True)))
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pytest, 'main', lambda args: calls.append(args) or 0)
    try:
        exec(compile(source, 'rerun', 'exec'), {})
    except SystemExit as stop:
        return stop.code, calls
    except OSError:
        return 1, calls


def test_rerun_runs_only_the_failed_timing_tests_alone(tmp_path, monkeypatch):
    code, calls = rerun(tmp_path, monkeypatch, ['tests/test_a.py::test_t[x]@timing', 'tests/test_b.py::test_u@timing'])
    assert (code, calls) == (0, [['-q', 'tests/test_a.py::test_t[x]', 'tests/test_b.py::test_u']])


@pytest.mark.parametrize('failed', [
    ['tests/test_a.py::test_p'],
    ['tests/test_a.py::test_t@timing', 'tests/test_a.py::test_p'],
    ['tests/test_a.py'],
    [],
    None,
], ids=['plain', 'plain-and-timing', 'collection-error', 'empty-cache', 'no-cache'])
def test_rerun_never_retries_and_fails_on_anything_else(tmp_path, monkeypatch, failed):
    code, calls = rerun(tmp_path, monkeypatch, failed)
    assert code not in (0, None) and calls == []


def test_pyproject_has_xdist_as_dev_dependency_and_the_group_marker():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert 'pytest-xdist' in project['project']['optional-dependencies']['dev']
    assert any(m.startswith('xdist_group') for m in project['tool']['pytest']['ini_options']['markers'])


def timing_marked(path):
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.FunctionDef):
            for deco in node.decorator_list:
                if (isinstance(deco, ast.Call) and ast.unparse(deco.func) == 'pytest.mark.xdist_group'
                        and [ast.literal_eval(a) for a in deco.args] == ['timing']):
                    found.add((path.name, node.name))
    return found


def test_exactly_the_clock_tests_share_the_timing_group():
    marked = set().union(*(timing_marked(p) for p in (ROOT / 'tests').glob('test_*.py')))
    assert marked == TIMING


@pytest.fixture
def script():
    spec = spec_from_file_location('changed_tests', ROOT / 'scripts/changed_tests.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tree(tmp_path):
    for name, source in {
        'test_a.py': 'from wuwei import heartbeat\n\ndef fixture_x():\n    pass\n',
        'test_b.py': 'from test_a import fixture_x\n',
        'test_c.py': "PAGE = 'docs/site/reference.md'\n",
        'test_d.py': 'import json\n',
    }.items():
        (tmp_path / 'tests').mkdir(exist_ok=True)
        (tmp_path / 'tests' / name).write_text(source)
    return tmp_path


@pytest.mark.parametrize('paths,selected', [
    ({'tests/test_d.py'}, ['tests/test_d.py']),
    ({'cli/wuwei/heartbeat.py'}, ['tests/test_a.py', 'tests/test_b.py']),
    ({'docs/site/reference.md'}, ['tests/test_c.py']),
    ({'tests/conftest.py'}, ['tests']),
    ({'pyproject.toml', 'tests/test_d.py'}, ['tests']),
    ({'templates/unused.txt'}, []),
    ({'tests/test_gone.py'}, []),
])
def test_select_picks_the_tests_a_diff_touches(script, tree, paths, selected):
    assert script.select(paths, tree) == selected


def test_main_fails_closed_when_the_diff_cannot_be_read(script, monkeypatch, capsys):
    def changed(root):
        raise subprocess.CalledProcessError(128, ['git', 'diff'])
    monkeypatch.setattr(script, 'changed', changed)
    assert script.main([]) == 2
    assert 'cannot read the diff' in capsys.readouterr().err


def test_main_runs_nothing_when_nothing_is_selected(script, monkeypatch, capsys):
    monkeypatch.setattr(script, 'changed', lambda root: {'templates/unused.txt'})
    monkeypatch.setattr(script, 'select', lambda paths, root: [])
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('pytest ran'))
    assert script.main([]) == 0
    assert 'no test touched by the diff' in capsys.readouterr().out


def test_main_passes_args_to_pytest_and_returns_its_exit(script, monkeypatch):
    calls = []
    monkeypatch.setattr(script, 'changed', lambda root: {'tests/test_a.py'})
    monkeypatch.setattr(script, 'select', lambda paths, root: ['tests/test_a.py'])
    monkeypatch.setattr(subprocess, 'run', lambda argv, **k: calls.append(argv) or subprocess.CompletedProcess(argv, 1))
    assert script.main(['-x']) == 1
    assert calls == [[sys.executable, '-m', 'pytest', '-q', '-x', 'tests/test_a.py']]
