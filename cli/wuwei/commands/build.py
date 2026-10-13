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
    parser.add_argument('operation', help='next, check, reconcile, analysis, classes, or legacy Codex item')
    parser.add_argument('arguments', nargs='*', metavar='item/brief/worktree')
    parser.add_argument('--file', help="analysis: read the spec-kit analysis report from PATH instead of stdin")
    # #901: reconcile brings work done outside the record back in
    parser.add_argument('--worktree', help='reconcile: the existing worktree that holds the work')
    parser.add_argument('--pr', help='reconcile: the open PR of the work, owner/repo#n')
    parser.add_argument('--repo', help='reconcile: the repository of --branch')
    parser.add_argument('--branch', help='reconcile: the existing branch that holds the work')
    parser.add_argument('--track', choices=('SLICE', 'FULL'), help="reconcile: the item's track, as plan add records it")
    parser.set_defaults(func=run)


def parked_line(item, action):
    """A parked build names the command that resumes it; that command asks the owner its card."""
    return (f'build: parked {item}: {action["reason"]}; run wuwei plan resume {item} after revising '
            'its brief; it asks the owner its Owner step card')


def run(args):
    if args.operation in ('analysis', 'classes'):
        if len(args.arguments) != 1:
            print('build: usage: build analysis <item> [--file PATH] or build classes <worktree>; run bin/wuwei build analysis <item> with the report on stdin', file=sys.stderr)
            return 2
        return (run_analysis if args.operation == 'analysis' else classes)(args.arguments[0], args.file)
    if args.operation == 'reconcile':
        return run_reconcile(args)
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
                    elif action.get('action') in ('continue', 'wait'):
                        print(action.get('feedback') or action['reason'], file=sys.stderr)
                return code
            from wuwei import dispatch
            try:
                action = step(item, root, *paths)
            except dispatch.Refused as exc:
                print(f'build: {exc}', file=sys.stderr)
                return 1
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
        from wuwei.commit_push import context
        repo, _, _ = context(tree, {}, {}, root, identity=False)
    return repo  # #600, #832: no fast checks is a state; CI and the gates are the evidence


def _save(item, record, root, kind, expected, extra=None, also=None):
    def update(data):
        builds = data.setdefault('builds', {})
        if builds.get(item) != expected:
            raise ValueError(f'build changed before recording action; {RACE}')
        builds[item] = record
        if also:
            also(data)
    state._write_state(update, root, kind=kind, payload={'item': item, **(extra or {})})


def _continue(root, record, feedback):
    """Resume the stopped builder with feedback: a failure round or a #648 release."""
    from wuwei.brief import launch_prompt
    from wuwei.security import agent_path
    return {'action': 'continue', 'feedback': feedback, 'resume': record.get('agent_id'),
            'agent_type': 'wuwei:builder',
            'prompt': launch_prompt(root / record['brief'], agent_path(root, 'builder'), root=root) + '\n\n' + feedback}


def _fix_id(data, repo, path):
    """#648: one fix item per broken file per repository; a merged one gets a successor."""
    base = 'fix-main-' + '-'.join(re.findall(r'[a-z0-9]+', f'{repo} {path}'.lower()))
    fix, number = base, 1
    while data['items'].get(fix, {}).get('phase') == 'merged':
        number += 1
        fix = f'{base}-{number}'
    return fix


def _main_broken(root, config, data, item, record, failures):
    """#648: (check, path, fix id) when every failure is main's, else None. An unreadable
    diff, a fix item failing on its own file or a fix the planner parked holds nothing."""
    from wuwei import dispatch, fast_checks
    from wuwei.brief import status
    try:
        _, rows = dispatch._changes(root, config, {'worktree': record['worktree']})
        dirty = status(registry.load('vcs', config), record['worktree'], root)
        changed = {path for change in [*rows, *dirty]
                   for path in (change.get('path'), change.get('original_path')) if path}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    held = fast_checks.unchanged(failures, changed, record['worktree'])
    if not held:
        return None
    check, path = held[0]
    fix = _fix_id(data, record['repo'], path)
    if fix == item or data['items'].get(fix, {}).get('phase') in ('parked', 'escalated'):
        return None
    return check, path, fix


def _admit(root, row, broken, repo):
    """#648: the fix item through plan add (the owner-item path, no ticket), in the held
    build's repository (#908)."""
    check, path, fix = broken
    if fix in state.read_state(root)['items']:
        return True
    from wuwei import plan
    try:
        plan.add(fix, root, goal=row.get('goal'), title=f'Fix main: {path} fails {check}'[:120],
                 source='main-broken', repo=repo)
    except (OSError, ValueError):
        pass  # a refusal holds nothing, unless a concurrent hold admitted it first
    return fix in state.read_state(root)['items']


def _hold(item, record, root, expected, broken):
    """#648: the item waits on the fix item; main_broken names the check, path and items."""
    check, path, fix = broken
    record.update(status='ready', action={'action': 'wait', 'fix': fix, 'reason': (
        f'main is broken: {check} fails on {path}, which {item} does not change; fix item {fix} '
        f'repairs it. Do not fix it in this branch: {item} rebases and reruns its checks once {fix} merges')})

    def entry(data):
        found = data.setdefault('main_broken', {}).setdefault(fix, {
            'repo': record['repo'], 'check': check, 'path': path, 'items': [],
            'scope': f'Fix main: {path} fails {check}'[:120],
            'evidence': f'{check} fails on {path}, a file the held items do not change',
            'at': workspace.now().isoformat()})
        if item not in found['items']:
            found['items'].append(item)
    _save(item, record, root, 'build.held', expected, {'fix': fix}, also=entry)


def _release(item, record, data, root):
    """#648: the fix item ended: the builder rebases and the fast checks rerun."""
    fix = record['action']['fix']
    feedback = (f"Main fix {fix} is {data['items'].get(fix, {}).get('phase')}. Rebase this branch onto "
                'the current base branch and run the fast checks; change nothing else unless a check '
                'still fails.')
    released = {**record, 'action': _continue(root, record, feedback)}
    _save(item, released, root, 'build.released', record, {'fix': fix})
    return released['action']


def _busy(item, record):
    marker = state.check_running(record)
    if marker:
        raise ValueError(f'fast checks for {item} are running since {marker["started_at"][11:16]} (pid {marker["pid"]}); run bin/wuwei build next {item} when that command exits')


