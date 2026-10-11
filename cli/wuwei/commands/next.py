"""Where the day stands and the one next action, read from the day's files only (#551)."""

import json
import os
import sys

from wuwei import brief, integrity, state, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED

HEADER = 'WUWEI orientation'
TERMINAL = ('merged', 'parked', 'escalated')
# #837: one sentence per guards.enforce value.
ENFORCE = {
    False: ('Guards log only (guards.enforce = false): guards record what they would refuse and '
            'let the call through. Records (state, events, config, verdicts, decisions) still refuse; '
            'deploys, releases and approve-tier messages ask on a card; merges and approvals stay '
            "owner-only. The day report's ## Shadow section lists the would-be refusals."),
    True: ('Guards enforce: records, publishing, plugin integrity and seat launches without a '
           'matching brief block; deploys, releases and approve-tier messages ask on a card; merges '
           'and approvals stay owner-only; outward text, scratch paths and seat capacity '
           'are logged. A refusal names its reason and the accepted form: '
           'use that form, never a way around it.'),
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
    # #614: Claude Code's Agent has no resume; a continue binds as a fresh Agent.
    'continue': ('Launch a fresh Agent in the background with the prompt unchanged and agent_type '
                 'as subagent_type (pass resume only to an Agent tool that takes it), then run wuwei '
                 'next; its completion notification brings this item back.'),
    'set': ('Do every entry now: run each command in order, pass every launch and continue to '
            'Agent in the background in one message (a continue is a fresh Agent with its prompt; '
            'resume only to an Agent tool that takes it), run each run entry through Bash in the '
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
    'lead': ('Pass it to Agent in the background. When its completion notification arrives, save '
             "the lead's JSON answer to {days}/lead.json with the Write tool, then run wuwei next."),
    'propose': ("If that file is missing, first save the lead's JSON answer there with the Write "
                'tool. On exit 1 or 2 show the owner the reason; then run wuwei next.'),
    'setup': ('Ask the owner which repositories WUWEI works on (owner/repo, path, default branch); '
              'run the command for each, which asks its Owner step card; then run wuwei next.'),
    'gate': ('Ask the widget list with AskUserQuestion. On any Approve option run its record command with '
             '<label> replaced by the chosen label; on Change '
             'something ask the owner what to change, edit {days}/lead.json and run wuwei plan propose '
             '{days}/lead.json again; then run wuwei next.'),
    'pr': ('Run it and do any action it prints; on exit 1 with an Owner step card, ask it with '
           'AskUserQuestion, then run it again on Yes. When it prints nothing the PR waits on people: '
           'end the turn with wuwei status --line, the watch wakes you when it changes.'),
    'owner-step': ('Run it; on exit 1 ask the Owner step card it prints with AskUserQuestion, then run '
                   'it again on Yes. Then run wuwei next.'),
    'merge': ('Run it; on exit 1 ask the Owner step card it prints with AskUserQuestion. On Yes run it '
              'again; on No run wuwei plan park {item} --reason "the owner keeps the merge of {pr}". '
              'Then run wuwei next.'),
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
             'framework. With more than one configured repository each candidate also has repo, the '
             'configured repository name it changes. While memory/goals.md has no goals, write each proposed goal as a block '
             '(id, outcome, measure, target, date, priority), never an id alone. Check open '
             'status and overlap against the items of the day and other active work.')
# No single quote in LEAD_BODY: step quotes it without shlex, which hook paths do not import.
PROPOSE = 'run wuwei plan propose '


def register(subparsers):
    parser = subparsers.add_parser('next', help='Print where the day stands and the one next action')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def _row(name, why, command=None, action='run', then=None, **extra):
    return {'state': name, 'action': action, **({'command': command} if command else {}),
            'why': why, 'then': then or THEN.get(action, THEN['run']), **extra}


def approved(data):
    """Approved items in queue order, less those plan carry or park disposed of."""
    return [name for name in data['approved_items'] if name in data['items']
            and (data['items'][name].get('disposition') or {}).get('kind') not in ('carried', 'parked')]


def _seen(directory):
    """(done (state, key) pairs, steward runs, day closed, the PRs whose latest
    merge event is an owner block) from one read of today's events; only lines
    naming a kind next needs are parsed (#346 budget). A row is done when its command ran (the
    done pairs run() records) or it passed with nothing to ask."""
    done, passed, returns, runs, closed, merges = set(), set(), {}, [], False, {}
    path = directory / 'events.jsonl'
    for text in path.read_text(encoding='utf-8').splitlines() if path.is_file() else ():
        if not ('"next.action"' in text or '"steward.run"' in text or '"day.closed"' in text
                or '"merge.' in text):
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
        elif kind == 'day.closed':
            closed = True
        elif kind in ('merge.policy_blocked', 'merge.intent'):  # #816
            merges[payload.get('pr')] = payload.get('reason') if payload.get('owner') is True else None
    # ponytail: a row returned three times counts as done, so a refused or failed command (no
    # PostToolUse span) never holds the day; evidence from PostToolUseFailure would lift it.
    done |= passed | {key for key, count in returns.items() if count >= 3}
    return done, runs, closed, merges


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
    ponytail: one row, not a list; the first runnable item wins and its rows name the rest (#666)."""
    if root is None:
        return _row('no-workspace', 'No WUWEI workspace here; create one with guards logging only in '
                    'the project directory.', 'bin/wuwei init --shadow')
    config = workspace.load_config(root)
    if not config['repos']:
        return _row('setup', 'No repository is configured yet.',
                    'wuwei config add-repo --name <owner/repo> --path <path> --branch <branch>',
                    then=THEN['setup'])
    directory = workspace.day_dir(root)
    days = f'.wuwei/days/{directory.name}'
    data = state.read_state(directory=directory)
    if not data.get('planner_session_id'):
        # Inline, not sessions.current(): hook.py imports this module on every event.
        session = os.environ.get('WUWEI_SESSION_ID', '').strip() or '<session id>'
        return _row('session', "Register this session as today's planner.",
                    f'wuwei plan session {session}')
    returned, runs, closed, merges = _seen(directory)
    returned |= set(ran)
    if not (directory / 'plan.md').is_file():
        if ('pr-flow', '') not in returned:
            return _row('pr-flow', 'Check the PR flow settings once before the day starts.',
                        'wuwei doctor --section pr-flow', then=THEN['pr-flow'])
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
    seats = brief.seats(data)
    if stuck := brief.stuck(data):
        return _row('stuck', f'Seat {stuck[0]} ended with no recorded result.',
                    f'wuwei seat stop {stuck[0]} --unmeasured "seat ended with no recorded result"')
    for ident, finding in data.get('seat_findings', {}).items():  # #646: proposed once
        if ident not in data['items'] and ('finding', ident) not in returned:
            return _row('finding', f"A seat found a small fix: {finding['scope']}. Add it as a small "
                        'item; its ticket follows after it ships.',
                        f'wuwei plan add {ident} --from-finding', item=ident)
    rows = state.in_flight(data)
    running = {item for _, _, item in rows}
    items = data['items']
    names = approved(data)
    # #648: a held item waits on its fix item and takes no seat
    building = sum(items[name]['phase'] in state.BUILD_PHASES and not state.held(data, name) for name in names)
    queued = sum(items[name]['phase'] == 'planned' for name in names)
    waiting = held = None
    found, prs = [], []  # #666: runnable rows first; a PR waits on people, so it comes last
    for name in names:
        phase = items[name]['phase']
        if phase in TERMINAL or name in running:
            continue
        # Inline, not wuwei.tracker: next runs on hook paths.
        ticket = data.get('tickets', {}).get(name, {}).get('id')
        label = f'{name} ({ticket})' if ticket else name
        if phase in state.BUILD_PHASES and (fix := state.held(data, name)):
            held = held or (label, fix)
        elif phase in state.BUILD_PHASES:
            found.append(_row('build', f'{label} is in {phase}; this is its build loop step.',
                              f'wuwei build next {name}', item=name))
        elif phase in ('gate', 'delta'):
            found.append(_row('verdicts', f'{label} is at {phase}; these are its gate steps.',
                              f'wuwei dispatch next {name}', item=name))
        elif phase == 'raised':
            pr = items[name].get('pr')
            if merges.get(pr):  # #816: one owner decision for this PR, on its Owner step card
                found.append(_row('merge', f'{label}: the merge policy does not clear PR {pr}; you decide '
                                  'on its Owner step card.', f'wuwei merge {pr}', item=name,
                                  then=THEN['merge'].format(item=name, pr=pr)))
            else:
                prs.append(_row('pr', f'{label} has PR {pr} open; act on its review state.',
                                f'wuwei pr act {pr}', item=name, then=THEN['pr']))
        elif phase == 'planned' and building < data['cap']:
            if not any(row['state'] == 'dispatch' for row in found):
                found.append(_row('dispatch', f'{min(queued, data["cap"] - building)} planned item(s) can '
                                  f'start, {building} of CAP {data["cap"]} building; this is the launch set.',
                                  'wuwei dispatch next --all', 'set'))
        elif phase == 'planned' and waiting is None:
            waiting = label
    queue = [{'state': row['state'], 'item': row.get('item', ''), 'command': row['command']}
             for row in found + prs]
    queue = {'rows': queue} if len(queue) > 1 else {}
    if found:
        return {**found[0], **queue}
    # #617: one steward at a time, on the newest brief; #624: and not while an item is mid fix round.
    if not state.mid_round(data) and not any(
            seat['role'] == 'steward' and seat['status'] == 'running' for seat in seats.values()):
        stem = str(runs[-1].get('brief', '')).rsplit('/', 1)[-1].removesuffix('.md') if runs else ''
        if stem and stem not in seats:
            return _row('steward', 'Launch the steward seat on its brief.', 'wuwei next --json',
                        'launch', THEN['agent'], brief=runs[-1]['brief'])
    if prs:
        return {**prs[0], **queue}
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
    if held:
        return _row('wait', f'{held[0]} waits on fix item {held[1]}: main is broken; it rebases and '
                    f'reruns its checks once {held[1]} merges.', 'wuwei status --line', 'wait')
    # ponytail: health from recorded watch and heartbeat events, not a doctor run (#346 budget).
    from wuwei.commands.status import scan
    _, watch, beat = scan(directory, {**data, 'now': workspace.now().isoformat()})
    if (watch == 'dead' or beat == 'degraded') and ('doctor', '') not in returned:
        return _row('doctor', f'Watch {watch}, heartbeat {beat}; run the doctor and fix what it '
                    'names.', 'wuwei doctor')
    if not data.get('close_requested'):
        return _row('close', 'Every approved item is merged, parked, carried or escalated; close '
                    'the day.', 'wuwei close', then=THEN['close'])
    if not any(run.get('trigger') == 'close' for run in runs):
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
    queue = ', '.join(' '.join(filter(None, (entry['state'], entry['item']))) for entry in row.get('rows', []))
    return (f"{row['state']}: {row['why']} {row['then']}" + (f'\n{command}' if command else '')
            + (f'\nQueue: {queue}' if queue else ''))


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
        return {**row, 'widget': widget} if widget else None
    if name == 'build':
        from wuwei.commands import build
        action = build.next_action(item, root=root)
        if action['action'] in ('done', 'park'):
            return None
        then = THEN[{'check': 'background', 'continue': 'continue'}.get(action['action'], 'agent')]
        return {**keep, **action, 'why': row['why'], 'then': then}
    if name == 'verdicts':
        from wuwei import dispatch
        action = dispatch.next_step(item, root)
        if action['action'] in ('fix', 'parked'):  # a PARK verdict or the owner's No parked it
            return None
        if action['action'] == 'escalate':  # the owner decides on the command's Owner step card
            return _row(name, f"{item}: {action['reason']}", action['command'], item=item,
                        then=THEN['owner-step'])
        if action['action'] == 'raise':
            return _shepherd(root, item, action['notes'], row['why'])
        if action['action'] == 'polish':  # #723
            return _row('polish', f"{item}: every gate passed with {len(action['notes'])} review "
                        'note(s); one polish round fixes them before the PR.', action['command'],
                        item=item, then=f"Run the command, or run {action['skip']} instead when the "
                        'notes are not small fixes inside the item; then run wuwei next.')
        return {**keep, **action, 'why': row['why'], 'then': THEN['set']}
    if name == 'dispatch':
        from wuwei import dispatch
        return {**keep, **dispatch.launch_set(root), 'why': row['why'], 'then': THEN['set']}
    return row


def _shepherd(root, item, notes, why):
    """The shepherd raises the PR: dispatch's brief command, its launch, or a card when it
    stopped without one (#783: one raise action for dispatch, build and next)."""
    from wuwei import dispatch
    action = dispatch.raise_action(root, state.read_state(root), item, notes)
    if action.get('commands'):
        return _row('raise', f'{why} Every gate passed; brief the shepherd to raise the PR.',
                    action['commands'][0], item=item)
    if action['seats']:
        return {'state': 'raise', 'item': item, **action['seats'][0],
                'why': f'{why} Launch the shepherd to raise the PR.', 'then': THEN['agent']}
    return _row('raise', f'shepherd-{item} stopped without raising the PR.', f'wuwei why {item}',
                'card', THEN['owner'], item=item)


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


def orientation(row, enforce, spec=None, session=None):
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
        ENFORCE[enforce],
        *([f'Spec: {spec}'] if spec else []),
        f'Next: {shown}',
        entry,
        f'Reference: wuwei --help lists every command; owner guide: {plugin}/docs/site/daily.md',
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
            if 'rows' in row:  # resolve builds new dicts; the queue rides on the action
                action = {**action, 'rows': row['rows']}
            if args.json:  # a person's look-up never moves the day
                _record(root, action, named(action), ran)
            row = action
    except ERRORS as exc:
        row, code = _row('unmeasured', str(exc), 'wuwei doctor'), UNRUN
        print(f'wuwei next: {exc}', file=sys.stderr)
    print(json.dumps(row) if args.json else text(row))
    return code
