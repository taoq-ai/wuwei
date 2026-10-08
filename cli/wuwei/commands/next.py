"""Where the day stands and the one next action, read from the day's files only (#551)."""

import json
import os
import sys

from wuwei import brief, integrity, state, workspace
from wuwei.decision import answered
from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED

HEADER = 'WUWEI orientation'
TERMINAL = ('merged', 'parked', 'escalated')
POSTURES = {
    'observe': ('Observe posture is on: guards record what they would refuse and let the call '
                'through. Records (state, events, config, verdicts, decisions) and owner-only actions '
                '(deploys, merges, approvals, approve-tier messages) still refuse. bin/wuwei shadow '
                'report lists the would-be refusals.'),
    'guarded': ('Posture guarded: records, publishing and plugin integrity block; seat launches, '
                'outward text and MCP findings below the floor warn. A refusal names its reason and '
                'the accepted form: use that form, never a way around it.'),
    'strict': ('Posture strict: every guard area blocks. A refusal names its reason and the '
               'accepted form: use that form, never a way around it.'),
}
ERRORS = (OSError, ValueError, KeyError, TypeError, UnicodeError)
EXECUTABLE = ('wuwei is the absolute path in .wuwei/executable: read it once and use it as the '
              'first word of a plain command, never through a variable')
LOOP = ('Loop: run wuwei next --json, do the one action it returns, and run it again when the '
        'result or a completion notification arrives.')
THEN = {
    'run': 'Run the command, then run wuwei next.',
    'background': 'Run the command through Bash in the background; run wuwei next when it exits.',
    'agent': ('Pass it to Agent in the background, then run wuwei next; its completion '
              'notification brings this item back.'),
    'set': ('Do every entry now: run each command in order, pass every launch and continue to '
            'Agent in the background in one message, run each run entry through Bash in the '
            'background; then run wuwei next.'),
    'card': ('Ask the widget list with AskUserQuestion, record each answer with its record '
             'command, then run wuwei next.'),
    'owner': ('Show the owner the why and the command in one line; run wuwei next when they say '
              'it is done.'),
    'wait': ('End the turn with the output of wuwei status --line; run wuwei next when a '
             'completion notification arrives.'),
    'done': 'The day is closed; tomorrow starts with wuwei next.',
    # Planner-facing lines of single rows; step formats {days} and {dm}.
    'pr-flow': 'On exit 1 show its output to the owner unchanged, once; then run wuwei next.',
    'mcp': 'On exit 1 or 2 show the owner its one-line reason; then run wuwei next.',
    'lead': ('Pass it to Agent in the background. When its completion notification arrives, save '
             "the lead's JSON answer to {days}/lead.json with the Write tool, then run wuwei next."),
    'propose': ("If that file is missing, first save the lead's JSON answer there with the Write "
                'tool. On exit 1 or 2 show the owner the reason; then run wuwei next.'),
    'gate': ('Ask the widget list with AskUserQuestion. On Approve run its record command; on Change '
             'something ask the owner what to change, edit {days}/lead.json and run wuwei plan propose '
             '{days}/lead.json again; then run wuwei next.'),
    'goals': ('Under strict the hook refuses and prints the command: show that line to the owner for '
              'a host terminal; then run wuwei next.'),
    'calibrate': ('Ask the widget list with AskUserQuestion, record each answer with its record '
                  'command (outside strict the answer writes its config key); when it prints a Next: '
                  'line, show the owner bin/wuwei config promote for a host terminal. Then run '
                  'wuwei next.'),
    'pr': ('Run it and do any action it prints; when it prints nothing the PR waits on people: end '
           'the turn with wuwei status --line, the watch wakes you when it changes.'),
    'close': 'On exit 1 show the owner what it names and end the turn; then run wuwei next.',
    'closed': ('Exit 0 closes the day; on exit 1 show the owner what it names and end the turn; then '
               'run wuwei next.'),
    'report': 'Present the report to the owner in one short message, then run wuwei next.',
    'report-dm': ("Present the report to the owner in one short message and also post it to the "
                  "owner's DM {dm} with the connector's send tool, then run wuwei next."),
}
LEAD_BODY = ('Propose today. Answer with one JSON object: goals, seat_policy, envelope, sweep and '
             'ordered candidates, plus seats (goal to seats of CAP) only to change the split the CLI '
             'derives. Each candidate has id, goal, evidence, scope, overlap, track, the three '
             'boolean flags, score and evidence_lines for each component of the configured '
             'framework. While memory/goals.md has no goals, write each proposed goal as a block '
             '(id, outcome, measure, target, date, priority), never an id alone. Check open '
             'status and overlap against the items of the day and other active work.')
