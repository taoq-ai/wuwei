"""In-process fixture replay, plus a PATH stub for subprocess smoke tests."""

import json
from pathlib import Path
import subprocess
import sys
import threading


FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'


def recordings(port):
    return json.loads((FIXTURES / port / 'recordings.json').read_text())


def pick(steps, used, argv):
    """Concurrent reads take the step whose 'when' tokens their argv names, else the next plain step."""
    matches = [index for index, step in enumerate(steps) if index not in used and (
        all(token in argv for token in step['when']) if 'when' in step else False)]
    plain = [index for index, step in enumerate(steps) if index not in used and 'when' not in step]
    index = (matches or plain or [None])[0]
    assert index is not None, f'no replay step for {argv}'
    used.add(index)
    return steps[index]


def replay(steps, tool):
    calls = []
    used = set()
    lock = threading.Lock()

    def run(argv, *, input=None, text=False, **kwargs):
        assert argv[0] == tool
        with lock:
            assert len(calls) < len(steps), 'unexpected extra call'
            step = pick(steps, used, argv)
            calls.append(argv)
        if 'argv' in step:
            assert argv[1:] == step['argv']
        if 'input' in step:
            assert json.loads(input) == step['input']
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
import fcntl, json, os, pathlib, sys, time
sys.path.insert(0, os.environ['REPLAY_FAKES'])
from replay import pick
calls = pathlib.Path(os.environ['REPLAY_CALLS'])
steps = json.loads(pathlib.Path(os.environ['REPLAY_CASSETTE']).read_text())
with open(str(calls) + '.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    seen = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    if len(seen) >= len(steps):
        sys.exit(98)
    used = set()
    for argv in seen:
        pick(steps, used, argv)
    step = pick(steps, used, sys.argv[1:])
    with calls.open('a') as stream:
        stream.write(json.dumps(sys.argv[1:]) + '\\n')
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
    monkeypatch.setenv('REPLAY_FAKES', str(Path(__file__).parent))
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
