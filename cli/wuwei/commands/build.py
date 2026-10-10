"""Select one build action; only Codex seats are polled by the CLI."""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import time

from wuwei import registry, state, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED, PAYLOAD, RACE


def register(subparsers):
    parser = subparsers.add_parser('build', help='Select the next builder action')
    parser.add_argument('operation', help='next, check, or legacy Codex item')
    parser.add_argument('arguments', nargs='*', metavar='item/brief/worktree')
    parser.set_defaults(func=run)


def parked_line(item, action):
    """#661: a parked item names its card, never a host-terminal command."""
    ident = Path(action['decision']).stem
    return (f'build: parked {item}: {action["reason"]}; decision {ident}; ask the owner with '
            f'bin/wuwei decision show {ident} --widget and run its record command, then resume the item')


def run(args):
    try:
        if args.operation in ('next', 'check'):
            root = workspace.find_workspace()
            if len(args.arguments) not in ((1, 3) if args.operation == 'next' else (1,)):
                raise ValueError('usage: build next <item> [<brief> <worktree>] or build check <item>; run bin/wuwei build next <item> for the next builder action. Run bin/wuwei build check <item> after the builder stops')
            item, *paths = args.arguments
            if args.operation == 'check':
                code = check(item, root=root)
                if code == 1:
                    action = state.read_state(root).get('builds', {}).get(item, {}).get('action', {})
                    if action.get('action') == 'park':
                        print(parked_line(item, action), file=sys.stderr)
                    elif action.get('action') == 'continue':
                        print(action['feedback'], file=sys.stderr)
                return code
            action = next_action(item, *paths, root=root)
            if action['action'] == 'done' and state.read_state(root)['items'][item]['phase'] in ('gate', 'delta'):
                from wuwei import dispatch  # #666: past the build, answer what dispatch next decides
                try:
                    action = dispatch.next_step(item, root)
                except dispatch.Refused as exc:
                    print(f'build: {exc}', file=sys.stderr)
                    return 1
                if action['action'] == 'fix':  # the round just opened: its builder action
                    action = state.read_state(root)['builds'][item]['action']
            print(json.dumps(action))
            return 1 if action['action'] == 'escalate' else 0
        if len(args.arguments) not in (0, 2):
            raise ValueError('usage: build next <item> or build <item> <brief> <worktree> (Codex only); use bin/wuwei build next <item> for a Claude builder. Use bin/wuwei build <item> <brief> <worktree> for a Codex builder')
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
        raise ValueError(f'invalid {label} result; {DAMAGED}')
    if response.exit:
        raise PortExit(response.exit, response.reason or f'{label} returned {response.exit}')
    return response.data


def _signature(failures):
    normalized = []
    for name, data in failures:
        ids = data.get('test_ids', []) if isinstance(data, dict) else []
        error = data.get('error', '') if isinstance(data, dict) else ''
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids) or not isinstance(error, str):
            raise ValueError(f'malformed check failure data; {DAMAGED}')
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
    # #600: no fast checks is a state (CI and the gates are the evidence); strict asks once
    from wuwei import calibrate
    name = repo['name']
    if (not repo['fast_checks'] and workspace.posture(config)[0] == 'strict'
            and not calibrate.checks_answered(root, name)):
        raise ValueError(f'posture strict: {name} has no fast checks and no answer on its fast-checks card; ask it with wuwei calibrate --questions --repo {name}, then rerun bin/wuwei build next <item>')
    return repo


def _save(item, record, root, kind, expected, extra=None):
    def update(data):
        builds = data.setdefault('builds', {})
        if builds.get(item) != expected:
            raise ValueError(f'build changed before recording action; {RACE}')
        builds[item] = record
    state._write_state(update, root, reserved=False, kind=kind, payload={'item': item, **(extra or {})})