# No single quote in LEAD_BODY: step quotes it without shlex, which hook paths do not import.
SHEPHERD_BODY = 'Raise the PR for {item} and own it until merged.'
PROPOSE = 'run wuwei plan propose '


def register(subparsers):
    parser = subparsers.add_parser('next', help='Print where the day stands and the one next action')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def _row(name, why, command=None, action='run', then=None, **extra):
    return {'state': name, 'action': action, **({'command': command} if command else {}),
            'why': why, 'then': then or THEN.get(action, THEN['run']), **extra}


def approved(data):
    """Approved items in queue order, less those a seat decision carried or parked."""
    disposed = {str(record.get('item_disposition')).split(' ', 1)[-1]
                for record in data.get('decision_outcomes', {}).values()
                if isinstance(record, dict) and record.get('decided_by') in ('seat', 'mandate')
                and str(record.get('item_disposition')).startswith(('carried ', 'parked '))}
    return [name for name in data['approved_items'] if name in data['items'] and name not in disposed]


def _seen(directory):
    """(done (state, key) pairs, passed pairs, steward runs, steward due, day closed) from one
    read of today's events; only lines naming a kind next needs are parsed (#346 budget). A row is
    done when its command ran (the done pairs run() records) or it passed with nothing to ask."""
    done, passed, returns, runs, due, closed = set(), set(), {}, [], False, False
    path = directory / 'events.jsonl'
    for text in path.read_text(encoding='utf-8').splitlines() if path.is_file() else ():
        if not ('"next.action"' in text or '"steward.' in text or '"day.closed"' in text):
            continue
        row = json.loads(text)
        kind, payload = row.get('kind'), row.get('payload')
        if not isinstance(payload, dict):
            raise ValueError(f'invalid event record; {DAMAGED}')
        if kind == 'next.action':
            key = (payload.get('state'), payload.get('item') or '')
            if payload.get('action') == 'pass':
                passed.add(key)
            else:
                returns[key] = returns.get(key, 0) + 1
            done.update(tuple(pair) for pair in payload.get('done', ()))
        elif kind == 'steward.run':
            runs.append(payload)
            due = False
        elif kind == 'steward.due':
            due = True
        elif kind == 'day.closed':
            closed = True
    # ponytail: a row returned three times counts as done, so a refused or failed command (no
    # PostToolUse span) never holds the day; evidence from PostToolUseFailure would lift it.
    done |= passed | {key for key, count in returns.items() if count >= 3}
    return done, passed, runs, due, closed


def _carry(root, directory):
    """True when the prior day left unfinished items the proposal does not name again: plan
    approve --import-yesterday imports them all and refuses an overlap."""
    prior = sorted(path.name for path in (root / '.wuwei/days').glob('????-??-??')
                   if path.is_dir() and path.name < directory.name)
    if not prior or not (root / '.wuwei/days' / prior[-1] / 'state.json').is_file():
        return False
    items = state.read_state(directory=root / '.wuwei/days' / prior[-1])['items']
    left = {name for name, item in items.items() if item['phase'] != 'merged' and item['status'] != 'done'}
    proposal = directory / 'proposal.json'
    named = ({row['id'] for row in json.loads(proposal.read_text(encoding='utf-8'))['candidates']}
             if proposal.is_file() else set())
    return bool(left) and not left & named