def step(item, root, *paths):
    """#902: the one resolver of build next and of next's build launches: the build loop's
    action; a build at its checks whose builder stopped Blocked asks the owner first (Yes
    continues it on the answer, No parks the item); past the build (#666), what dispatch next
    decides."""
    from wuwei import dispatch
    data = state.read_state(root)
    record = data.get('builds', {}).get(item)
    phase = (data['items'].get(item) or {}).get('phase')
    seat = data.get('seats', {}).get((record or {}).get('seat'), {})
    stopped = seat.get('status') in ('stopped', 'unmeasured') and seat.get('brief') == record.get('brief')
    blocked = (record and (record['status'] == 'check' or 'result' not in record and stopped)
               and phase in state.BUILD_PHASES
               and dispatch._blocked_card(root, data, item, build=True))
    if blocked and record.get('answered') != blocked[3]:  # one continue per answered line
        reason, answer, card, line = blocked
        if answer == 'No':
            return dispatch._parked(root, item, reason, ask=False)
        if answer != 'Yes':
            return {'action': 'escalate', 'reason': reason, 'command': 'wuwei build next ' + shlex.quote(item),
                    'card': card}
        action = _continue(root, record, (
            f'The owner answered Yes to your Blocked: line: {line}. Go on as you recommended, record it '
            "under Assumptions in the item's spec, commit, and stop."))
        _save(item, {**record, 'status': 'ready', 'action': action, 'answered': line}, root, 'build.answered',
              record, {'line': line})
        return action
    action = next_action(item, *paths, root=root)
    if action['action'] == 'done' and state.read_state(root)['items'][item]['phase'] in (
            'gate', 'delta', 'parked', 'escalated'):
        return dispatch.gate_step(item, root)
    return action


def next_action(item, brief=None, worktree=None, *, root=None, runtime=None):
    """Return one stable action. Executing it belongs to the caller. runtime (#845): the runtime
    a new build binds, routed by the launch set; else routed here on fresh window room."""
    from wuwei.brief import events, identifier, read, seat_action
    root = workspace.find_workspace(root)
    identifier(item)
    data = state.read_state(root)
    if item not in data['items']:
        raise PortExit(2, f'unknown item {item}')
    record = data.get('builds', {}).get(item)
    if _recover_committed(item, record, root):
        return state.read_state(root)['builds'][item]['action']
    if record is not None and record['status'] == 'running':
        raise ValueError(f'builder is still running; wait for its stop hook, then run bin/wuwei build next {item}')
    if record is not None:
        _busy(item, record)
    config = workspace.load_config(root)
    if brief is None:
        matches = [row['payload'] for row in events(root) if row['kind'] == 'brief written'
                   and row['payload'].get('item') == item and row['payload'].get('role') == 'builder']
        if not matches:
            raise ValueError(f'no logged builder brief for {item}; write one with bin/wuwei seat brief, or pass the paths: bin/wuwei build next {item} <brief> <worktree>')
        brief = root / matches[-1]['path']
        worktree = matches[-1].get('worktree') or data['items'][item].get('worktree')
    if worktree is None:
        raise ValueError(f'builder brief needs a worktree; create one with bin/wuwei worktree add {item} and pass it with --worktree. Or run bin/wuwei build next {item} <brief> <worktree>')
    tree = (root / worktree).resolve(strict=True)
    path = (root / brief).resolve(strict=True)
    relative = str(path.relative_to(root))
    # #892: a builder launched straight from its brief ran outside the build record; one brief
    # is one seat, so the build continues that seat instead of handing the brief out again
    def ran(path):  # the builder seats that ran a brief of this item
        return [name for name, seat in data.get('seats', {}).items() if seat.get('role') == 'builder'
                and seat.get('item') == item and seat.get('brief') == path]
    used = next(iter(ran(relative)), None)
    if used and (record is None or record.get('seat') != used):
        status = data['seats'][used]['status']
        if status == 'running':
            raise ValueError(f'builder seat {used} is still running; wait for its stop hook, then run bin/wuwei build next {item}')
        if status != 'stopped':
            raise ValueError(f'brief {used} already ran a seat that is {status}; write a fresh brief with bin/wuwei seat brief, then run bin/wuwei build next {item}')
    unbound = bool(used) and record is not None and record.get('seat') != used
    stale, logged = False, []
    if record is not None:
        if relative == record['brief'] and str(tree) == record['worktree'] and not unbound:
            if record['action']['action'] == 'wait' and not state.held(data, item):
                return _release(item, record, data, root)
            return record['action']
        if record['status'] == 'ready' and record['action']['action'] == 'launch' and str(tree) == record['worktree']:
            # #889: an unlaunched brief the worktree moved past is one the launch guard refuses
            # (unlogged today, or logged at another HEAD); a new brief replaces it, and the build
            # keeps its start head (a record from before start heads takes the old brief's),
            # its fix rounds and its fix feedback
            logged = [row['payload'].get('head') for row in events(root) if row['kind'] == 'brief written'
                      and row['payload'].get('path') == record['brief']]
            # D1: a seat other than the build's already ran the recorded brief: the guard refuses it
            stale = (unbound or not logged or bool(set(ran(record['brief'])) - {record.get('seat')})
                     or (logged[-1] is not None and logged[-1] != read(
                         registry.load('vcs', config).head, tree, root=root)['sha']))
        if record['status'] not in ('done', 'parked') and not stale:
            raise ValueError(f'cannot replace an unfinished build with a new brief; run bin/wuwei build next {item} to finish it first')
        if data['items'][item]['phase'] in ('parked', 'escalated'):
            raise ValueError(f'{item} is parked; resume it with bin/wuwei plan resume {item}, then run bin/wuwei build next {item}')
    if record is None and data['items'][item]['phase'] == 'planned' and data['cap_bound']:
        # #901: a new build takes a CAP slot, as wuwei next counts it; the launch guard sends a
        # builder with no build record here, so past CAP this waits instead of starting one
        from wuwei.commands.next import building as holders
        building = len(holders(data))
        if building >= data['cap']:
            raise ValueError(f'CAP {data["cap"]} reached ({building} building); wait for a build to finish, '
                             f'then run bin/wuwei build next {item} (bin/wuwei next names the seat expected to free first)')
    repo = _repo(root, tree, config)
    policy = data['seat_policy'].get('builder', {})
    if runtime is None and policy.get('alternate'):
        from wuwei import dispatch
        rooms = dispatch.windows(root, config, [policy['runtime'], policy['alternate']])
        runtime = dispatch.route(policy, config['adapters']['runtime'], {name: row['room'] for name, row in rooms.items()})
    action = seat_action('builder', path, tree, root, runtime)
    previous = record
    feedback = stale and previous['action'].get('feedback')
    if feedback:
        action['feedback'] = feedback
        action['prompt'] += '\n\n' + feedback + previous['action']['prompt'].partition('\n\n' + feedback)[2]
    commands = [] if data['items'][item].get('kind') == 'measure' else list(repo['fast_checks'])
    from wuwei import derive  # #871 L2: the head the build must move past
    if used:  # #892: the head the seat launched at
        start = data['seats'][used].get('head')
    elif stale:
        start = previous.get('start') or next(iter(logged), None)
    else:  # #889 F4: a new record counts the commits its branch holds over the brief's base
        start = (previous is None and _base_start(path, tree, config, root)) or derive.head(tree)
    record = {**(previous if stale else {}), 'brief': relative, 'worktree': str(tree), 'start': start,
              'runtime': action['runtime'], 'repo': repo['name'],
              'commands': commands, 'iteration': 0, 'repeats': 0,
              'signature': None, 'status': 'ready', 'action': action}
    if used:
        record.update(seat=used, agent_id=data['seats'][used].get('agent_id'))
        record['action'] = action = _continue(root, record, (
            f'Seat {used} ran this brief before WUWEI recorded its build. Finish what the brief '
            'asks, commit it, and stop; WUWEI runs the fast checks next.'))
    _save(item, record, root, 'build.started', previous,
          None if commands else {'checks': 'none configured'})
    if data['items'][item]['phase'] == 'planned':
        state.transition(item, 'implement', root)
    if previous is None:
        from wuwei import dispatch
        dispatch.tracker_call(item, 'claim', root)
    if _recover_committed(item, record, root):
        return state.read_state(root)['builds'][item]['action']
    return action


