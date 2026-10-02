"""Select one build action; only Codex seats are polled by the CLI."""

import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import sys
import time

from wuwei import registry, state, workspace


def register(subparsers):
    parser = subparsers.add_parser('build', help='Select the next builder action')
    parser.add_argument('operation', help='next, check, or legacy Codex item')
    parser.add_argument('arguments', nargs='*', metavar='item/brief/worktree')
    parser.set_defaults(func=run)


def run(args):
    try:
        if args.operation in ('next', 'check'):
            root = workspace.find_workspace()
            if len(args.arguments) not in ((1, 3) if args.operation == 'next' else (1,)):
                raise ValueError('usage: build next <item> [<brief> <worktree>] or build check <item>')
            item, *paths = args.arguments
            if args.operation == 'check':
                code = check(item, root=root)
                if code == 1:
                    action = state.read_state(root).get('builds', {}).get(item, {}).get('action', {})
                    if action.get('action') == 'park':
                        print(f'build: parked {item}: {action["reason"]}; decision {action["decision"]}', file=sys.stderr)
                    elif action.get('action') == 'continue':
                        print(action['feedback'], file=sys.stderr)
                return code
            print(json.dumps(next_action(item, *paths, root=root)))
            return 0
        if len(args.arguments) not in (0, 2):
            raise ValueError('usage: build next <item> or build <item> <brief> <worktree> (Codex only)')
        return run_loop(args.operation, *(args.arguments or [None, None]))
    except PortExit as exc:
        print(f'build: {exc}', file=sys.stderr)
        return exc.code
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'build: {exc}', file=sys.stderr)
        return 2


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


def _repo(root, tree, config):
    repo = next((row for row in config['repos'] if (root / row['path']).resolve() == tree), None)
    if repo is None:
        from wuwei.guards.commit_push import context
        repo, _, _ = context(tree, {}, {}, root, identity=False)
    if not repo['fast_checks']:
        raise ValueError('worktree has no configured fast checks')
    return repo


def _save(item, record, root, kind, expected):
    def update(data):
        builds = data.setdefault('builds', {})
        if builds.get(item) != expected:
            raise ValueError('build changed before recording action')
        builds[item] = record
    state._write_state(update, root, reserved=False, kind=kind, payload={'item': item})


def next_action(item, brief=None, worktree=None, *, root=None):
    """Return one stable action. Executing it belongs to the caller."""
    from wuwei.brief import events, identifier, seat_action
    root = workspace.find_workspace(root)
    identifier(item)
    data = state.read_state(root)
    if item not in data['items']:
        raise PortExit(2, f'unknown item {item}')
    record = data.get('builds', {}).get(item)
    if record is not None and record['status'] == 'running':
        raise ValueError('builder is still running; call build next after its stop hook')
    config = workspace.load_config(root)
    if brief is None:
        matches = [row['payload'] for row in events(root) if row['kind'] == 'brief written'
                   and row['payload'].get('item') == item and row['payload'].get('role') == 'builder']
        if not matches:
            raise ValueError('no logged builder brief for item')
        brief = root / matches[-1]['path']
        worktree = matches[-1].get('worktree') or data['items'][item].get('worktree')
    if worktree is None:
        raise ValueError('builder brief needs a worktree')
    tree = (root / worktree).resolve(strict=True)
    path = (root / brief).resolve(strict=True)
    if record is not None:
        if str(path.relative_to(root)) == record['brief'] and str(tree) == record['worktree']:
            return record['action']
        if record['status'] not in ('done', 'parked'):
            raise ValueError('cannot replace an unfinished build with a new brief')
        if data['items'][item]['phase'] in ('parked', 'escalated'):
            raise ValueError('resume the parked item before starting a new build')
    repo = _repo(root, tree, config)
    action = seat_action('builder', path, tree, root)
    previous = record
    record = {'brief': str(path.relative_to(root)), 'worktree': str(tree),
              'runtime': action['runtime'], 'repo': repo['name'],
              'commands': repo['fast_checks'], 'iteration': 0, 'repeats': 0,
              'signature': None, 'status': 'ready', 'action': action}
    _save(item, record, root, 'build.started', previous)
    if data['items'][item]['phase'] == 'planned':
        state.transition(item, 'implement', root)
    if previous is None:
        from wuwei import dispatch
        dispatch.tracker_call(item, 'claim', root)
    return action