def step(root, ran=()):
    """The first due action row; root None means no workspace here. Hook-safe: it only reads.
    ran: the (state, key) pairs whose command ran since the last recorded action.
    ponytail: one row, not a list; the first due item wins and status --line shows the rest."""
    if root is None:
        return _row('no-workspace', 'No WUWEI workspace here; create one in observe posture in a '
                    'host terminal in the project directory.',
                    'bin/wuwei setup --shadow', 'card', THEN['owner'])
    config = workspace.load_config(root)
    # Not calibrate.approved: hook paths must not import calibrate (test_hooks pins it).
    calibration = root / '.wuwei/calibration.json'
    if (not config['repos'] or not calibration.is_file()
            or not json.loads(calibration.read_text(encoding='utf-8'))):
        return _row('setup', 'Setup is incomplete; complete the repositories, calibration and '
                    'interview in a host terminal.', 'bin/wuwei setup', 'card',
                    THEN['owner'])
    directory = workspace.day_dir(root)
    days = f'.wuwei/days/{directory.name}'
    data = state.read_state(directory=directory)
    if not data.get('planner_session_id'):
        # Inline, not sessions.current(): hook.py imports this module on every event.
        session = os.environ.get('WUWEI_SESSION_ID', '').strip() or '<session id>'
        return _row('session', "Register this session as today's planner.",
                    f'wuwei plan session {session}')
    returned, passed, runs, due, closed = _seen(directory)
    returned |= set(ran)
    if not (directory / 'plan.md').is_file():
        if ('pr-flow', '') not in returned:
            return _row('pr-flow', 'Check the PR flow settings once before the day starts.',
                        'wuwei doctor --section pr-flow', then=THEN['pr-flow'])
        if ('mcp', '') not in returned:
            return _row('mcp', 'Check the MCP registry before any seat launches.', 'wuwei mcp check',
                        then=THEN['mcp'])
        lead = data['seats'].get('lead')
        if not (directory / 'lead.json').is_file() and (lead is None or lead['status'] == 'running'):
            if not (directory / 'briefs/lead.md').is_file():
                return _row('lead', 'Brief the lead seat for discovery and the proposal.',
                            f"wuwei brief lead day lead --body '{LEAD_BODY}'")
            if lead is None:
                return _row('lead', 'Launch the lead seat on its brief.', 'wuwei next --json',
                            'launch', THEN['lead'].format(days=days),
                            brief=f'{days}/briefs/lead.md')
            return _row('wait', 'The lead seat is proposing the day.', 'wuwei status --line', 'wait')
        return _row('propose', "Propose the day from the lead's answer.",
                    f'wuwei plan propose {days}/lead.json', then=THEN['propose'])
    if not data['gate_approved']:
        return _row('gate', f'Morning gate open: the plan in {days}/plan.md is approved only on '
                    'your answer.', 'wuwei plan gate' + (' --import-yesterday' if _carry(root, directory) else ''),
                    'card', THEN['gate'].format(days=days))
    if (directory / 'goals.md').is_file() and ('goals', '') not in returned:
        return _row('goals', 'Record the goals you approved at the gate.',
                    f'wuwei goals edit --file {days}/goals.md', then=THEN['goals'])
    earlier = any(path.name < directory.name for path in (root / '.wuwei/days').glob('????-??-??'))
    if not earlier and ('calibrate', '') not in returned:
        return _row('calibrate', 'First day: ask the calibration questions setup did not cover.',
                    'wuwei calibrate --questions', 'card', THEN['calibrate'])
    if ('telemetry', '') not in returned:
        return _row('telemetry', "Ask this week's telemetry proposals.",
                    'wuwei telemetry proposals --widget', 'card')
    routes = data.get('decision_routes', {})
    if not isinstance(routes, dict):
        raise ValueError(f'invalid decision ledger; {DAMAGED}')
    pending = [identifier for identifier in routes if answered(data, identifier) is None]
    for identifier in pending:
        if ('decision', identifier) not in returned:
            return _row('decision', f'Decision {identifier} waits for your answer.',
                        f'wuwei decision show {identifier} --widget', 'card', item=identifier)
    seats = brief.seats(data)
    if stuck := brief.stuck(data):
        return _row('stuck', f'Seat {stuck[0]} ended with no recorded result.',
                    f'wuwei seat stop {stuck[0]} --unmeasured "seat ended with no recorded result"')
    rows = state.in_flight(data)
    running = {item for _, _, item in rows}
    items = data['items']
    names = approved(data)
    building = sum(items[name]['phase'] in state.BUILD_PHASES for name in names)
    queued = sum(items[name]['phase'] == 'planned' for name in names)
    waiting = None
    for name in names:
        phase = items[name]['phase']
        if phase in TERMINAL or name in running:
            continue
        # Inline, not wuwei.tracker: next runs on hook paths.
        ticket = data.get('tickets', {}).get(name, {}).get('id')
        label = f'{name} ({ticket})' if ticket else name
        if phase in state.BUILD_PHASES:
            return _row('build', f'{label} is in {phase}; this is its build loop step.',
                        f'wuwei build next {name}', item=name)
        if phase in ('gate', 'delta'):
            from wuwei import docs  # Local: only an item at the gate needs it.
            if docs.unmet(config, items[name]):
                return _row('docs', f"{name} (tier {items[name]['gates']['tier']}) has no docs value; "
                            'record it before the quality gate.',
                            docs.command(config, name).removeprefix('bin/'), item=name,
                            then='Choose the value it names, record it, then run wuwei next.')
            return _row('verdicts', f'{label} is at {phase}; these are its gate steps.',
                        f'wuwei dispatch next {name}', item=name)
        if phase == 'raised':
            pr = items[name].get('pr')
            return _row('pr', f'{label} has PR {pr} open; act on its review state.',
                        f'wuwei pr act {pr}', item=name, then=THEN['pr'])
        if phase == 'planned' and building < data['cap']:
            return _row('dispatch', f'{min(queued, data["cap"] - building)} planned item(s) can '
                        f'start, {building} of CAP {data["cap"]} building; this is the launch set.',
                        'wuwei dispatch next --all', 'set')
        if phase == 'planned' and waiting is None:
            waiting = label
    if due:
        return _row('steward', 'The steward is due after the recorded tool calls.',
                    'wuwei steward run --trigger tool-calls', then=THEN['background'])
    for run in runs:
        stem = str(run.get('brief', '')).rsplit('/', 1)[-1].removesuffix('.md')
        if stem and stem not in seats:
            return _row('steward', 'Launch the steward seat on its brief.', 'wuwei next --json',
                        'launch', THEN['agent'], brief=run['brief'])
    builders = sorted((seat.get('started_at') or '', name) for name, seat in seats.items()
                      if seat['status'] == 'running' and seat['role'] == 'builder')
    text = state.in_flight_text(rows)
    if waiting and builders:
        return _row('wait', f'{waiting} waits: {building} of CAP {data["cap"]} building; '
                    f'{builders[0][1]} started first ({builders[0][0] or "start unrecorded"}) and '
                    f'is expected to free first; SubagentStop records each result. Running: {text}',
                    'wuwei status --line', 'wait')
    if rows:
        return _row('wait', f'Running: {text}; SubagentStop records each seat, and a background '
                    'check reports when it exits.', 'wuwei status --line', 'wait')
    # ponytail: health from recorded watch and heartbeat events, not a doctor run (#346 budget).
    from wuwei.commands.status import scan
    _, watch, _, beat, _ = scan(directory, {**data, 'now': workspace.now().isoformat()})
    if (watch == 'dead' or beat == 'degraded') and ('doctor', '') not in returned:
        return _row('doctor', f'Watch {watch}, heartbeat {beat}; run the doctor and fix what it '
                    'names.', 'wuwei doctor')
    if not data.get('close_requested'):
        return _row('close', 'Every approved item is merged, parked, carried or escalated; close '
                    'the day.', 'wuwei close', then=THEN['close'])
    if not any(run.get('trigger') == 'close' for run in runs):
        pending = [identifier for identifier in pending if ('close', identifier) not in passed]
        if pending:  # a decision that holds the close is asked again (#530)
            return _row('close', f'Decision {pending[0]} holds the close.',
                        f'wuwei decision show {pending[0]} --widget', 'card', item=pending[0])
        return _row('close', 'Close the day once nothing holds it.', 'wuwei close', then=THEN['close'])
    if not (directory / 'retro' / f'{directory.name}.md').is_file():
        return _row('retro', 'Compile the steward retro.', 'wuwei retro')
    if ('promote', '') not in returned:
        return _row('promote', 'Land the supported charter learnings.', 'wuwei promote')
    if ('retro-applied', '') not in returned:
        return _row('retro-applied', 'Record what promote applied in the retro.', 'wuwei retro')
    if not (directory / 'report.md').is_file():
        outbound = config['outbound']
        dm = outbound['owner']['slack']['dm'] or outbound['owner']['slack']['user']
        then = THEN['report-dm'].format(dm=dm) if outbound['owner_channel'] == 'dm' else THEN['report']
        return _row('report', "Write the day's report.", 'wuwei report', then=then)
    if not closed:
        return _row('closed', 'Report written; close the day.', 'wuwei close', then=THEN['closed'])
    return _row('done', 'The day is closed.', action='done')