def _base_start(path, tree, config, root):
    """#889 F4, #901: the brief's Merge-base when it is an ancestor of HEAD (D3: a base a rebase
    left behind is not), else None; the start head a new build counts its commits from."""
    from wuwei import derive
    from wuwei.brief import read
    base = re.search(r'^Merge-base: (\S+)', Path(path).read_text(encoding='utf-8').split('\n\n', 1)[0], re.M)
    if not (base and derive.SHA.fullmatch(base[1])):
        return None
    try:
        return base[1] if read(registry.load('vcs', config).merge_base, str(tree), base[1], root=root)['sha'] == base[1] else None
    except ValueError:
        return None


def open_fix(item, feedback, *, root, polish=None, start=None):
    """Resume the linked builder once with measured gate or PR feedback. polish (#723) is the
    item's polish record, written in the same state write."""
    from wuwei.brief import ci_block, ci_jobs, launch_prompt
    from wuwei.security import agent_path
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError('fix round needs measured feedback; run the gates first, then pass their findings to the fix round')
    data = state.read_state(root)
    if item not in data['items']:
        raise ValueError(f'unknown item {item}; check the name with bin/wuwei next, or admit it with bin/wuwei plan add {item}')
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
    if used >= cap and not dispatch._resumed(root, item):  # #623: one cap for gate and PR fixes; D3, #904: the owner's resume grants one
        raise ValueError(f'round cap {cap} reached (gates.max_rounds); park {item} for the owner (bin/wuwei why {item} shows the rounds)')
    phase = data['items'][item]['phase']
    if phase not in ('gate', 'raised', 'delta'):
        raise ValueError(f'fix round needs a gated, delta or raised item; run bin/wuwei dispatch next {item} for its current step')
    brief = root / record['brief']
    # #733: the CI job the feedback names is recorded, and every one of its steps is listed
    refs = sorted({*data['items'][item].get('ci_jobs', ()), *ci_jobs(feedback, record['worktree'])})
    ci = ci_block(refs, record['worktree'])
    resume = record.get('agent_id') or record.get('job')
    if not resume and (record['status'] == 'done' or record['runtime'] == 'codex'):
        from wuwei import brief as brief_writer
        body = f'Read the original builder brief {record["brief"]}.\n\nFix feedback:\n{feedback}'
        name = f'{item}-{"pr" if phase == "raised" else "gate"}-fix' + (f'-{used + 1}' if used else '')
        relative = brief_writer.write('builder', item, name, body,
                                      worktree=record['worktree'],
                                      pr=data['items'][item].get('pr'), root=root)
        brief = root / relative
    prompt = launch_prompt(brief, agent_path(root, 'builder'), root=root) + '\n\n' + feedback + ('\n' + ci if ci else '')
    action = {'action': 'continue' if resume else 'launch',
              'feedback': feedback, 'prompt': prompt, 'agent_type': 'wuwei:builder',
              'runtime': record['runtime'], 'brief': str(brief),
              'worktree': record['worktree']}
    if record.get('agent_id'):
        action['resume'] = record['agent_id']
    def update(fresh):
        if fresh.get('builds', {}).get(item) != record:
            raise ValueError(f'build changed before fix round; run bin/wuwei build next {item} again')
        if phase in ('delta', 'raised'):  # #903: a pre-PR delta never stands in for a PR fix's review
            dispatch.rotate(fresh, item, used)
        if polish:
            if fresh['items'][item].get('polish'):
                raise ValueError(f'polish round already recorded for {item}; run bin/wuwei dispatch next {item}')
            fresh['items'][item]['polish'] = polish
        fresh['items'][item]['phase'] = 'fix'
        from wuwei import derive  # #844: the head each fix round starts from and leaves
        head = start or derive.head(record['worktree'])
        fresh['items'][item]['fix_heads'] = [*fresh['items'][item].get('fix_heads', []), [head, None]]
        if refs:
            fresh['items'][item]['ci_jobs'] = refs
        fresh['builds'][item] = {**record, 'brief': str(brief.relative_to(root)), 'start': head,
                                 'status': 'ready', 'action': action,
                                 'fix_rounds': used + 1, 'iteration': 0, 'repeats': 0,
                                 'signature': None}
    state._write_state(update, root, kind='build.fix_opened',
                       payload={'item': item, 'round': used + 1, 'cap': cap,
                                **({'polish': True} if polish else {})})
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


def continuing(record, agent_id):
    """A SendMessage continuation has no launch hook; only its bound agent can finish it."""
    return bool(record and agent_id and record.get('agent_id') == agent_id
                and record['status'] == 'ready' and record['action']['action'] == 'continue'
                and record['action'].get('resume') == agent_id)