def open_fix(item, feedback, *, root):
    """Resume the linked builder once with measured gate or PR feedback."""
    from wuwei.brief import launch_prompt
    from wuwei.security import agent_path
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError('fix round needs measured feedback')
    data = state.read_state(root)
    if item not in data['items']:
        raise ValueError(f'unknown item {item}')
    record = data.get('builds', {}).get(item)
    if record is None:
        next_action(item, root=root)
        data = state.read_state(root)
        record = data.get('builds', {}).get(item)
    if data['items'][item]['phase'] == 'fix' and record is not None:
        if record['status'] == 'ready':
            return next_action(item, root / record['brief'], record['worktree'], root=root)
        if record['status'] in ('running', 'check'):
            return {'action': 'wait', 'item': item, 'status': record['status']}
    if record is None or record['status'] not in ('done', 'ready'):
        raise ValueError('fix round needs a completed or ready build')
    if record.get('fix_rounds', 0) >= 1:
        raise ValueError('fix round budget exhausted')
    phase = data['items'][item]['phase']
    if phase not in ('gate', 'raised'):
        raise ValueError('fix round needs a gated or raised item')
    brief = root / record['brief']
    resume = record.get('agent_id') or record.get('job')
    if not resume and (record['status'] == 'done' or record['runtime'] == 'codex'):
        from wuwei import brief as brief_writer
        body = f'Read the original builder brief {record["brief"]}.\n\nFix feedback:\n{feedback}'
        relative = brief_writer.write('builder', item, f'{item}-{"gate" if phase == "gate" else "pr"}-fix', body,
                                      worktree=record['worktree'],
                                      pr=data['items'][item].get('pr'), root=root)
        brief = root / relative
    prompt = launch_prompt(brief, agent_path(root, 'builder'), root=root) + '\n\n' + feedback
    action = {'action': 'continue' if resume else 'launch',
              'feedback': feedback, 'prompt': prompt, 'agent_type': 'wuwei:builder',
              'runtime': record['runtime'], 'brief': str(brief),
              'worktree': record['worktree']}
    if record.get('agent_id'):
        action['resume'] = record['agent_id']
    def update(fresh):
        if fresh.get('builds', {}).get(item) != record:
            raise ValueError('build changed before fix round')
        fresh['items'][item]['phase'] = 'fix'
        fresh['builds'][item] = {**record, 'brief': str(brief.relative_to(root)),
                                 'status': 'ready', 'action': action,
                                 'fix_rounds': 1, 'iteration': 0, 'repeats': 0,
                                 'signature': None}
    state._write_state(update, root, reserved=False, kind='build.fix_opened',
                       payload={'item': item})
    return next_action(item, brief, record['worktree'], root=root)


def started(data, item, name):
    """Bind a Claude iteration inside the existing seat reservation transaction."""
    record = data.get('builds', {}).get(item)
    if record is None:
        return
    if record['status'] != 'ready' or record['action']['action'] not in ('launch', 'continue'):
        raise ValueError('build is not ready for a seat')
    if data['seats'][name]['brief'] != record['brief']:
        raise ValueError('seat brief differs from active build')
    record.update(status='running', seat=name, started_at=workspace.now().isoformat())


