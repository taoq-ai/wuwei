"""In-process fixture replay, plus a PATH stub for subprocess smoke tests."""

import json
from pathlib import Path
import subprocess
import sys


FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'


def recordings(port):
    return json.loads((FIXTURES / port / 'recordings.json').read_text())


def replay(steps, tool):
    calls = []

    def run(argv, *, input=None, text=False, **kwargs):
        assert argv[0] == tool
        assert len(calls) < len(steps), 'unexpected extra call'
        step = steps[len(calls)]
        if 'argv' in step:
            assert argv[1:] == step['argv']
        if 'input' in step:
            assert json.loads(input) == step['input']
        calls.append(argv)
        stdout, stderr = step.get('stdout', ''), step.get('stderr', '')
        if not text:
            stdout, stderr = stdout.encode(), stderr.encode()
        return subprocess.CompletedProcess(argv, step.get('exit', 0), stdout, stderr)

    run.calls = calls
    return run


def install_replay(monkeypatch, tool, steps):
    run = replay(steps, tool)
    monkeypatch.setattr(subprocess, 'run', run)
    return run.calls


def install_stub(tmp_path, monkeypatch, tool, steps):
    directory = tmp_path / 'tools'
    directory.mkdir(exist_ok=True)
    cassette = tmp_path / 'cassette.json'
    cassette.write_text(json.dumps(steps))
    calls = tmp_path / 'calls.jsonl'
    if calls.exists():
        calls.unlink()
    stub = directory / tool
    stub.write_text(f'#!{sys.executable}\n' + '''
import json, os, pathlib, sys, time
calls = pathlib.Path(os.environ['REPLAY_CALLS'])
index = len(calls.read_text().splitlines()) if calls.exists() else 0
with calls.open('a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
steps = json.loads(pathlib.Path(os.environ['REPLAY_CASSETTE']).read_text())
if index >= len(steps):
    sys.exit(98)
step = steps[index]
if 'argv' in step and sys.argv[1:] != step['argv']:
    print('unexpected argv', file=sys.stderr)
    sys.exit(99)
if 'input' in step and json.loads(sys.stdin.read()) != step['input']:
    sys.exit(97)
time.sleep(step.get('sleep', 0))
sys.stdout.write(step.get('stdout', ''))
sys.stderr.write(step.get('stderr', ''))
sys.exit(step.get('exit', 0))
''')
    stub.chmod(0o755)
    monkeypatch.setenv('PATH', str(directory))
    monkeypatch.setenv('REPLAY_CALLS', str(calls))
    monkeypatch.setenv('REPLAY_CASSETTE', str(cassette))
    return calls


class Recorder:
    """Record port calls and return independent copies of fixture-backed results."""

    def __init__(self, results=None):
        from copy import deepcopy
        from wuwei.registry import Result

        self.calls = []
        self.results = deepcopy(results) if results is not None else {
            case['operation']: Result(0, case['data']) for case in recordings(self.port)
        }

    def _call(self, operation, args, root):
        from copy import deepcopy
        from wuwei.registry import Result

        self.calls.append((operation, deepcopy(args), root))
        return deepcopy(self.results.get(operation, Result(2, None, 'unconfigured fake operation')))
