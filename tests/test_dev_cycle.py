"""#685, #849: the suite runs in parallel, CI holds it under 3000 test functions, and a seat can run only the tests a diff touches."""

import ast
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]

WORKFLOW = (ROOT / '.github/workflows/tests.yml').read_text()
JOB = WORKFLOW[WORKFLOW.index('\n  test:'):WORKFLOW.index('\n  ziran-audit:')]


def test_ci_test_job_runs_in_parallel_with_no_timing_group():
    assert 'python -m pytest -q -n auto\n' in JOB
    assert 'pip install pytest pytest-xdist' in JOB
    assert 'loadgroup' not in JOB and 'timing' not in JOB and 'needs:' not in WORKFLOW


def count_step(tmp_path, monkeypatch, functions):
    """Run the workflow's count step over a tests/ tree holding that many test functions."""
    lines = JOB.split("python - <<'EOF'\n", 1)[1].splitlines()
    source = textwrap.dedent('\n'.join(lines[:[line.strip() for line in lines].index('EOF')]))
    (tmp_path / 'tests/sub').mkdir(parents=True)
    (tmp_path / 'tests/test_a.py').write_text('def test_x():\n    pass\n' * (functions - 1))
    (tmp_path / 'tests/sub/test_b.py').write_text('class TestB:\n    def test_y(self):\n        pass\n')
    monkeypatch.chdir(tmp_path)
    try:
        exec(compile(source, 'count', 'exec'), {})
    except SystemExit as stop:
        return stop.code
    return 0


@pytest.mark.parametrize('functions,failed', [(2999, False), (3000, True)])
def test_ci_fails_at_3000_test_functions(tmp_path, monkeypatch, capsys, functions, failed):
    assert bool(count_step(tmp_path, monkeypatch, functions)) is failed
    assert f'{functions} test functions' in capsys.readouterr().out


def test_pyproject_has_xdist_as_dev_dependency_and_no_group_marker():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert 'pytest-xdist' in project['project']['optional-dependencies']['dev']
    assert 'markers' not in project['tool']['pytest']['ini_options']


def test_no_test_shares_an_xdist_group():
    # #849: no clock test is left to pin to one worker.
    grouped = [(path.name, node.name) for path in (ROOT / 'tests').glob('test_*.py')
               for node in ast.walk(ast.parse(path.read_text()))
               if isinstance(node, ast.FunctionDef) and any(
                   isinstance(deco, ast.Call) and ast.unparse(deco.func) == 'pytest.mark.xdist_group'
                   for deco in node.decorator_list)]
    assert grouped == []


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