def record_result(item, result, *, root, agent_id=None, model=None, completion=None, expected=None):
    record = expected if expected is not None else state.read_state(root)['builds'][item]
    if record['status'] != 'running' and not continuing(record, agent_id):
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
            for key in ('reason', 'report', 'report_sha256'):  # recovered from unmeasured (#473, #905)
                data['seats'][record['seat']].pop(key, None)
        current.update(status='check', iteration=iteration, agent_id=agent_id, completion=completion,
                       result=result, action=recheck(item, record))
    updated = state._write_state(update, root, kind='seat.usage',
                       payload={'item': item, 'role': 'builder', 'iteration': iteration, 'usage': usage,
                                'runtime': record['runtime']})
    if updated['items'][item].get('kind') == 'measure':
        complete_checks(item, [], root=root, expected=updated['builds'][item])
    if result.get('windows'):
        from wuwei import dispatch
        dispatch.save_windows(root, record['runtime'], result['windows'])
    if agent_id is not None:
        state.append_event('seat stopped', {'name': record['seat']}, root)
    return updated['builds'][item]


def recheck(item, record, reason=None):
    """The fast-check step; reason (#904): the environment hold it waits on to be repaired."""
    action = {'action': 'check', 'command': 'wuwei build check ' + shlex.quote(item),
              'worktree': record['worktree'], 'checks': record['commands']}
    return {**action, 'reason': reason} if reason else action


def check_binding(item, record):
    return {'item': item, 'brief': record['brief'], 'iteration': record['iteration'] + 1}


class Mismatch(ValueError):
    """#905: a stop from an agent that is not the bound builder; the seat stays as it was."""


def stopped(item, name, payload, *, root):
    """Accept only the hook-bound seat result and current measured check evidence."""
    data = state.read_state(root)
    record = data.get('builds', {}).get(item)
    if record is None or record.get('seat') != name:
        return False
    if record['status'] != 'running' and not (record['status'] == 'ready' and record['action']['action'] == 'continue'):
        return True
    agent_id = payload.get('agent_id')
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise Mismatch(f'SubagentStop omitted builder agent_id; {PAYLOAD}')
    if agent_id == record.get('replaced'):
        return True  # #614: the replaced agent's late stop; the fresh launch records the round
    if record.get('agent_id') and record['agent_id'] != agent_id:
        raise Mismatch(f'SubagentStop agent_id differs from resumed builder; {PAYLOAD}')
    if record['status'] == 'ready' and not continuing(record, agent_id):
        return True
    from wuwei.brief import last_turn
    text = payload.get('last_assistant_message')
    deadline = time.monotonic() + 2
    while True:
        try:
            completion, message, _ = last_turn(payload['agent_transcript_path'])
            if not isinstance(text, str) or not text.strip():
                text = message  # #473: a background hand-back carries no message
            if message.strip() == text.strip():
                break
        except ValueError:
            pass  # the writer may still be flushing the final JSON row
        if time.monotonic() >= deadline:
            raise ValueError('SubagentStop has no matching assistant completion after waiting for '
                             f'the transcript; retry bin/wuwei seat stop {name} --verdict <file>')
        time.sleep(0.05)
    if completion == record.get('completion'):
        return True
    reported = payload.get('usage', {})
    try:
        if isinstance(reported, dict):
            reported = {**{key: payload[source] for key, source in (
                ('input_tokens', 'total_input_tokens'), ('output_tokens', 'total_output_tokens'),
                ('duration', 'duration_seconds'), ('model', 'model')) if source in payload}, **reported}
            if 'duration' not in reported and 'duration_ms' in payload:
                milliseconds = payload['duration_ms']
                if type(milliseconds) not in (int, float) or not math.isfinite(milliseconds) or milliseconds < 0:
                    raise ValueError(f'malformed runtime usage; {ADAPTER_DATA}')
                reported['duration'] = milliseconds / 1000
        normalize_usage(reported, None)
    except ValueError:
        reported = {}  # #905: usage the runtime got wrong is unmeasured; the finished result still counts
    expected = record_result(item, {'text': text, 'usage': reported},
                             root=root, agent_id=agent_id, completion=completion, expected=record)
    if data['items'][item].get('kind') == 'measure':
        return True
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
        raise ValueError(f'incomplete fast checks; rerun bin/wuwei build check {item}; if it repeats, run bin/wuwei doctor')
    for command, result in zip(record['commands'], results):
        if not isinstance(result, registry.Result) or type(result.exit) is not int or result.exit not in (0, 1, 2):
            raise ValueError(f'invalid check result; {ADAPTER_DATA}')
        if result.exit == 2:
            raise ValueError(result.reason or f'fast check could not run; rerun bin/wuwei build check {item}; if it repeats, run bin/wuwei doctor')
        if result.exit == 1:
            if isinstance(result.data, dict) and 'environment' in result.data:
                reason = result.data['environment']
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError(f'invalid environment check reason; {DAMAGED}')
                # #904: a hold the repair clears with a recheck; unchanged, it parks for the owner
                signature = _signature([('environment', {'error': reason})])
                record['repeats'] = record['repeats'] + 1 if signature == record['signature'] else 1
                record['signature'], reason = signature, f'environment: {reason}'
                if record['repeats'] >= workspace.load_config(root)['build']['stuck_after']:
                    _park(root, item, record, reason, expected)
                else:
                    record['action'] = recheck(item, record, f'{reason}; repair the check environment '
                                               f'(install it, or fix the interpreter), then run bin/wuwei build check {item}')
                    _save(item, record, root, 'build.held', expected, {'reason': reason})
                return 1
            failures.append((command, result.data))
    config = workspace.load_config(root)
    data = state.read_state(root)
    row = data['items'][item]
    if row.get('kind') == 'measure':
        from wuwei import brief, dispatch
        try:
            vcs = registry.load('vcs', config)
            changed = (brief.read(vcs.head, record['worktree'], root=root)['sha'] != record['start']
                       if record.get('start') else bool(dispatch._changes(
                           root, config, {'worktree': record['worktree']})[1]))
            dirty = brief.status(vcs, record['worktree'], root)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f'measurement diff unmeasured: {exc}') from exc
        if changed or dirty:
            failures.append(('change', {'error': 'measurement changed the worktree; remove its code diff and hand off the evidence'}))
    broken = failures and _main_broken(root, config, data, item, record, failures)
    if broken and _admit(root, row, broken, record['repo']):
        _hold(item, record, root, expected, broken)
        return 1
    if not failures and row.get('resume_phase', row['phase']) in ('implement', 'fix'):  # #872: paused too
        # Design 5.10: the move to the gates needs every spec step, implementation included.
        from wuwei import specmode
        code, reason = specmode.check(root, config, item, row, Path(record['worktree']),
                                      build=True, where='gates')
        if code:
            failures.append(('spec', {'error': reason}))
    if not failures and row.get('kind') != 'measure':  # a measurement hands off evidence, not a commit
        failures += _unbuilt(record, root, config)
    if not failures:  # #901 review: the head the checks passed on is the only head a gate reads
        record.update(status='done', action={'action': 'done'}, checked=_measured(item, record, data))
    elif _retry(root, config, item, record, failures, expected):
        return 1
    _save(item, record, root, 'build.checked', expected,
          {'passed': len(results) - len(failures), 'failed': len(failures)})
    after = AFTER.get(state.read_state(root)['items'][item]['phase'])  # a paused item: plan resume moves it
    if not failures and after:
        from wuwei import derive
        end = derive.head(record['worktree'])
        state._write_state(lambda data: built(data, item, after, end), root, kind='state.transition',
                           payload={'item': item, 'phase': after})
    return 1 if failures else 0


