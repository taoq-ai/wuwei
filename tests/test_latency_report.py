"""#562: the latency job's report over this run's figures and the last green main run's."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/latency_report.py'
spec = spec_from_file_location('latency_report', SCRIPT)
report = module_from_spec(spec)
spec.loader.exec_module(report)


def row(probe, cpu, wall, budget=50, measure='cpu'):
    return {'probe': probe, 'cpu_ms': cpu, 'wall_ms': wall, 'budget_ms': budget, 'measure': measure,
            'floor_cpu_ms': 20.0, 'floor_wall_ms': 22.0, 'load': 1.0, 'cpus': 4}


def write(path, rows):
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    return str(path)


NOW = [row('status --line', 45.0, 60.0), row('PreToolUse', 24.0, 40.0),
       row('heartbeat tick', 30.0, 144.0, 200, 'wall'), row('new probe', 10.0, 20.0)]
LAST = [row('status --line', 30.0, 50.0), row('PreToolUse', 20.0, 35.0),
        row('heartbeat tick', 30.0, 120.0, 200, 'wall')]


def test_table_and_moved_most(tmp_path, capsys):
    code = report.main([write(tmp_path / 'now', NOW), write(tmp_path / 'last', LAST)])
    out = capsys.readouterr().out
    assert code == 1  # status --line at 45 of 50 is short of margin
    for probe in ('status --line', 'PreToolUse', 'heartbeat tick', 'new probe'):
        assert probe in out
    assert 'moved most: status --line +15.0 ms (+50%)' in out
    assert re.search(r'new probe .*-', out)
    assert 'margin short: status --line 5.0 ms' in out


def test_margins(tmp_path, capsys):
    held = [row('a', 30.0, 90.0), row('b', 60.0, 70.0, 100, 'wall')]
    assert report.main([write(tmp_path / 'held', held)]) == 0
    assert 'moved most' not in capsys.readouterr().out
    assert report.main([write(tmp_path / 'cpu', [row('a', 42.0, 90.0)])]) == 1
    assert 'margin short: a 8.0 ms' in capsys.readouterr().out
    assert report.main([write(tmp_path / 'wall', [row('b', 10.0, 85.0, 100, 'wall')])]) == 1
    assert 'margin short: b 15.0 ms' in capsys.readouterr().out
    assert report.main([write(tmp_path / 'over', [row('a', 55.0, 90.0)])]) == 1
    assert 'over budget: a' in capsys.readouterr().out


def test_previous_missing_or_malformed(tmp_path, capsys):
    current = write(tmp_path / 'now', [row('a', 30.0, 40.0)])
    assert report.main([current, str(tmp_path / 'absent')]) == 0
    assert 'no last green figures' in capsys.readouterr().out
    (tmp_path / 'bad').write_text('{not json\n')
    assert report.main([current, str(tmp_path / 'bad')]) == 0
    assert 'last green figures unreadable' in capsys.readouterr().out


def test_current_missing_or_malformed(tmp_path, capsys):
    assert report.main([str(tmp_path / 'absent')]) == 2
    assert 'latency report:' in capsys.readouterr().err
    (tmp_path / 'bad').write_text('[]\n')
    assert report.main([str(tmp_path / 'bad')]) == 2
    assert 'latency report:' in capsys.readouterr().err


def test_script_runs(tmp_path):
    result = subprocess.run([sys.executable, '-I', str(SCRIPT), write(tmp_path / 'now', [row('a', 30.0, 40.0)])],
                            text=True, capture_output=True)
    assert result.returncode == 0 and 'a' in result.stdout, result.stderr


def test_latency_job_keeps_and_compares_figures():
    text = (ROOT / '.github/workflows/tests.yml').read_text()
    job = text[text.index('\n  latency:'):text.index('\n  skill-evals:')]
    for needed in ('continue-on-error: true', 'WUWEI_BENCH: "1"', 'WUWEI_LATENCY_OUT: latency.jsonl',
                   'actions: read', 'actions/upload-artifact', 'name: latency',
                   'scripts/latency_report.py latency.jsonl previous/latency.jsonl'):
        assert needed in job, needed
    assert job.count('if: always()') >= 3