def normalize_usage(reported, model):
    """Validate reported seat usage into the five measured keys."""
    if not isinstance(reported, dict):
        raise ValueError('malformed runtime usage')
    for key in ('input_tokens', 'output_tokens'):
        if key in reported and (type(reported[key]) is not int or reported[key] < 0):
            raise ValueError('malformed runtime usage')
    for key in ('cost', 'duration'):
        if key in reported and (type(reported[key]) not in (int, float)
                                or not math.isfinite(reported[key]) or reported[key] < 0):
            raise ValueError('malformed runtime usage')
    if 'model' in reported and (not isinstance(reported['model'], str) or not reported['model']):
        raise ValueError('malformed runtime usage')
    usage = {key: reported.get(key, 'unmeasured')
             for key in ('input_tokens', 'output_tokens', 'cost', 'model', 'duration')}
    if usage['model'] == 'unmeasured':
        usage['model'] = model or 'unmeasured'
    return usage


def record_result(item, result, *, root, agent_id=None, model=None, completion=None, expected=None):
    record = expected if expected is not None else state.read_state(root)['builds'][item]
    if record['status'] != 'running':
        return
    if not isinstance(result, dict):
        raise ValueError('invalid runtime result')
    usage = normalize_usage(result.get('usage', {}), result.get('model') or model)
    iteration = record['iteration'] + 1
    # The result and usage share the writer lock, so duplicate hooks cannot charge twice.
    def update(data):
        current = data['builds'][item]
        if current != record:
            raise ValueError('build changed during result recording')
        if agent_id is not None:
            data['seats'][record['seat']]['status'] = 'stopped'
        current.update(status='check', iteration=iteration, agent_id=agent_id, completion=completion,
                       result=result, action={'action': 'check',
                       'command': 'wuwei build check ' + shlex.quote(item),
                       'worktree': record['worktree'], 'checks': record['commands']})
    updated = state._write_state(update, root, reserved=False, kind='seat.usage',
                       payload={'item': item, 'role': 'builder', 'iteration': iteration, 'usage': usage})
    if agent_id is not None:
        state.append_event('seat stopped', {'name': record['seat']}, root)
    return updated['builds'][item]


def check_binding(item, record):
    return {'item': item, 'brief': record['brief'], 'iteration': record['iteration'] + 1}


def stopped(item, name, payload, *, root):
    """Accept only the hook-bound seat result and current measured check evidence."""
    data = state.read_state(root)
    record = data.get('builds', {}).get(item)
    if record is None or record.get('seat') != name:
        return False
    if record['status'] != 'running':
        return True
    agent_id = payload.get('agent_id')
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError('SubagentStop omitted builder agent_id')
    if record.get('agent_id') and record['agent_id'] != agent_id:
        raise ValueError('SubagentStop agent_id differs from resumed builder')
    text = payload.get('last_assistant_message')
    if not isinstance(text, str):
        raise ValueError('SubagentStop omitted builder result')
    completion, message = None, None
    for index, line in enumerate(Path(payload['agent_transcript_path']).read_text().splitlines()):
        row = json.loads(line)
        if row.get('type') == 'assistant':
            content = row['message']['content']
            message = ('\n'.join(part['text'] for part in content if part.get('type') == 'text')
                       if isinstance(content, list) else content)
            completion = [index, hashlib.sha256(line.encode()).hexdigest()]
    if completion is None or not isinstance(message, str) or message.strip() != text.strip():
        raise ValueError('SubagentStop has no matching assistant completion')
    if completion == record.get('completion'):
        return True
    reported = payload.get('usage', {})
    if isinstance(reported, dict):
        reported = {**{key: payload[source] for key, source in (
            ('input_tokens', 'total_input_tokens'), ('output_tokens', 'total_output_tokens'),
            ('duration', 'duration_seconds'), ('model', 'model')) if source in payload}, **reported}
        if 'duration' not in reported and 'duration_ms' in payload:
            milliseconds = payload['duration_ms']
            if type(milliseconds) not in (int, float) or not math.isfinite(milliseconds) or milliseconds < 0:
                raise ValueError('malformed runtime usage')
            reported['duration'] = milliseconds / 1000
    expected = record_result(item, {'text': text, 'usage': reported},
                             root=root, agent_id=agent_id, completion=completion, expected=record)
    measured = data.get('fast_checks', {}).get(record['repo'], {})
    rows = [measured.get(command, {}) for command in record['commands']]
    if not all(row.get('build') == check_binding(item, record)
               and row.get('worktree') == record['worktree'] and row.get('clean') is True
               and 'data' in row for row in rows):
        return True
    vcs = registry.load('vcs', workspace.load_config(root))
    head = _data(vcs.head(record['worktree'], root=root), 'HEAD')['sha']
    from wuwei.brief import status
    if not all(row.get('sha') == head for row in rows) or status(vcs, record['worktree'], root):
        return True
    complete_checks(item, [registry.Result(row['exit'], row.get('data'), row.get('reason', ''))
                           for row in rows], root=root, expected=expected)
    return True