def text(row):
    """The action for a person: one paragraph, then the command on its own line."""
    command = row.get('command')
    if row['action'] in ('launch', 'continue') and row.get('agent_type'):
        command = f"Agent {row['agent_type']}"
    return f"{row['state']}: {row['why']} {row['then']}" + (f'\n{command}' if command else '')


def _widget(argv):
    """A widget command's printed list, run in process: the same code the planner would run."""
    import io
    from contextlib import redirect_stdout
    from wuwei.__main__ import main
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    found = json.loads(out.getvalue() or '[]') if code in (0, 1) else None
    if not isinstance(found, list):
        raise ValueError(f'wuwei {" ".join(argv)} printed no widget list (exit {code}); run it for '
                         'its reason')
    return found


def resolve(row, root):
    """The delegate's own action for a delegated row, or None when the day must be asked again
    (an empty widget list, a build done or park, a gate fix). Called by the next command only."""
    import shlex
    name, item = row['state'], row.get('item')
    keep = {'state': name, **({'item': item} if item else {})}
    if row['action'] == 'launch':
        action = brief.seat_action('lead' if name == 'lead' else 'steward', root / row['brief'],
                                   root, root)
        return {**keep, **action, 'why': row['why'], 'then': row['then']}
    if row['action'] == 'card' and row['command'].startswith('wuwei '):
        widget = _widget(shlex.split(row['command'])[1:])
        if name == 'gate':
            from wuwei import mcp
            widget += mcp.widget(root)
        return {**row, 'widget': widget} if widget else None
    if name == 'build':
        from wuwei.commands import build
        action = build.next_action(item, root=root)
        if action['action'] in ('done', 'park'):
            return None
        then = THEN['background'] if action['action'] == 'check' else THEN['agent']
        return {**keep, **action, 'why': row['why'], 'then': then}
    if name == 'verdicts':
        from wuwei import dispatch
        action = dispatch.next_step(item, root)
        if action['action'] == 'fix':
            return None
        if action['action'] == 'escalate':
            return _row(name, f"{item}: {action['reason']}; park it for the owner.",
                        f'wuwei plan park {item} --reason ' + shlex.quote(action['reason']), item=item)
        if action['action'] == 'raise':
            return _shepherd(root, item, action['notes'], row['why'])
        return {**keep, **action, 'why': row['why'], 'then': THEN['set']}
    if name == 'dispatch':
        from wuwei import dispatch
        return {**keep, **dispatch.launch_set(root), 'why': row['why'], 'then': THEN['set']}
    return row