def _measured(item, record, data):
    """#901 review D2: the one HEAD every fast check measured; HEAD when none is configured."""
    from wuwei import derive
    if not record['commands']:
        return derive.head(record['worktree'])
    rows = data.get('fast_checks', {}).get(record['repo'], {})
    shas = {(rows.get(command) or {}).get('sha') for command in record['commands']}
    if len(shas) != 1 or None in shas:
        raise ValueError(f'incomplete fast checks: they measured no single HEAD; rerun bin/wuwei build check {item}')
    return shas.pop()


AFTER = {'implement': 'gate', 'fix': 'delta'}


REPEATED = {'change': 'no change over the start head', 'private': 'private files repeated',
            'commit': 'commit refused repeated', 'dirty': 'uncommitted changes repeated'}


def _private(paths):
    """#871: the paths a build never hands to the gates: the credential locations of the #870
    trace check (scanner._credential_path), the one rule; .env templates pass."""
    from wuwei.scanner import _credential_path
    return [path for path in paths if _credential_path('./' + path)]


def _retry(root, config, item, record, failures, expected):
    """A failed iteration: the builder continues with the failures, or the item parks on a
    repeat. True when parked. #871 B5: an unchanged head parks on its first repeat."""
    signature = _signature(failures)
    record['repeats'] = record['repeats'] + 1 if signature == record['signature'] else 1
    record['signature'] = signature
    names = {name for name, _ in failures}
    cause = REPEATED.get(*names) if len(names) == 1 else None  # #871: a park names its cause
    stuck = 2 if names == {'change'} else config['build']['stuck_after']
    reason = ((cause or 'same fast-check failure repeated') if record['repeats'] >= stuck
              else 'maximum build iterations reached' if record['iteration'] >= config['build']['max_iterations'] else None)
    if reason:
        _park(root, item, record, reason, expected)
        return True
    feedback = '\n'.join(f'{name}: {json.dumps(data)}' for name, data in failures)
    record.update(status='ready', action=_continue(root, record, feedback))
    return False


def _unbuilt(record, root, config):
    """#871 L2: a build that leaves uncommitted changes, commits a private file, or makes no
    commit over the head it started from did not build; the gates never get those heads."""
    from wuwei import derive
    from wuwei.brief import read, status
    vcs = registry.load('vcs', config)
    dirty = status(vcs, record['worktree'], root)
    if dirty:
        return [('dirty', {'error': 'uncommitted changes: ' + ', '.join(row['path'] for row in dirty)
                            + '; remove what does not belong to the change (WUWEI commits a Codex '
                            'build; a Claude builder commits its own)'})]
    if not record.get('start'):
        return []
    if derive.head(record['worktree']) != record['start']:
        # A16: any commit since start, a file deleted again included; the push sends them all
        private = _private(read(vcs.touched, record['worktree'], record['start'], root=root))
        if private:
            return [('private', {'error': (
                f'private files {", ".join(private)} in the commits since the start head; these '
                f'commits are not pushed yet, so rewrite them locally: git reset --soft {record["start"]}, '
                'remove the files, add them to .gitignore, and commit again')})]
        return []
    return [('change', {'error': f'no change over the start head {record["start"][:12]}; '
                                 'make the change the brief asks for'})]


def built(data, item, after, end):
    """Move an item whose build passed past its build phase (complete_checks; plan resume, #872)."""
    if AFTER.get(data['items'][item]['phase']) != after:
        return  # #872: paused or moved since the caller read it; plan resume moves it
    heads = data['items'][item].get('fix_heads') or []
    if after == 'delta' and heads and heads[-1][1] is None:
        heads[-1][1] = end  # #844: the head this fix round produced
    state._move(data, item, after)


def recheck_moved(item, root, record, head):
    """#901 review: a done build whose worktree moved past its checked head goes back to its fast
    checks before any gate reads that head; returns the check step."""
    _save(item, {**record, 'status': 'check', 'action': recheck(item, record)}, root, 'build.rechecked',
          record, {'checked': record['checked'], 'head': head})
    return {**recheck(item, record), 'reason': (
        f'HEAD {head[:12]} is past {record["checked"][:12]}, the head the fast checks passed on; a gate '
        f'reads only a checked head, so run wuwei build check {item}, then wuwei dispatch next {item}')}


def _recover_committed(item, record, root):
    """#930: missing hand-back, finished seat and committed work: measure it through checks."""
    from wuwei import brief, derive, dispatch
    if (not record or record['status'] not in ('ready', 'running') or 'result' in record
            or record.get('reconciled') or record.get('signature') or record.get('answered')
            or not derive.SHA.fullmatch(record.get('start') or '')):
        return False
    data = state.read_state(root)
    seats = brief.seats(data)
    seat = seats.get(record.get('seat'))
    if (not seat or seat['status'] not in ('stopped', 'unmeasured') or seat['item'] != item
            or seat.get('brief') != record['brief'] or seat['role'] != 'builder'
            or any(row['status'] == 'running' and row['role'] == 'builder' and row['item'] == item
                   for row in seats.values())):
        return False
    if seat['status'] == 'unmeasured' and record['seat'] not in brief.stuck(data):
        return False
    if dispatch._blocked(root, data, item):
        return False
    _busy(item, record)
    vcs = registry.load('vcs', workspace.load_config(root))
    tree = record['worktree']
    head = brief.read(vcs.head, tree, root=root)['sha']
    if (head == record['start'] or brief.status(vcs, tree, root)
            or brief.read(vcs.merge_base, tree, record['start'], root=root)['sha'] != record['start']):
        return False
    recovered = {**record, 'status': 'check', 'action': recheck(item, record),
                 'reconciled': {'head': head, 'dirty': [], 'at': workspace.now().isoformat()}}

    def unchanged(current):
        if current.get('seats') != data.get('seats'):
            raise ValueError(f'seats changed during build recovery; {RACE}')
    _save(item, recovered, root, 'build.reconciled', record,
          {'head': head, 'start': record['start'], 'result': 'unmeasured'}, also=unchanged)
    return True