def complete_checks(item, results, *, root, expected=None):
    if expected is None:
        expected = state.read_state(root)['builds'][item]
    record = dict(expected)
    if record['status'] != 'check':
        raise ValueError('build is not awaiting checks')
    failures = []
    if len(results) != len(record['commands']):
        raise ValueError('incomplete fast checks')
    for command, result in zip(record['commands'], results):
        if not isinstance(result, registry.Result) or type(result.exit) is not int or result.exit not in (0, 1, 2):
            raise ValueError('invalid check result')
        if result.exit == 2:
            raise ValueError(result.reason or 'fast check could not run')
        if result.exit == 1:
            if isinstance(result.data, dict) and 'environment' in result.data:
                reason = result.data['environment']
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError('invalid environment check reason')
                _park(root, item, record, f'environment: {reason}', expected)
                return 1
            failures.append((command, result.data))
    if not failures:
        record.update(status='done', action={'action': 'done'})
    else:
        signature = _signature(failures)
        record['repeats'] = record['repeats'] + 1 if signature == record['signature'] else 1
        record['signature'] = signature
        config = workspace.load_config(root)
        reason = ('same fast-check failure repeated' if record['repeats'] >= config['build']['stuck_after']
                  else 'maximum build iterations reached' if record['iteration'] >= config['build']['max_iterations'] else None)
        if reason:
            _park(root, item, record, reason, expected)
            return 1
        from wuwei.brief import launch_prompt
        from wuwei.security import agent_path
        feedback = '\n'.join(f'{name}: {json.dumps(data)}' for name, data in failures)
        action = {'action': 'continue', 'feedback': feedback, 'resume': record.get('agent_id'),
                  'agent_type': 'wuwei:builder',
                  'prompt': launch_prompt(root / record['brief'], agent_path(root, 'builder'), root=root) + '\n\n' + feedback}
        record.update(status='ready', action=action)
    _save(item, record, root, 'build.checked', expected)
    after = {'implement': 'gate', 'fix': 'delta'}.get(state.read_state(root)['items'][item]['phase'])
    if not failures and after:
        state.transition(item, after, root)
    return 1 if failures else 0


def check(item, *, root=None):
    root = workspace.find_workspace(root)
    record = state.read_state(root).get('builds', {}).get(item)
    if record is None or record['status'] != 'check':
        raise ValueError('build is not awaiting checks')
    from wuwei import fast_checks
    fast_checks.record(record['worktree'])
    measured = state.read_state(root).get('fast_checks', {}).get(record['repo'], {})
    if any(command not in measured for command in record['commands']):
        raise ValueError('incomplete fast checks')
    results = [registry.Result(row['exit'], row.get('data'), row.get('reason') or '')
               for row in (measured[command] for command in record['commands'])]
    return complete_checks(item, results, root=root, expected=record)


