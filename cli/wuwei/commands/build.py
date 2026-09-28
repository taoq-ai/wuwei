"""Run a builder seat with fast-check backpressure."""

import hashlib
import json
from pathlib import Path
import re
import sys
import time

from wuwei import registry, state, workspace


def register(subparsers):
    parser = subparsers.add_parser('build', help='Run a builder until fast checks pass or it parks')
    parser.add_argument('item')
    parser.add_argument('brief')
    parser.add_argument('worktree')
    parser.set_defaults(func=run)


def run(args):
    return run_loop(args.item, args.brief, args.worktree)


class PortExit(Exception):
    def __init__(self, code, reason):
        self.code = code
        super().__init__(reason)


def _data(response, label):
    if not isinstance(response, registry.Result) or type(response.exit) is not int or response.exit not in (0, 1, 2):
        raise ValueError(f'invalid {label} result')
    if response.exit:
        raise PortExit(response.exit, response.reason or f'{label} returned {response.exit}')
    return response.data


def _signature(failures):
    normalized = []
    for name, data in failures:
        ids = data.get('test_ids', []) if isinstance(data, dict) else []
        error = data.get('error', '') if isinstance(data, dict) else ''
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids) or not isinstance(error, str):
            raise ValueError('malformed check failure data')
        if ids:
            error = '\n'.join(line for line in error.splitlines()
                              if line.startswith(('FAILED ', 'ERROR ')))
        error = re.sub(r'\bline\s+\d+\b', 'line N', error)
        error = re.sub(r'/(?:private/)?(?:tmp|var/folders/[^/\s]+/[^/\s]+/T)/\S+'
                       r'|\b\d+(?:\.\d+)?s\b|0x[0-9a-fA-F]+|pytest-\d+',
                       '<variable>', error)
        normalized.append([name, sorted(ids), ' '.join(error.split())])
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def _park(root, item, iteration, reason):
    directory = workspace.day_dir(root)
    decision = directory / 'decisions' / f'build-{item}.md'
    decision.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(decision, f'# Build parked: {item}\n\nIteration: {iteration}\nReason: {reason}\n')

    def update(data):
        if item not in data['items']:
            raise ValueError(f'unknown item: {item}')
        data['items'][item]['phase'] = 'parked'
        data['items'][item]['status'] = 'blocked'
    state._write_state(update, root, reserved=False, kind='build.parked',
                       payload={'item': item, 'iteration': iteration, 'reason': reason})


def run_loop(item, brief, worktree, *, root=None):
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        tree = Path(worktree).resolve(strict=True)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', item):
            print(f'build: invalid item {item}', file=sys.stderr)
            return 1
        if item not in state.read_state(root)['items']:
            print(f'build: unknown item {item}', file=sys.stderr)
            return 1
        repo = next((row for row in config['repos'] if (root / row['path']).resolve() == tree), None)
        if repo is None:
            from wuwei.guards.commit_push import context
            repo, _, _ = context(tree, {}, {}, root)
        if not repo['fast_checks']:
            raise ValueError('worktree has no configured fast checks')
        runtime = registry.load('runtime', config)
        checks = registry.load('checks', config)
        previous = None
        repeats = 0
        job = None
        for iteration in range(1, config['build']['max_iterations'] + 1):
            iteration_start = time.monotonic()
            if iteration == 1:
                job = _data(runtime.dispatch('builder', brief, str(tree), True, root=root), 'dispatch')
            else:
                job = _data(runtime.continue_job(job, feedback, root=root), 'continuation')
            deadline = time.monotonic() + config['build']['poll_timeout_seconds']
            while True:
                status = _data(runtime.status(job, root=root), 'status')
                if not isinstance(status, dict) or status.get('status') not in ('queued', 'running', 'completed', 'failed', 'cancelled'):
                    raise ValueError('invalid runtime status')
                if status['status'] == 'completed':
                    break
                if status['status'] in ('failed', 'cancelled'):
                    raise RuntimeError(f'runtime seat {status["status"]}')
                if time.monotonic() >= deadline:
                    raise TimeoutError('runtime seat timed out')
                time.sleep(config['build']['poll_interval_seconds'])
            result = _data(runtime.result(job, root=root), 'result')
            if not isinstance(result, dict):
                raise ValueError('invalid runtime result')
            reported = result.get('usage', {})
            if not isinstance(reported, dict):
                raise ValueError('malformed runtime usage')
            for key in ('input_tokens', 'output_tokens'):
                if key in reported and (type(reported[key]) is not int or reported[key] < 0):
                    raise ValueError('malformed runtime usage')
            if 'cost' in reported and (type(reported['cost']) not in (int, float) or reported['cost'] < 0):
                raise ValueError('malformed runtime usage')
            usage = {**reported, 'input_tokens': reported.get('input_tokens'),
                     'output_tokens': reported.get('output_tokens'),
                     'model': reported.get('model') or result.get('model') or status.get('model') or 'unreported',
                     'duration': time.monotonic() - iteration_start}
            state.append_event('seat.usage', {'item': item, 'role': 'builder', 'iteration': iteration,
                                              'usage': usage}, root=root)
            failures = []
            for command in repo['fast_checks']:
                check = checks.run(str(tree), command, root=root)
                if not isinstance(check, registry.Result) or type(check.exit) is not int or check.exit not in (0, 1, 2):
                    raise ValueError('invalid check result')
                if check.exit == 2:
                    raise RuntimeError(check.reason or 'fast check could not run')
                if check.exit == 1:
                    failures.append((command, check.data))
            if not failures:
                return 0
            signature = _signature(failures)
            repeats = repeats + 1 if signature == previous else 1
            previous = signature
            if repeats >= config['build']['stuck_after']:
                _park(root, item, iteration, 'same fast-check failure repeated')
                return 1
            feedback = '\n'.join(f'{name}: {data}' for name, data in failures)
        _park(root, item, config['build']['max_iterations'], 'maximum build iterations reached')
        return 1
    except PortExit as exc:
        print(f'build: {exc}', file=sys.stderr)
        return exc.code
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(f'build: {exc}', file=sys.stderr)
        return 2