def check(item, *, root=None):
    root = workspace.find_workspace(root)
    record = state.read_state(root).get('builds', {}).get(item)
    if _recover_committed(item, record, root):
        record = state.read_state(root)['builds'][item]
    if record is None or record['status'] != 'check':
        found = 'no build yet' if record is None else f'build {record["status"]}'
        outside = (f'; work done outside the record: bin/wuwei build reconcile {item} --worktree <path>'
                   if record is None else '')  # #901
        raise ValueError(f'{item} is not waiting for checks ({found}); run bin/wuwei build next {item} '
                         f'for its current step{outside}')
    _busy(item, record)
    from wuwei import fast_checks  # complete on the configured fast checks
    config = workspace.load_config(root)
    repo = next((row for row in config['repos'] if row['name'] == record['repo']), None)
    commands = repo['fast_checks'] if repo else record['commands']
    marked = {**record, 'commands': commands,
              'check': {'started_at': workspace.now().isoformat(), 'pid': os.getpid()}}
    _save(item, marked, root, 'build.check_started', record)
    record = marked
    fast_checks.record(record['worktree'])
    measured = state.read_state(root).get('fast_checks', {}).get(record['repo'], {})
    if any(command not in measured for command in record['commands']):
        raise ValueError(f'incomplete fast checks; rerun bin/wuwei build check {item}')
    results = [registry.Result(row['exit'], row.get('data'), row.get('reason') or '')
               for row in (measured[command] for command in record['commands'])]
    return complete_checks(item, results, root=root, expected=marked)


def _park(root, item, record, reason, expected):
    def update(data):
        if data['builds'][item] != expected:
            raise ValueError(f'build changed before parking; {RACE}')
        record.update(status='parked', action={'action': 'park', 'reason': reason})
        data['builds'][item] = record
        data['items'][item].update(phase='parked', status='blocked', disposition={'kind': 'parked', 'reason': reason})
    state._write_state(update, root, kind='build.parked',
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
        if status['status'] in ('failed', 'cancelled'):  # #871: the caller frees the seat; a rerun relaunches
            raise RuntimeError(f'runtime seat {status["status"]}' + (f': {status["error"]}' if status.get('error') else '')
                               + '; rerun the same command to relaunch it, and run bin/wuwei doctor if it fails again')
        if time.monotonic() >= deadline:
            raise TimeoutError('runtime seat timed out; rerun the same bin/wuwei build command to resume, or raise the runtime timeout with bin/wuwei config set')
        time.sleep(config['build']['poll_interval_seconds'])


def _commit(item, root, config):
    """#871 L2: commit a completed runtime job's changes with the repository identity. The
    job's sandbox cannot write the worktree's git metadata (it lives in the main repository's
    .git/worktrees), so it leaves them uncommitted. Returns the failure that stopped the commit
    (B1, B2: a private file, a rejecting hook, a timeout), which goes back to the builder; an
    unset identity raises, for the owner."""
    from wuwei import commit_push
    from wuwei.brief import status
    record = state.read_state(root)['builds'][item]
    vcs = registry.load('vcs', config)
    dirty = status(vcs, record['worktree'], root)
    if not dirty:
        return None
    index, repo = next(((index, row) for index, row in enumerate(config['repos'])
                        if row['name'] == record['repo']), ('<n>', {}))
    unset = commit_push.unset_identity(repo.get('identity'), index)
    if unset:
        raise ValueError(f'{unset[0]}; WUWEI commits a Codex build with it. The owner runs {unset[1]}, '
                         'then rerun the same command')
    private = _private(row['path'] for row in dirty)
    if private:
        return ('private', {'error': f'private files {", ".join(private)}: remove them or add them to '
                                     '.gitignore; WUWEI does not commit them'})
    try:
        _data(vcs.commit_all(record['worktree'], item,
                             repo['identity']['name'], repo['identity']['email'], root=root), 'commit')
    except PortExit as exc:
        return ('commit', {'error': str(exc)})
    return None


def _refuse(item, record, root, config, failure):
    """B1, B2: a commit WUWEI could not make is the builder's next iteration, like a failed check."""
    retried = dict(record)
    if not _retry(root, config, item, retried, [failure], record):
        _save(item, retried, root, 'build.checked', record, {'passed': 0, 'failed': 1})


def run_loop(item, brief, worktree, *, root=None):
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        runtime_config = registry.runtime_config('builder', config, root)
        bound = state.read_state(root).get('builds', {}).get(item)  # #845: a routed build keeps its runtime
        if bound:
            runtime_config = {**config, 'adapters': {**config['adapters'], 'runtime': bound['runtime']}}
        if runtime_config['adapters']['runtime'] == 'claude':
            raise ValueError('Claude builders require build next <item> in the planner session; run bin/wuwei build next <item> there. Or the owner switches the builder runtime to codex with bin/wuwei config set')
        if brief is None or worktree is None:
            raise ValueError('usage: build <item> <brief> <worktree> (Codex only); run bin/wuwei build <item> <brief> <worktree> with all three arguments')
        runtime = registry.load('runtime', runtime_config)

        def claim(data):  # #845 F2: one loop per item; a second run ends without a job
            record = data.get('builds', {}).get(item)
            if record and state.check_running({'check': record.get('loop')}):
                raise PortExit(0, f"{item} build loop already running (pid {record['loop']['pid']})")
            if record:
                record['loop'] = {'pid': os.getpid(), 'started_at': workspace.now().isoformat()}
        state._write_state(claim, root)
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
                if action['action'] == 'wait':
                    print(f'build: {item} waits: {action["reason"]}; run bin/wuwei build {item} <brief> <worktree> again once {action["fix"]} merges', file=sys.stderr)
                    return 1
                if action['action'] == 'check' and action.get('reason'):
                    print(f'build: {item} holds: {action["reason"].partition(";")[0]}; repair it, then run '
                          f'bin/wuwei build check {item}', file=sys.stderr)
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
            try:
                status = wait(runtime, job, config, root)
            except RuntimeError as exc:  # #871: a failed job frees the build; the rerun relaunches
                running = state.read_state(root)['builds'][item]
                _save(item, {**running, 'status': 'ready'}, root, 'build.failed', running, {'reason': str(exc)})
                raise
            refused = (None if state.read_state(root)['items'][item].get('kind') == 'measure'
                       else _commit(item, root, config))
            recorded = record_result(item, _data(runtime.result(job, root=root), 'result'),
                                     root=root, model=status.get('model'))
            if refused and recorded:
                _refuse(item, recorded, root, config, refused)
    except PortExit as exc:
        print(f'build: {exc}', file=sys.stderr)
        return exc.code
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'build: {exc}', file=sys.stderr)
        return 2