def _park(root, item, record, reason, expected):
    from wuwei import decision
    text = (
        f'Question: Park build {item}?\nContext: Iteration {record["iteration"]}: {reason}.\n'
        'Options:\n| Option | Description |\n| --- | --- |\n'
        '| defer | Defer work until the failure is investigated |\n'
        '| retry | Continue spending the build budget |\n'
        'Musts:\n| Criterion | defer | retry |\n| --- | --- | --- |\n'
        '| Respect iteration limits | pass | fail |\n'
        'Wants:\n| Criterion | Weight | defer | retry |\n| --- | --- | --- | --- |\n'
        '| Preserve budget | 10 | 10 | 0 |\n'
        'Recommendation: defer\nConfidence: high\nReversibility: two-way\n'
        'Blast radius: own branch\nPre-mortem: Repeated failures consume the remaining budget.\n'
        'Revisit: After investigating the failure and revising the brief.\n'
        f'Decided-by: seat\nOutcome: parked {item}\n')
    def update(data):
        if data['builds'][item] != expected:
            raise ValueError('build changed before parking')
        path = decision.write(text, root)
        data.setdefault('decision_outcomes', {})[path.stem] = decision.seat_outcome(*decision.evaluate(text))
        record.update(status='parked', action={'action': 'park', 'reason': reason,
                                               'decision': str(path.relative_to(root))})
        data['builds'][item] = record
        data['items'][item].update(phase='parked', status='blocked')
    state._write_state(update, root, reserved=False, kind='build.parked',
                       payload={'item': item, 'iteration': record['iteration'], 'reason': reason})


def wait(runtime, job, config, root):
    """Poll a runtime job until it completes; return its last status."""
    deadline = time.monotonic() + config['build']['poll_timeout_seconds']
    while True:
        status = _data(runtime.status(job, root=root), 'status')
        if not isinstance(status, dict) or status.get('status') not in ('queued', 'running', 'completed', 'failed', 'cancelled'):
            raise ValueError('invalid runtime status')
        if status['status'] == 'completed':
            return status
        if status['status'] in ('failed', 'cancelled'):
            raise RuntimeError(f'runtime seat {status["status"]}')
        if time.monotonic() >= deadline:
            raise TimeoutError('runtime seat timed out')
        time.sleep(config['build']['poll_interval_seconds'])


def run_loop(item, brief, worktree, *, root=None):
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        runtime_config = registry.runtime_config('builder', config, root)
        if runtime_config['adapters']['runtime'] == 'claude':
            raise ValueError('Claude builders require build next <item> in the planner session')
        if brief is None or worktree is None:
            raise ValueError('usage: build <item> <brief> <worktree> (Codex only)')
        runtime = registry.load('runtime', runtime_config)
        while True:
            record = state.read_state(root).get('builds', {}).get(item)
            if record and record['status'] == 'running' and record.get('job'):
                job = record['job']
            else:
                action = next_action(item, brief, worktree, root=root)
                if action['action'] == 'done':
                    return 0
                if action['action'] == 'park':
                    print(f'build: parked {item}: {action["reason"]}; decision {action["decision"]}', file=sys.stderr)
                    return 1
                if action['action'] == 'check':
                    check(item, root=root)
                    continue
                record = state.read_state(root)['builds'][item]
                if action['action'] == 'launch':
                    job = _data(runtime.dispatch('builder', brief, worktree, True, root=root), 'dispatch')
                else:
                    job = _data(runtime.continue_job(record['job'], action['feedback'], root=root), 'continuation')
                previous = dict(record)
                record.update(status='running', job=job, started_at=workspace.now().isoformat())
                _save(item, record, root, 'build.launched', previous)
            status = wait(runtime, job, config, root)
            record_result(item, _data(runtime.result(job, root=root), 'result'),
                          root=root, model=status.get('model'))
    except PortExit as exc:
        print(f'build: {exc}', file=sys.stderr)
        return exc.code
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'build: {exc}', file=sys.stderr)
        return 2