def _shepherd(root, item, notes, why):
    """The shepherd raises the PR: its brief, its launch, or a card when it stopped without one."""
    import shlex
    data = state.read_state(root)
    name = f'shepherd-{item}'
    path = workspace.day_dir(root) / 'briefs' / f'{name}.md'
    worktree = data['items'][item].get('worktree') or str(root)
    if not path.is_file():
        body = '\n'.join([SHEPHERD_BODY.format(item=item), *(f'Review note: {note}' for note in notes)])
        return _row('raise', f'{why} Every gate passed; brief the shepherd to raise the PR.',
                    f'wuwei brief shepherd {item} {name} --worktree {shlex.quote(worktree)} --body '
                    + shlex.quote(body), item=item)
    if name not in data['seats']:
        return {'state': 'raise', 'item': item, **brief.seat_action('shepherd', path, worktree, root),
                'why': f'{why} Launch the shepherd to raise the PR.', 'then': THEN['agent']}
    return _row('raise', f'{name} stopped without raising the PR.', f'wuwei why {item}', 'card',
                THEN['owner'], item=item)


def named(action):
    """The exact commands an action names, a command its then line names included."""
    found = [action['command']] if action.get('command') else []
    found += [widget['record'] for widget in action.get('widget', []) if widget.get('record')]
    found += action.get('commands', [])
    for entry in action.get('entries', []) + action.get('seats', []):
        found += [entry[key] for key in ('command', 'receive') if entry.get(key)]
        found += entry.get('commands', [])
    if PROPOSE in action['then']:
        found.append('wuwei plan propose ' + action['then'].split(PROPOSE, 1)[1].split()[0])
    return found