def run_reconcile(args):
    from wuwei.brief import Refused
    if len(args.arguments) != 1:
        print('build: usage: build reconcile <item> [--worktree PATH] [--pr owner/repo#n] '
              '[--repo NAME --branch BRANCH]; run bin/wuwei build reconcile <item> --worktree <path>',
              file=sys.stderr)
        return 2
    try:
        print(json.dumps(reconcile(args.arguments[0], worktree=args.worktree, pr=args.pr,
                                   repo=args.repo, branch=args.branch, track=args.track)))
        return 0
    except (state.StateError, Refused) as exc:
        print(f'build reconcile: {exc}', file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, PortExit) as exc:
        print(f'build reconcile: {exc}', file=sys.stderr)
        return 2


UNMEASURED = ['gates: not run on this work yet', 'owner approval: none recorded',
              'tests or reviews the outside work ran: not counted']


def reconcile(item, *, root=None, worktree=None, pr=None, repo=None, branch=None, track=None):
    """#901: bring work done outside the record back in: the item's worktree, its PR and, before
    the gates, a build record that starts at the fast checks (no builder seat is invented). Each
    step reads what is recorded first, so a rerun finishes an interrupted one and an unchanged
    one writes nothing. Nothing outside counts as tested or approved: the checks and gates run."""
    from wuwei import dispatch, merge, shepherd
    from wuwei.brief import identifier, read, status
    from wuwei.commands import worktree as worktrees
    root = workspace.find_workspace(root)
    identifier(item)
    config = workspace.load_config(root)
    vcs = registry.load('vcs', config)
    data = state.read_state(root)
    row = data['items'].get(item)
    if row is None or item not in data['approved_items']:
        raise state.StateError(f"{item} is not in the approved plan; on the owner's word admit it with "
                               f'bin/wuwei plan add {item} --goal <G-n>, then rerun')
    if row['phase'] in ('parked', 'escalated'):
        raise state.StateError(f'{item} is {row["phase"]}; resume it with bin/wuwei plan resume {item}, then rerun')
    if dispatch._blocked(root, data, item):
        raise state.StateError(f'builder has an unresolved Blocked line; run bin/wuwei build next {item}')
    ref = pr and merge.reference(pr, root, config, repo=config['repos'][0]['name'] if len(config['repos']) == 1 else None)
    other = next((name for name in (repo, ref and ref.split('#')[0]) if name and row.get('repo') not in (None, name)), None)
    if other:  # review F2: the item's recorded repository changes only by an explicit decision
        raise state.StateError(f'{item} is for {row["repo"]}, not {other}; pass a worktree, branch or PR of '
                               f'{row["repo"]}, or the owner admits the {other} work as its own item with '
                               f'bin/wuwei plan add <item> --repo {other}')
    if _recover_committed(item, data.get('builds', {}).get(item), root):
        data = state.read_state(root)
    _running(data, item)  # a seat still committing stops before its work is verified
    repo = row.get('repo') or repo
    if worktree:
        command = ['bin/wuwei', 'build', 'reconcile', item, '--worktree', str(Path(worktree).resolve())]
        for key, value in (('--pr', pr), ('--repo', repo), ('--branch', branch), ('--track', track)):
            if value and not (key == '--repo' and value == row.get('repo')):
                command.extend((key, value))
        workspace.adopt_worktree(root, item, worktree, vcs, dirty=True, repo=repo, rebind=shlex.join(command))
    elif branch and not row.get('worktree'):
        rows = [found for found in config['repos'] if found['name'] == repo or not repo and len(config['repos']) == 1]
        if len(rows) != 1:
            raise state.StateError(f'{branch} names no single repository; pass --repo <one of '
                                   f'{", ".join(found["name"] for found in config["repos"])}>')
        worktrees.checkout(root, config, item, rows[0], branch, dirty=True)
    if pr:
        data = state.read_state(root)
        row = data['items'][item]
        if row.get('pr') != ref or not row.get('worktree') and ref not in data['raised_prs']:
            from contextlib import redirect_stdout
            with redirect_stdout(sys.stderr):  # review F5: stdout stays one JSON document
                code = shepherd.claim_pr(root, ref, item, built=True)
            if code:
                raise (state.StateError if code == 1 else ValueError)(
                    f'pr claim {ref} exited {code}; the line above says why, then rerun')
    row = state.read_state(root)['items'][item]
    if not row.get('worktree'):
        raise state.StateError(f'{item} has no worktree; pass --worktree <path>, --repo <name> --branch <branch> '
                               'or --pr <owner/repo#n>')
    tree = (root / row['worktree']).resolve(strict=True)
    if row['phase'] in ('planned', *state.BUILD_PHASES):
        _reconcile_build(item, root, config, vcs, tree, row, track)
    data = state.read_state(root)
    row, record = data['items'][item], data.get('builds', {}).get(item) or {}
    head = read(vcs.head, str(tree), root=root)['sha']
    measured = data.get('fast_checks', {}).get(record.get('repo'), {})
    phase = row['phase']
    return {'item': item, 'phase': phase, 'worktree': str(tree), 'head': head, 'start': record.get('start'),
            'pr': row.get('pr'), 'build': record.get('status'),
            'dirty': [change['path'] for change in status(vcs, str(tree), root)],
            'changed': read(vcs.touched, str(tree), record['start'], root=root) if record.get('start') else [],
            **{key: [f'{command}: exit {measured[command]["exit"]} at {head[:12]}'
                     for command in record.get('commands', ())
                     if measured.get(command, {}).get('sha') == head and (measured[command]['exit'] == 0) is passed]
               for key, passed in (('verified', True), ('failed', False))},
            'unmeasured': UNMEASURED + (['fast checks: none configured'] if record and not record['commands'] else []),
            'action': record.get('action'),
            'next': (f'wuwei build next {item}' if phase in state.BUILD_PHASES
                     else f'wuwei dispatch next {item}' if phase in ('gate', 'delta')
                     else None if phase == 'merged' else 'wuwei next')}


def _running(data, item):
    """A running builder seat of the item, by its build record or its seat row (review F1)."""
    from wuwei.brief import seats, stuck
    for name, seat in seats(data).items():
        if (seat['item'] == item and seat['role'] == 'builder' and seat['status'] == 'unmeasured'
                and name not in stuck(data)):
            raise state.StateError(f'builder seat {name} has no completion evidence; wait for its stop hook, '
                                   f'or record its finished report with bin/wuwei seat stop {name} --verdict <file>')
    record = data.get('builds', {}).get(item) or {}
    name = record.get('seat') if record.get('status') == 'running' else next(
        (name for name, seat in seats(data).items()
         if seat['role'] == 'builder' and seat['item'] == item and seat['status'] == 'running'), None)
    if record.get('status') == 'running' or name:
        raise state.StateError(f'builder seat {name} is running on {item}; wait for its stop hook, then rerun')