def _busy(item, record):
    marker = state.check_running(record)
    if marker:
        raise ValueError(f'fast checks for {item} are running since {marker["started_at"][11:16]} (pid {marker["pid"]}); run bin/wuwei build next {item} when that command exits')


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
        raise ValueError(f'builder is still running; wait for its stop hook, then run bin/wuwei build next {item}')
    if record is not None:
        _busy(item, record)
    config = workspace.load_config(root)
    if brief is None:
        matches = [row['payload'] for row in events(root) if row['kind'] == 'brief written'
                   and row['payload'].get('item') == item and row['payload'].get('role') == 'builder']
        if not matches:
            raise ValueError(f'no logged builder brief for {item}; write one with bin/wuwei brief, or pass the paths: bin/wuwei build next {item} <brief> <worktree>')
        brief = root / matches[-1]['path']
        worktree = matches[-1].get('worktree') or data['items'][item].get('worktree')
    if worktree is None:
        raise ValueError(f'builder brief needs a worktree; create one with bin/wuwei worktree add {item} and pass it with --worktree. Or run bin/wuwei build next {item} <brief> <worktree>')
    tree = (root / worktree).resolve(strict=True)
    path = (root / brief).resolve(strict=True)
    if record is not None:
        if str(path.relative_to(root)) == record['brief'] and str(tree) == record['worktree']:
            return record['action']
        if record['status'] not in ('done', 'parked'):
            raise ValueError(f'cannot replace an unfinished build with a new brief; run bin/wuwei build next {item} to finish it first')
        if data['items'][item]['phase'] in ('parked', 'escalated'):
            raise ValueError(f'{item} is parked; resume the parked item before starting a new build (answer its decision, then run bin/wuwei build next {item})')
    from wuwei import tracker
    status, reason = tracker.check(data, config, item, data['items'][item])
    if status == 'missing':
        raise PortExit(1, reason)
    repo = _repo(root, tree, config)
    action = seat_action('builder', path, tree, root)
    previous = record
    from wuwei import fast_checks  # #600: no fast checks still runs repos.tests at careful pace
    commands = repo['fast_checks'] or fast_checks.commands(root, config, repo, tree)
    record = {'brief': str(path.relative_to(root)), 'worktree': str(tree),
              'runtime': action['runtime'], 'repo': repo['name'],
              'commands': commands, 'iteration': 0, 'repeats': 0,
              'signature': None, 'status': 'ready', 'action': action}
    _save(item, record, root, 'build.started', previous,
          None if commands else {'checks': 'none configured'})
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
        raise ValueError('fix round needs measured feedback; run the gates first, then pass their findings to the fix round')
    data = state.read_state(root)
    if item not in data['items']:
        raise ValueError(f'unknown item {item}; check the name with bin/wuwei status, or admit it with bin/wuwei plan add {item}')
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
        raise ValueError(f'fix round needs a completed or ready build; run bin/wuwei build next {item} for the current step')
    from wuwei import dispatch
    cap = dispatch.max_rounds(workspace.load_config(root), data['items'][item])
    used = dispatch.rounds_used(data, item)
    if used >= cap:  # #623: one round cap for gate and PR fixes alike
        raise ValueError(f'round cap {cap} reached (gates.max_rounds); park {item} for the owner (bin/wuwei why {item} shows the rounds)')
    phase = data['items'][item]['phase']
    if phase not in ('gate', 'raised', 'delta'):
        raise ValueError(f'fix round needs a gated, delta or raised item; run bin/wuwei dispatch next {item} for its current step')
    brief = root / record['brief']
    resume = record.get('agent_id') or record.get('job')
    if not resume and (record['status'] == 'done' or record['runtime'] == 'codex'):
        from wuwei import brief as brief_writer
        body = f'Read the original builder brief {record["brief"]}.\n\nFix feedback:\n{feedback}'
        name = f'{item}-{"pr" if phase == "raised" else "gate"}-fix' + (f'-{used + 1}' if used else '')
        relative = brief_writer.write('builder', item, name, body,
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
            raise ValueError(f'build changed before fix round; run bin/wuwei build next {item} again')
        if phase == 'delta':
            dispatch.rotate(fresh, item, used)
        fresh['items'][item]['phase'] = 'fix'
        fresh['builds'][item] = {**record, 'brief': str(brief.relative_to(root)),
                                 'status': 'ready', 'action': action,
                                 'fix_rounds': used + 1, 'iteration': 0, 'repeats': 0,
                                 'signature': None}
    state._write_state(update, root, reserved=False, kind='build.fix_opened',
                       payload={'item': item, 'round': used + 1, 'cap': cap})
    return next_action(item, brief, record['worktree'], root=root)


def started(data, item, name, fresh=False):
    """Bind a Claude iteration inside the existing seat reservation transaction. fresh (#614):
    a new agent continues the round, so the replaced agent's id and transcript binding go."""
    record = data.get('builds', {}).get(item)
    if record is None:
        return
    if record['status'] != 'ready' or record['action']['action'] not in ('launch', 'continue'):
        raise ValueError(f'build is not ready for a seat; run bin/wuwei build next {item} for the current step (bin/wuwei why {item} explains it)')
    if data['seats'][name]['brief'] != record['brief']:
        raise ValueError(f'seat brief differs from active build; start the seat with the brief that bin/wuwei build next {item} returned')
    if fresh:
        record['replaced'] = record.pop('agent_id', None)
        record.pop('completion', None)
    record.update(status='running', seat=name, started_at=workspace.now().isoformat())


def normalize_usage(reported, model):
    """Validate reported seat usage into the five measured keys."""
    if not isinstance(reported, dict):
        raise ValueError(f'malformed runtime usage; {ADAPTER_DATA}')
    for key in ('input_tokens', 'output_tokens'):
        if key in reported and (type(reported[key]) is not int or reported[key] < 0):
            raise ValueError(f'malformed runtime usage; {ADAPTER_DATA}')
    for key in ('cost', 'duration'):
        if key in reported and (type(reported[key]) not in (int, float)
                                or not math.isfinite(reported[key]) or reported[key] < 0):
            raise ValueError(f'malformed runtime usage; {ADAPTER_DATA}')
    if 'model' in reported and (not isinstance(reported['model'], str) or not reported['model']):
        raise ValueError(f'malformed runtime usage; {ADAPTER_DATA}')
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
        raise ValueError(f'invalid runtime result; {ADAPTER_DATA}')
    usage = normalize_usage(result.get('usage', {}), result.get('model') or model)
    iteration = record['iteration'] + 1
    # The result and usage share the writer lock, so duplicate hooks cannot charge twice.
    def update(data):
        current = data['builds'][item]
        if current != record:
            raise ValueError(f'build changed during result recording; {RACE}')
        if agent_id is not None:
            data['seats'][record['seat']]['status'] = 'stopped'
            data['seats'][record['seat']].pop('reason', None)  # recovered from unmeasured (#473)
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
        raise ValueError(f'SubagentStop omitted builder agent_id; {PAYLOAD}')
    if agent_id == record.get('replaced'):
        return True  # #614: the replaced agent's late stop; the fresh launch records the round
    if record.get('agent_id') and record['agent_id'] != agent_id:
        raise ValueError(f'SubagentStop agent_id differs from resumed builder; {PAYLOAD}')
    from wuwei.brief import last_turn
    completion, message, _ = last_turn(payload['agent_transcript_path'])
    text = payload.get('last_assistant_message')
    if not isinstance(text, str) or not text.strip():
        text = message  # #473: a background hand-back carries no message
    elif message.strip() != text.strip():
        raise ValueError(f'SubagentStop has no matching assistant completion; {PAYLOAD}')
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
                raise ValueError(f'malformed runtime usage; {ADAPTER_DATA}')
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
    record.pop('check', None)
    if record['status'] != 'check':
        raise ValueError(f'build is not awaiting checks; run bin/wuwei build next {item} for the current step')
    failures = []
    if len(results) != len(record['commands']):
        raise ValueError('incomplete fast checks; rerun bin/wuwei fast-checks in the worktree; if it repeats, run bin/wuwei doctor')
    for command, result in zip(record['commands'], results):
        if not isinstance(result, registry.Result) or type(result.exit) is not int or result.exit not in (0, 1, 2):
            raise ValueError(f'invalid check result; {ADAPTER_DATA}')
        if result.exit == 2:
            raise ValueError(result.reason or 'fast check could not run; rerun bin/wuwei fast-checks in the worktree; if it repeats, run bin/wuwei doctor')
        if result.exit == 1:
            if isinstance(result.data, dict) and 'environment' in result.data:
                reason = result.data['environment']
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError(f'invalid environment check reason; {DAMAGED}')
                _park(root, item, record, f'environment: {reason}', expected)
                return 1
            failures.append((command, result.data))
    config = workspace.load_config(root)
    row = state.read_state(root)['items'][item]
    if not failures and row['phase'] in ('implement', 'fix'):
        # Design 5.10: the move to the gates needs every spec step, implementation included.
        from wuwei import specmode
        code, reason = specmode.check(root, config, item, row, Path(record['worktree']),
                                      build=True, where='gates')
        if code:
            failures.append(('spec', {'error': reason}))
    if not failures:
        record.update(status='done', action={'action': 'done'})
    else:
        signature = _signature(failures)
        record['repeats'] = record['repeats'] + 1 if signature == record['signature'] else 1
        record['signature'] = signature
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
    _save(item, record, root, 'build.checked', expected,
          {'passed': len(results) - len(failures), 'failed': len(failures)})
    after = {'implement': 'gate', 'fix': 'delta'}.get(state.read_state(root)['items'][item]['phase'])
    if not failures and after:
        state.transition(item, after, root)
    return 1 if failures else 0


def check(item, *, root=None):
    root = workspace.find_workspace(root)
    record = state.read_state(root).get('builds', {}).get(item)
    if record is None or record['status'] != 'check':
        found = 'no build yet' if record is None else f'build {record["status"]}'
        raise ValueError(f'{item} is not waiting for checks ({found}); run bin/wuwei build next {item} '
                         'for its current step')
    _busy(item, record)
    from wuwei import fast_checks  # #579: complete on the checks the day's pace runs
    config = workspace.load_config(root)
    repo = next((row for row in config['repos'] if row['name'] == record['repo']), None)
    commands = fast_checks.commands(root, config, repo, record['worktree']) if repo else record['commands']
    marked = {**record, 'commands': commands,
              'check': {'started_at': workspace.now().isoformat(), 'pid': os.getpid()}}
    _save(item, marked, root, 'build.check_started', record)
    record = marked
    fast_checks.record(record['worktree'])
    measured = state.read_state(root).get('fast_checks', {}).get(record['repo'], {})
    if any(command not in measured for command in record['commands']):
        raise ValueError(f'incomplete fast checks; rerun bin/wuwei fast-checks in the worktree, then bin/wuwei build check {item}')
    results = [registry.Result(row['exit'], row.get('data'), row.get('reason') or '')
               for row in (measured[command] for command in record['commands'])]
    return complete_checks(item, results, root=root, expected=marked)


def _park(root, item, record, reason, expected):
    from wuwei import decision
    text = (
        f'Question: Park build {item}?\nClass: park\nContext: Iteration {record["iteration"]}: {reason}.\n'
        'Options:\n| Option | Title | Rationale | Consequence |\n| --- | --- | --- | --- |\n'
        '| defer | Defer and investigate | Respects the iteration limits and preserves budget. | '
        'The item parks until the failure is investigated. |\n'
        '| retry | Retry the build | Fails the iteration limit must. | The build keeps spending budget. |\n'
        'Musts:\n| Criterion | defer | retry |\n| --- | --- | --- |\n'
        '| Respect iteration limits | pass | fail |\n'
        'Wants:\n| Criterion | Weight | defer | retry |\n| --- | --- | --- | --- |\n'
        '| Preserve budget | 10 | 10 | 0 |\n'
        'Recommendation: defer\nReasoning: Preserving the budget decided it; a new brief would flip it.\n'
        'Confidence: high\nReversibility: two-way\n'
        'Blast radius: own branch\nPre-mortem: Repeated failures consume the remaining budget.\n'
        'Revisit: After investigating the failure and revising the brief.\n'
        f'Decided-by: seat\nOutcome: parked {item}\n')
    def update(data):
        if data['builds'][item] != expected:
            raise ValueError(f'build changed before parking; {RACE}')
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
            raise ValueError(f'invalid runtime status; {ADAPTER_DATA}')
        if status['status'] == 'completed':
            return status
        if status['status'] in ('failed', 'cancelled'):
            raise RuntimeError(f'runtime seat {status["status"]}; rerun the same bin/wuwei build command to resume, and run bin/wuwei doctor if it fails again')
        if time.monotonic() >= deadline:
            raise TimeoutError('runtime seat timed out; rerun the same bin/wuwei build command to resume, or raise the runtime timeout with bin/wuwei config set in a host terminal')
        time.sleep(config['build']['poll_interval_seconds'])


def run_loop(item, brief, worktree, *, root=None):
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        runtime_config = registry.runtime_config('builder', config, root)
        if runtime_config['adapters']['runtime'] == 'claude':
            raise ValueError('Claude builders require build next <item> in the planner session; run bin/wuwei build next <item> there. Or the owner switches the builder runtime to codex with bin/wuwei config set in a host terminal')
        if brief is None or worktree is None:
            raise ValueError('usage: build <item> <brief> <worktree> (Codex only); run bin/wuwei build <item> <brief> <worktree> with all three arguments')
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
                    print(parked_line(item, action), file=sys.stderr)
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
