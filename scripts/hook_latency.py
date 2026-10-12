"""Hook latency figures for the informational latency job (#346, #562, #805, #849).

Usage: WUWEI_LATENCY_OUT=latency.jsonl python scripts/hook_latency.py
Runs each probe 60 times and prints its p95 CPU and wall ms beside the python3 -I startup
floor. With WUWEI_LATENCY_OUT set, it appends one JSON row per probe, which
scripts/latency_report.py compares with the last green run and warns on. Nothing here asserts a
duration. The probes run under pytest for the tests' fixtures; the exit is pytest's, nonzero only
when a probed hook itself fails.
"""

import json
import os
from pathlib import Path
from resource import RUSAGE_CHILDREN, getrusage
from statistics import quantiles
import subprocess
import sys
from time import perf_counter

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'cli'), str(ROOT)]
from test_hooks import fixture, seeded_workspace, subprocess_plugin, subprocess_replay  # noqa: E402,F401

RUNS = 60


def timed(run, runs=RUNS, before=lambda: None):
    """p95 CPU and wall ms of run(), each run after before() and outside its figures."""
    cpu, wall = [], []
    for _ in range(runs):
        before()
        start_cpu, start = getrusage(RUSAGE_CHILDREN), perf_counter()
        run()
        wall.append(perf_counter() - start)
        end_cpu = getrusage(RUSAGE_CHILDREN)
        cpu.append(end_cpu.ru_utime - start_cpu.ru_utime + end_cpu.ru_stime - start_cpu.ru_stime)
    return quantiles(cpu, n=100)[94] * 1000, quantiles(wall, n=100)[94] * 1000


def startup_floor(runs):
    """p95 CPU and wall ms of a bare interpreter start, the floor under every hook figure."""
    return timed(lambda: subprocess.run([sys.executable, '-I', '-c', 'pass'], check=True), runs)


def record(name, cpu_ms, wall_ms, *, wall_budget=None, runs=RUNS, floor=startup_floor):
    load, cpus = os.getloadavg()[0], os.cpu_count() or 1
    floor_cpu, floor_wall = floor(runs)
    print(f'{name} p95 over {runs} runs: CPU {cpu_ms:.2f} ms, wall {wall_ms:.2f} ms, '
          f'python3 -I startup floor CPU {floor_cpu:.2f} ms, wall {floor_wall:.2f} ms, '
          f'load {load:.2f} on {cpus} CPUs')
    if out := os.environ.get('WUWEI_LATENCY_OUT'):
        with open(out, 'a', encoding='utf-8') as file:
            file.write(json.dumps({'probe': name, 'cpu_ms': cpu_ms, 'wall_ms': wall_ms,
                                   'budget_ms': 50 if wall_budget is None else wall_budget,
                                   'measure': 'cpu' if wall_budget is None else 'wall',
                                   'floor_cpu_ms': floor_cpu, 'floor_wall_ms': floor_wall,
                                   'load': load, 'cpus': cpus}) + '\n')


def succeeded(result):
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result


@pytest.mark.parametrize('event', ['PreToolUse', 'PostToolUse'])
def probe_hook(subprocess_plugin, event):
    name = 'bash' if event == 'PreToolUse' else 'example'
    payload = (ROOT / f'tests/payloads/{event}/{name}.json').read_text()
    record(event, *timed(lambda: succeeded(subprocess_replay(subprocess_plugin, event, payload))))


def probe_status_line(subprocess_plugin):
    root, env = subprocess_plugin
    env['WUWEI_NOW'] = '2026-09-28T12:00:00+02:00'
    directory = root.parent / '.wuwei/days/2026-09-28'
    directory.mkdir(parents=True)
    (directory / 'state.json').write_text('{"items":{},"cap":1}\n')
    kinds = ('state.write', 'state.set', 'state.transition', 'seat launched',
             'brief written', 'fast_checks.record', 'seat stopped', 'retro.captured')
    (directory / 'events.jsonl').write_text(''.join(
        json.dumps({'kind': kinds[index % len(kinds)], 'payload': {'detail': 'x' * 400},
                    'ts': '2026-09-28T12:00:00+02:00'}) + '\n' for index in range(10000)))
    record('status --line', *timed(lambda: succeeded(subprocess.run(
        [str(root / 'bin/wuwei'), 'status', '--line'], capture_output=True, text=True,
        cwd=root.parent, env=env))))


@pytest.mark.parametrize('path', ['SubagentStop', 'SessionStart', 'commit', 'push'])
def probe_workspace_hook(seeded_workspace, path):
    plugin, payloads, reset, calls = seeded_workspace
    event, fields = payloads[path]
    payload = json.dumps({**fixture(event), **fields})
    record(f'{path} in a workspace', *timed(
        lambda: succeeded(subprocess_replay(plugin, event, payload)), before=reset), wall_budget=100)
    if calls.exists():
        raise RuntimeError(f'{path} called gh: {calls.read_text()}')


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q', '-s', '-p', 'no:cacheprovider', '--rootdir', str(ROOT),
                          '-o', 'python_files=hook_latency.py', '-o', 'python_functions=probe_*']))