def _reconcile_build(item, root, config, vcs, tree, row, track=None):
    """The build step of reconcile: a build record at the fast checks on a brief at HEAD; an
    existing record keeps its start head, runtime, fix rounds and failure counts (review F3)."""
    from wuwei import brief as briefs, dispatch
    record = state.read_state(root).get('builds', {}).get(item)
    _running(state.read_state(root), item)
    head = briefs.read(vcs.head, str(tree), root=root)['sha']
    snapshot = {'head': head, 'dirty': sorted(change['path'] for change in briefs.status(vcs, str(tree), root))}
    if record and (record['status'] in ('done', 'parked') or record['action']['action'] == 'wait'
                   or {key: (record.get('reconciled') or {}).get(key) for key in snapshot} == snapshot
                   and record['status'] != 'check'):
        return
    if not record or record['status'] != 'check':
        name = f'{item}-reconcile-{head[:12]}'
        relative = str((workspace.day_dir(root) / 'briefs' / f'{name}.md').relative_to(root))
        if not any(event['kind'] == 'brief written' and event['payload'].get('path') == relative
                   for event in briefs.events(root)):
            try:
                relative = briefs.write('builder', item, name, (
                    f'Reconciled: {item} was built outside the WUWEI record in this worktree, at HEAD {head}. '
                    'Nothing it ran outside counts: WUWEI runs the fast checks, then the gates. When WUWEI '
                    'sends you their failures, fix them here, commit, and stop. Uncommitted at reconcile: '
                    + (', '.join(snapshot['dirty']) or 'none') + '.'), worktree=str(tree), pr=row.get('pr'),
                    track=track, root=root)
            except briefs.Refused as exc:  # review F7: the way out is this command's own option
                if '--track FULL' not in str(exc):
                    raise
                raise briefs.Refused(f'{exc}: rerun bin/wuwei build reconcile {item} with --track FULL') from exc
        repo = _repo(root, tree, config)
        fresh = {'iteration': 0, 'repeats': 0, 'signature': None,
                 **{key: record[key] for key in ('fix_rounds', 'iteration', 'repeats', 'signature')
                    if record and key in record},
                 'brief': relative, 'worktree': str(tree),
                 'start': (record or {}).get('start') or _base_start(root / relative, tree, config, root) or head,
                 'runtime': (record or {}).get('runtime') or registry.runtime_config('builder', config, root)['adapters']['runtime'],
                 'repo': repo['name'], 'commands': list(repo['fast_checks']),
                 'status': 'check', 'reconciled': {**snapshot, 'at': workspace.now().isoformat()}}
        fresh['action'] = recheck(item, fresh)

        def implement(data):  # in the same write: the record and the build phase
            if data['items'][item]['phase'] in ('planned', 'spec'):
                state._move(data, item, 'implement')
        _save(item, fresh, root, 'build.reconciled', record,
              {'brief': relative, 'start': fresh['start'], **snapshot}, also=implement)
    dispatch.tracker_call(item, 'claim', root)  # the duty is done once, on any day
    check(item, root=root)


def run_analysis(item, file):
    """#614: a Claude Code subagent cannot write analysis.md; this saves the seat's report."""
    try:
        print(write_analysis(item, Path(file).read_text(encoding='utf-8') if file else sys.stdin.read()))
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'wuwei build analysis: {exc}', file=sys.stderr)
        return 2


def write_analysis(item, text, root=None):
    """Write text as analysis.md in the item's one spec-kit directory; the path relative to
    its worktree."""
    from wuwei import specmode
    root = workspace.find_workspace(root)
    items = state.read_state(root)['items']
    # The step line formats {item} lowercased, like every spec step.
    names = [item] if item in items else [name for name in items if name.lower() == item.lower()]
    if len(names) != 1:
        raise ValueError(f'unknown item {item}; use the item id from the brief (bin/wuwei next lists them)')
    name, = names
    worktree = items[name].get('worktree')
    if not isinstance(worktree, str) or not worktree:
        raise ValueError(f'no worktree recorded for {name}; the planner creates it with bin/wuwei worktree add {name}')
    tree = (root / worktree).resolve()
    location, reason = specmode._location(tree, 'speckit', name)
    if location is None:
        raise ValueError(f'no single spec directory: {reason}; run /speckit.specify first, or remove the extra directory')
    directory = tree / location
    if directory.is_symlink() or not directory.resolve().is_relative_to(tree):
        raise ValueError(f'{location} is a symlink or leaves the worktree; replace it with the directory itself')
    if not (directory / 'spec.md').is_file():
        raise ValueError(f'{location} has no spec.md yet; run /speckit.specify first')
    target = directory / 'analysis.md'
    if target.is_symlink():
        raise ValueError(f'{location}/analysis.md is a symlink; remove the link, then run this again')
    if not text.strip():
        raise ValueError('empty report; pass the /speckit.analyze report on stdin or with --file PATH')
    found = specmode.governing(tree, items[name], location)  # #664
    gap = found and specmode.governed(text, (directory / 'spec.md').read_text(encoding='utf-8'))
    if gap:
        reference, first, last, _ = found
        raise ValueError(f'{name} is governed by {reference} (lines {first}-{last}) and {gap}; add one row '
                         'per assumption: | <assumption> | agrees, conflicts or not covered | <path>:<line> |, '
                         'then run this again')
    workspace.atomic_write(target, text if text.endswith('\n') else text + '\n', mode=0o644)
    return target.relative_to(tree).as_posix()


def classes(worktree, _file=None):
    """#567: the builder's class sweep: the classes whose files the item's diff touches."""
    from wuwei import dispatch
    try:
        root = workspace.find_workspace()
        tree = (root / worktree).resolve()
        items = state.read_state(root)['items']
        item = next((name for name, row in sorted(items.items()) if row.get('worktree')
                     and (root / row['worktree']).resolve() == tree), None)
        if item is None:
            raise ValueError(f'no item has the worktree {worktree}; pass the --worktree of its builder brief')
        record, found = dispatch.classes(root, workspace.load_config(root), items[item])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei build classes: {exc}', file=sys.stderr)
        return 2
    if record.get('depth', record['tier']) == 'light':
        print('Depth: light; no class sweep')
        return 0
    print(f"Depth: {record['tier']}")
    for name, paths in found.items():
        print(f"{name}: {', '.join(paths) or 'none changed'}")
    return 0