def _record(root, action, commands, ran=()):
    """Append the reserved next.action event; nothing without today's state (#551)."""
    directory = workspace.day_dir(root)
    if not (directory / 'state.json').is_file():
        return
    traces = directory / 'traces.jsonl'
    count = len(traces.read_bytes().splitlines()) if traces.is_file() else 0
    state.append_event('next.action', {'state': action['state'], 'action': action['action'],
                                       'item': action.get('item', ''), 'named': commands,
                                       'traces': count, **({'done': list(ran)} if ran else {})}, root)


def _ran(root):
    """[[state, key]] of the last recorded action when a Bash span since names one of its
    commands: the evidence that its command ran, not that next returned it."""
    from wuwei import metrics
    directory = workspace.day_dir(root)
    events, traces = metrics._events(directory), metrics._traces(directory)
    last = next((row['payload'] for row in reversed(events or []) if row['kind'] == 'next.action'
                 and row['payload'].get('action') != 'pass'), None)
    if last is None or not traces:
        return []
    for row in traces[last.get('traces', 0):]:
        found = row['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
        if found['name'] != 'Bash':
            continue
        attributes = {pair['key']: pair['value']['stringValue'] for pair in found['attributes']}
        command = json.loads(attributes['gen_ai.tool.arguments']).get('command', '')
        try:
            if any(metrics._matches(command, pattern) for pattern in last.get('named', [])):
                return [[last['state'], last.get('item') or '']]
        except ValueError:
            continue  # an unparsed command names nothing
    return []


def orientation(row, posture, spec=None, session=None):
    """The SessionStart block: the next action and the loop; paths are computed, nothing read.
    spec: the spec engine and its effective mode (5.10). session: the payload's session id."""
    plugin = integrity.PLUGIN
    role = os.environ.get('WUWEI_SEAT_ROLE')
    if (isinstance(role, str) and role and '/' not in role and not role.startswith(('_', '.'))
            and (plugin / 'charters' / f'{role}.md').is_file()):
        entry = f'You are the {role} seat: follow {plugin}/charters/{role}.md and your brief; the ' \
                'planner session runs the day.'
    else:
        entry = LOOP
    shown = text(row).replace('<session id>', session) if session else text(row)
    return '\n'.join([
        HEADER,
        "WUWEI runs this workspace's coding day the way a careful engineering team works: the "
        'planner session ranks the work, seats build and review each change in their own '
        'worktree, and merges follow a policy.',
        f'The owner answers questions and decisions; the session runs the commands ({EXECUTABLE}) '
        'and never asks the owner to edit a file.',
        POSTURES[posture],
        *([f'Spec: {spec}'] if spec else []),
        f'Next: {shown}',
        entry,
        'Reference: wuwei guide (every command, the accepted forms and the rules; the same text is '
        f'the guide block in the memory.export_to file); owner guide: {plugin}/docs/site/daily.md',
    ])


def run(args):
    code = CLEAN
    try:
        try:
            root = workspace.find_workspace()
        except FileNotFoundError:
            root = None
        ran = _ran(root) if root is not None else []
        row = step(root, map(tuple, ran))
        if root is not None:
            from wuwei import dispatch
            from wuwei.commands.build import PortExit
            try:
                for _ in range(8):
                    action = resolve(row, root)
                    if action is not None:
                        break
                    _record(root, {**row, 'action': 'pass'}, [])
                    row = step(root, map(tuple, ran))
                else:
                    raise ValueError('the day did not settle on one action; run wuwei status')
            except (dispatch.Refused, brief.Refused) as exc:
                action, code = {**row, 'why': str(exc)}, FINDINGS
            except PortExit as exc:
                if exc.code != 1:
                    raise ValueError(str(exc)) from exc
                action, code = {**row, 'why': str(exc)}, FINDINGS
            if args.json:  # a person's look-up never moves the day
                _record(root, action, named(action), ran)
            row = action
    except ERRORS as exc:
        row, code = _row('unmeasured', str(exc), 'wuwei doctor'), UNRUN
        print(f'wuwei next: {exc}', file=sys.stderr)
    print(json.dumps(row) if args.json else text(row))
    return code
