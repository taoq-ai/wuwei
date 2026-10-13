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
    True: ('Guards enforce: records, publishing and seat launches without a matching brief '
           'block; plugin integrity only warns; deploys, releases and approve-tier messages ask on '
           'a card; merges and approvals stay owner-only; outward text, scratch paths and seat '
           'capacity are logged. A refusal names its reason and the accepted form: '
           'use that form, never a way around it.'),
}
ERRORS = (OSError, ValueError, KeyError, TypeError, UnicodeError)
EXECUTABLE = ('wuwei is the absolute path in .wuwei/executable: read it once and use it as the '
              'first word of a plain command, never through a variable')
LOOP = ('Loop: run wuwei next --json, do every launch and every duty it returns, ask its one '
        'decision when there is one, and run it again when the result or a completion '
        'notification arrives.')
THEN = {
    'run': 'Run the command, then run wuwei next.',
    'background': 'Run the command through Bash in the background; run wuwei next when it exits.',
    'agent': ('Pass it to Agent in the background, then run wuwei next; its completion '
              'notification brings this item back.'),
    # #614: Claude Code's Agent has no resume; a continue binds as a fresh Agent.
    'continue': ('Launch a fresh Agent in the background with the prompt unchanged and agent_type '
                 'as subagent_type (pass resume only to an Agent tool that takes it), then run wuwei '
                 'next; its completion notification brings this item back.'),
    'set': ('Do every launch and every duty now: run each command in order, pass every launch and '
            'continue to Agent in the background in one message (a continue is a fresh Agent with '
            'its prompt; resume only to an Agent tool that takes it), run each run entry through '
            'Bash in the background, write each duty and run its record command, and ask the '
            "decision's card with AskUserQuestion when there is one; then run wuwei next. When "
            'nothing changed since the last call, end the turn with wuwei status --line instead.'),
    'decide': ('Ask its card with AskUserQuestion; on Yes run its command, on No leave it; then run '
               'wuwei next.'),
    'card': ('Ask the widget list with AskUserQuestion, record each answer with its record '
             'command, then run wuwei next.'),
    'owner': ('Show the owner the why and the command in one line; run wuwei next when they say '
              'it is done.'),
    'wait': ('End the turn with the output of wuwei status --line; run wuwei next when a '
             'completion notification arrives.'),
    'done': 'The day is closed; tomorrow starts with wuwei next.',
    # #887: the PR loop between owner messages
    'pr-wait': ('Run the command through Bash in the background (or Monitor: one line per PR change); '
                'run wuwei next when it exits. Then end the turn with the output of wuwei status --line.'),
    # Planner-facing lines of single rows; step formats {days} and {dm}.
    'pr-flow': ('Run wuwei doctor --section pr-flow as its own command. On exit 1 show its output to the owner '
                'unchanged, once; then run wuwei next.'),
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
           'end the turn with wuwei status --line; run wuwei next when the owner returns.'),
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
             'framework. Candidate kind defaults to build; use review with pr and review_role '
             'for a PR verdict, or measure with no paths for read-only evidence. '
             'With more than one configured repository each candidate also has repo, the '
             'configured repository name it changes. While memory/goals.md has no goals, or when the owner changed '
             'the goals, write each goal as a block '
             '(id, outcome, measure, target, date, priority), never an id alone. Check open '
             'status and overlap against the items of the day and other active work.')
# No single quote in LEAD_BODY: step quotes it without shlex, which hook paths do not import.
PROPOSE = 'run wuwei plan propose '


def register(subparsers):
    parser = subparsers.add_parser('next', help='Print where the day stands and the one next action')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--housekeeping', action='store_true', help='Reap owned leftovers and list current findings')
    parser.add_argument('--background', action='store_true', help='Record and run a background wait')
    parser.add_argument('argv', nargs='*')
    parser.set_defaults(func=run)


def _row(name, why, command=None, action='run', then=None, **extra):
    return {'state': name, 'action': action, **({'command': command} if command else {}),
            'why': why, 'then': then or THEN.get(action, THEN['run']), **extra}


def approved(data):
    """Approved items in queue order, less those plan carry or park disposed of."""
    return [name for name in data['approved_items'] if name in data['items']
            and (data['items'][name].get('disposition') or {}).get('kind') not in ('carried', 'parked')]


def building(data):
    """#910: the one build slot count for derive, the launch set, build next, next and the launch
    guard: approved items in a build phase, not held (#648), in plan order. Running and reserved
    builds alike: a stopped builder awaiting its checks keeps its slot until its handoff."""
    return [name for name in approved(data) if data['items'][name]['status'] != 'done'
            and data['items'][name]['phase'] in state.BUILD_PHASES
            and not state.held(data, name)]


def slot(data, item, cap):
    """#910: item's builder may launch: it is among the first CAP holders, or a slot is free."""
    holders = building(data)
    return item in holders[:cap] or len(holders) < cap


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
        elif kind in ('merge.policy_blocked', 'merge.intent'):  # #816; G1: (owner reason, when it held)
            owner = payload.get('owner') is True and kind == 'merge.policy_blocked'
            merges[payload.get('pr')] = (payload.get('reason'), None) if owner else (None, row.get('ts'))
    # ponytail: a row returned three times counts as done, so a refused or failed command (no
    # PostToolUse span) never holds the day; evidence from PostToolUseFailure would lift it.
    done |= passed | {key for key, count in returns.items() if count >= 3}
    return done, runs, closed, merges


def _carry(root, directory):
    """True when the prior day left unfinished items the proposal does not name again: plan
    approve --import-yesterday imports them all and refuses an overlap."""
    prior = sorted(path.name for path in (root / '.wuwei/days').glob('????-??-??')
                   if path.is_dir() and path.name < directory.name)
    if not prior or not state.day_started(root / '.wuwei/days' / prior[-1]):
        return False
    items = state.read_state(directory=root / '.wuwei/days' / prior[-1])['items']
    left = {name for name, item in items.items() if item['phase'] != 'merged' and item['status'] != 'done'}
    proposal = directory / 'proposal.json'
    named = ({row['id'] for row in json.loads(proposal.read_text(encoding='utf-8'))['candidates']}
             if proposal.is_file() else set())
    return bool(left) and not left & named


def refill_limit(root, data):
    """The approved day's discovery bounds, shared by next, admission and report."""
    from datetime import date, datetime, time
    config = workspace.load_config(root)
    end = data.get('envelope', {}).get('end')
    if end:
        now = workspace.now().astimezone(workspace.zone(config))
        try:
            deadline = datetime.fromisoformat(end)
        except (TypeError, ValueError):
            try:
                deadline = datetime.combine(date.fromisoformat(workspace.day_dir(root).name),
                                            time.fromisoformat(end))
            except (TypeError, ValueError):
                deadline = None
        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=now.tzinfo)
        if deadline is not None and now >= deadline:
            return f'Refill stopped at envelope.end ({end}).'
    history = data.get('refills', [])
    limit = config['plan']['max_refills']
    if len(history) >= limit and not any(row['pending'] for row in history):
        return f'Refill limit reached ({limit}).'
    return ''


def refill(root, data):
    """Read-only continuation of the lead/propose path after an exhausted queue (#949)."""
    from wuwei import goals
    if refill_limit(root, data):
        return None
    path = workspace.day_dir(root) / 'goals.md'
    text = path.read_text(encoding='utf-8') if path.is_file() else ''
    opened = ({key: value for key, value in goals.parse(text).items() if key in data['goals']}
              if goals.defined(text) else {})
    history = data.get('refills', [])
    pending = next((row for row in history if row['pending']), None)
    number = pending['number'] if pending else len(history) + 1
    directory = workspace.day_dir(root)
    days = f'.wuwei/days/{directory.name}'
    name = f'lead-{number}'
    if pending:
        return _row('propose', 'The refill has one owner decision waiting.',
                    f'wuwei plan propose {days}/{name}.json --refill {number}', then=THEN['propose'])
    if not opened or any(row['goals'] == opened and not row['admitted'] for row in history):
        return None
    seat = data['seats'].get(name)
    if seat and seat['status'] == 'running':
        return _row('wait', 'The lead is finding work against open goals.', 'wuwei status --line', 'wait')
    if (directory / f'{name}.json').is_file() or seat:
        return _row('propose', 'Admit the refill from the lead answer.',
                    f'wuwei plan propose {days}/{name}.json --refill {number}', then=THEN['propose'])
    if not (directory / f'briefs/{name}.md').is_file():
        import shlex
        body = (LEAD_BODY + f' Refill only the gate-approved goals in {days}/goals.md; '
                f'Read approved goal IDs and all items in {days}/state.json, and wuwei status --line. '
                'Do not re-propose finished, parked or other existing items. '
                'Memory context is in .wuwei/memory/goals.md; it does not expand today\'s goals. '
                'Use the morning discovery sources attached to this lead brief. '
                'Keep the approved seat policy and envelope. Return no candidates if no work is found.')
        return _row('refill', 'Open goals need another discovery pass.',
                    f'wuwei seat brief lead day {name} --body ' + shlex.quote(body))
    return _row('refill', 'Launch the lead on the open goals.', 'wuwei next --json', 'launch',
                THEN['lead'].format(days=days).replace('/lead.json', f'/{name}.json'),
                brief=f'{days}/briefs/{name}.md')


def step(root, ran=(), *, findings=None):
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
    from wuwei import watch
    live_waits = []
    process_code, processes = watch.housekeeping(root, data=data, live_waits=live_waits)
    if findings is not None:
        findings.extend(processes)
    if any(row['kind'] == 'process' for row in processes):
        return {'state': 'set', 'action': 'set', 'launches': [], 'decision': None, 'parks': [], 'rows': [],
                'duties': [{'item': 'day', 'duty': 'housekeeping',
                            'prompt': 'Reap owned waits; inspect the remaining cleanup listing.',
                            'record': 'wuwei next --housekeeping'}],
                'why': 'Housekeeping: ' + '; '.join(row['why'] for row in processes), 'then': THEN['set']}
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
                            f"wuwei seat brief lead day lead --body '{LEAD_BODY}'")
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
    stuck = brief.stuck(data)
    if not stuck and not closed:
        from wuwei import derive
        listing = derive.listing(directory)
        owned = set(data['raised_prs'] + data['claimed_prs'])
        events = directory / 'events.jsonl'
        for line in events.read_text(encoding='utf-8').splitlines() if events.is_file() else ():
            if '"pr.unclaimed"' not in line:
                continue
            event = json.loads(line)
            if event.get('kind') != 'pr.unclaimed':
                continue
            payload = event['payload']
            pr = payload['pr']
            if pr.split('#')[0].casefold() not in {row['name'].casefold() for row in config['repos']}:
                continue
            if pr in owned or ('pr-claim', pr) in returned:
                continue
            pull = listing['pulls'].get(pr)
            repo = listing['repos'].get(pr.split('#')[0]) or {}
            if (pull and pull.get('state') in ('closed', 'merged')
                    or repo.get('failed') or not pull and repo.get('at')):
                continue
            item = payload.get('item')
            goal = (data['items'].get(item) or {}).get('goal')
            choice = goal or (f'<one of {", ".join(data["goals"])}>' if len(data['goals']) > 1 else None)
            command = f"wuwei pr claim {payload['url']}" + (f' --item {item}' if item else '')
            command += f' --goal {choice}' if choice else ''
            why = (f"{pr} belongs to {item}. Run {item}'s gates first, then claim its existing PR."
                   if item else f'{pr} was opened outside WUWEI; claim it before starting more work.')
            if payload.get('reason'):
                why += f' Earlier automatic claim refused: {payload["reason"]}.'
            return _row('pr-claim', why, command, 'owner' if choice and not goal else 'run', item=pr)
    from wuwei import derive
    launches = [{'kind': 'stop', 'item': seats[name]['item'], 'why': f'Seat {name} ended with no recorded result.',
                 'command': brief.recovery(name, seats[name])} for name in stuck]
    launches += [{'kind': 'stop', 'item': row.get('item', 'day'), 'why': row['why'],
                  'command': row['command']} for row in processes if row['kind'] in ('seat', 'build')
                 and row['command'] not in {launch['command'] for launch in launches}]
    launches += [{'kind': 'finding', 'item': ident, 'command': _finding_command(ident, finding, data, config),
                  'why': f"A seat found a small fix: {finding['scope']}. Add it as a small item."}
                 for ident, finding in data.get('seat_findings', {}).items()  # #646: proposed once
                 if ident not in data['items'] and ('finding', ident) not in returned]
    found = derive.offers(data, root, config, merges)
    launches += found['launches']
    # #906: the shepherd duty is a launch; it stays a due row (pr act its step) only where a seat
    # could have launched and did not: a raised item with no launch offered and nothing in flight
    busy = {launch['item'] for launch in found['launches']} | {item for _, _, item in state.in_flight(data)}
    due = [duty for duty in derive.duties(root, config, directory, data) if duty['duty'] != 'shepherd'
           or (data['items'].get(duty['item']) or {}).get('phase') == 'raised' and duty['item'] not in busy]
    decision = found['decision']
    if decision:
        pr = decision['command'].split()[-1]
        decision['then'] = (THEN['decide'] if decision.get('card') else
                            THEN['merge'].format(item=decision['item'], pr=pr)
                            if decision['command'].startswith('wuwei merge ') else THEN['owner-step'])
    if launches or due or decision or found['parks']:
        parts = [f'{len(launches)} launch(es)' if launches else '', f'{len(due)} due duty(ies)' if due else '',
                 'one owner decision' if decision else '']
        return {'state': 'set', 'action': 'set', 'launches': launches, 'duties': due,
                'decision': decision, 'parks': found['parks'], 'rows': found['rows'],
                'why': 'Ready now: ' + ', '.join(filter(None, parts)) + '.' if any(parts) else
                'A verdict parks an item in code.', 'then': THEN['set']}
    rows = state.in_flight(data)
    items = data['items']
    names = approved(data)
    count = len(building(data))
    waiting = next((name for name in names if items[name]['phase'] == 'planned'), None)
    held = next(((name, fix) for name in names if items[name]['phase'] in state.BUILD_PHASES
                 and (fix := state.held(data, name))), None)
    prs = [row for row in found['rows'] if row['state'] in ('pr', 'unmeasured')]
    # #617: one steward at a time, on the newest brief; #624: and not while an item is mid fix round.
    if not state.mid_round(data) and not any(
            seat['role'] == 'steward' and seat['status'] == 'running' for seat in seats.values()):
        stem = str(runs[-1].get('brief', '')).rsplit('/', 1)[-1].removesuffix('.md') if runs else ''
        if stem and stem not in seats:
            return _row('steward', 'Launch the steward seat on its brief.', 'wuwei next --json',
                        'launch', THEN['agent'], brief=runs[-1]['brief'])
    builders = sorted((seat.get('started_at') or '', name) for name, seat in seats.items()
                      if seat['status'] == 'running' and seat['role'] == 'builder')
    text = state.in_flight_text(rows)
    if waiting and builders:
        return _row('wait', f'{waiting} waits: {count} of CAP {data["cap"]} building; '
                    f'{builders[0][1]} started first ({builders[0][0] or "start unrecorded"}) and '
                    f'is expected to free first; SubagentStop records each result. Running: {text}',
                    'wuwei status --line', 'wait')
    if rows:
        return _row('wait', f'Running: {text}; SubagentStop records each seat, and a background '
                    'check reports when it exits.', 'wuwei status --line', 'wait')
    if held:
        return _row('wait', f'{held[0]} waits on fix item {held[1]}: main is broken; it rebases and '
                    f'reruns its checks once {held[1]} merges.', 'wuwei status --line', 'wait')
    if live_waits:
        return _row('wait', 'The recorded PR wait is still running; it reports when PRs change.',
                    'wuwei status --line', 'wait', rows=found['rows'])
    if prs:  # #666: a PR waiting on people is a wait, never a row to run; #887: pr wait wakes it
        waits = ', '.join(row['item'] for row in prs if row['state'] == 'pr')
        why = [f'{waits}: the PR waits on people; wuwei pr wait exits when it changes.'] if waits else []
        why += [row['why'] + '.' for row in prs if row['state'] == 'unmeasured']  # #900
        return _row('wait', ' '.join(why), 'wuwei pr wait', 'background', THEN['pr-wait'], rows=found['rows'])
    if not closed and not data.get('close_requested') and (row := refill(root, data)):
        return row
    if not data.get('close_requested'):
        return _row('close', 'Every approved item is merged, parked, carried or escalated; close '
                    'the day.', 'wuwei close', then=THEN['close'])
    if not any(run.get('trigger') == 'close' for run in runs):
        return _row('close', 'Close the day once nothing holds it.', 'wuwei close', then=THEN['close'])
    if not (directory / 'retro' / f'{directory.name}.md').is_file():
        return _row('retro', 'Compile the steward retro.', 'wuwei retro')
    if ('promote', '') not in returned:
        return _row('promote', 'Land the supported charter learnings.', 'wuwei retro --promote')
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
    """The action for a person: one paragraph, then the command on its own line; a set names
    each launch, duty and the decision on its own line."""
    if row['state'] == 'set':
        lines = [f"set: {row['why']} {row['then']}"]
        lines += [f"{launch['kind']} {launch['item']}: {launch.get('command') or launch.get('action')}"
                  for launch in row['launches']]
        lines += [f"duty {duty['duty']} {duty['item']}: {duty['prompt']} Record: {duty['record']}"
                  for duty in row['duties']]
        if row['decision']:
            lines.append(f"owner {row['decision']['item']}: {row['decision']['why']} {row['decision']['command']}")
        lines += [f"unmeasured {entry['why']}" for entry in row['rows'] if entry['state'] == 'unmeasured']
        return '\n'.join(lines)
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


def _resolve(row, root):
    """The row with its prompts: each launch of a set resolved through its resolver (the launch
    set, within CAP and the free host seats), a seat launch row through its brief, a card row
    with its widget list. Called by the next command only; it never loops."""
    import shlex
    if row['state'] == 'set':
        from wuwei import derive, dispatch
        value = dispatch.launch_set(root) if row['launches'] else {'entries': [], 'capacity': ''}
        if value.get('listing_refreshed') and any(
                launch['command'] == 'wuwei dispatch next --all' for launch in row['launches']):
            row = step(root)
            if row['state'] != 'set':
                return row
            value = dispatch.launch_set(root) if row['launches'] else {'entries': [], 'capacity': ''}
        starts = {launch['item']: launch['why'] for launch in row['launches']
                  if launch['command'] == 'wuwei dispatch next --all'}
        for entry in value['entries']:
            if entry['action'] == 'start' and entry['item'] in starts:
                entry['why'] = starts[entry['item']]
        data = state.read_state(root)
        runs = [launch for launch in row['launches']  # PR, merge, seat stop and finding steps run as is
                if not derive.seated(data, launch)]
        launches = [{**launch, 'action': 'run'} for launch in runs] + value['entries']
        if (launches and all(launch['action'] == 'wait' for launch in launches) and not row['duties']
                and not row['decision'] and any(launch.get('until') for launch in launches)):
            # #845: every launch waits, one for a usage window; sleep past the earliest reset, then next
            from datetime import datetime
            until = min((launch['until'] for launch in launches if launch.get('until')), key=datetime.fromisoformat)
            seconds = max(60, int((datetime.fromisoformat(until) - workspace.now()).total_seconds()) + 61)
            reasons = '; '.join(dict.fromkeys(launch['reason'] for launch in launches))
            return _row('wait', f'{reasons}; running seats finish. wuwei next offers them again after the reset.',
                        f'sleep {seconds}', 'background', until=until)
        decision = row['decision']
        asked = next((launch for launch in launches if launch['action'] == 'escalate'), None)
        # #902: a launch that resolved to a park, a finished build or an owner step is no launch;
        # the first owner step is the set's decision, the rest come back on the next derivation
        launches = [launch for launch in launches if launch['action'] not in ('escalate', 'parked', 'done')]
        if decision is None and asked:
            decision = {'item': asked['item'], 'why': f"{asked['item']}: {asked['reason']}",
                        'command': asked['command'], **({'card': asked['card']} if asked.get('card') else {}),
                        'then': THEN['decide'] if asked.get('card') else THEN['owner-step']}
        return {**row, 'launches': launches, 'decision': decision,
                **({'capacity': value['capacity']} if value.get('capacity') else {})}
    name = row['state']
    keep = {'state': name, **({'item': row['item']} if row.get('item') else {})}
    if row['action'] == 'launch':
        action = brief.seat_action('lead' if name in ('lead', 'refill') else 'steward', root / row['brief'],
                                   root, root)
        return {**keep, **action, 'why': row['why'], 'then': row['then']}
    if row['action'] == 'card' and row['command'].startswith('wuwei '):
        widget = _widget(shlex.split(row['command'])[1:])
        return {**row, 'widget': widget}
    return row


def resolve(row, root):
    """Record only long waits; one-shot state writers finish without reaping."""
    return recorded(_resolve(row, root))


def recorded(action):
    """Format wait ownership without resolving seats or writing state."""
    command = action.get('command', '')
    if action['action'] == 'background' and (command == 'wuwei pr wait' or command.startswith('sleep ')):
        action = {**action, 'command': f'wuwei next --background -- {command}'}
    return action


def named(action):
    """The exact commands an action names, a command its then line names included."""
    found = [action['command']] if action.get('command') else []
    if action.get('state') == 'pr-claim' and action.get('command'):
        prefix = action['command'].split(' --goal ', 1)[0]
        found += [prefix, prefix + ' --goal *']
    found += [widget['record'] for widget in action.get('widget', []) if widget.get('record')]
    found += action.get('commands', [])
    found += [duty['record'] for duty in action.get('duties', [])]
    found += [action['decision']['command']] if action.get('decision') else []
    for entry in action.get('launches', []):
        found += named({**entry, 'then': ''})
    for entry in action.get('entries', []) + action.get('seats', []):
        found += [entry[key] for key in ('command', 'receive') if entry.get(key)]
        found += entry.get('commands', [])
    if PROPOSE in action['then']:
        found.append('wuwei plan propose ' + action['then'].split(PROPOSE, 1)[1].split()[0])
    return found


def _record(root, action, commands, ran=()):
    """Append the reserved next.action event; nothing without today's state (#551)."""
    directory = workspace.day_dir(root)
    if not state.day_started(directory):
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


def _finding_command(ident, finding, data, config):
    """#908: a finding's plan add, with the goal and repository selections it cannot infer."""
    choices = (('goal', data.get('goals', [])), ('repo', [repo['name'] for repo in config['repos']]))
    return ' '.join([f'wuwei plan add {ident} --from-finding', *(
        f'--{key} <one of {", ".join(values)}>' for key, values in choices if not finding.get(key) and len(values) > 1)])


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
    shown = text(recorded(row))
    if session:
        shown = shown.replace('<session id>', session)
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


def _supervise(root, config, refreshed):
    """#847: merge.poll (red base revert, 5.6 outcomes) with each listing refresh, and while the
    merge journal holds a merge in its window, at most once per pr.poll_seconds."""
    from contextlib import redirect_stdout
    from datetime import datetime
    from wuwei import merge, watch
    if not refreshed:
        polled = watch.saved(root).get('merge_polled_at')
        if polled and (workspace.now() - datetime.fromisoformat(polled)).total_seconds() < config['pr']['poll_seconds']:
            return
        if not merge.supervised(root):
            return
    with redirect_stdout(sys.stderr):  # supervision lines never reach next's row
        merge.poll(root)
    watch.save(root, {'merge_polled_at': workspace.now().isoformat()})


def run(args):
    if getattr(args, 'argv', None) and (getattr(args, 'housekeeping', False)
                                       or not getattr(args, 'background', None)):
        raise ValueError('next takes no positional arguments; run wuwei next --help')
    if getattr(args, 'housekeeping', False):
        from wuwei import watch
        code, rows = watch.housekeeping(workspace.find_workspace(), reap=True)
        for row in rows:
            print(f"{row['kind']}: {row['why']}\n{row['command']}")
        return code
    if getattr(args, 'background', None):
        from wuwei import watch
        return watch.background(workspace.find_workspace(), args.argv)
    code = CLEAN
    try:
        try:
            root = workspace.find_workspace()
        except FileNotFoundError:
            root = None
        ran = _ran(root) if root is not None else []
        if root is not None and state.day_started(workspace.day_dir(root)):
            from wuwei import derive
            config = workspace.load_config(root)
            data = state.read_state(root)
            refreshed = derive.stale(root, config, data)
            directory = workspace.day_dir(root)
            log = directory / 'events.jsonl'
            owned = set(data['raised_prs'] + data['claimed_prs'])
            extra = set()
            done, _, closed, _ = _seen(directory)
            done.update(map(tuple, ran))
            if not closed:
                listing = derive.listing(directory)
                for line in log.read_text(encoding='utf-8').splitlines() if log.is_file() else ():
                    if '"pr.unclaimed"' not in line:
                        continue
                    event = json.loads(line)
                    if event.get('kind') != 'pr.unclaimed':
                        continue
                    ref = event['payload']['pr']
                    if (ref in owned or ('pr-claim', ref) in done
                            or (listing['pulls'].get(ref) or {}).get('state') in ('closed', 'merged')):
                        continue
                    repo = ref.split('#')[0]
                    configured = next((row['name'] for row in config['repos']
                                       if row['name'].casefold() == repo.casefold()), None)
                    if configured:
                        at = derive.when((listing['repos'].get(configured) or {}).get('at')
                                         or (None if listing['repos'] else listing['fetched_at']))
                        created = derive.when(event['ts'])
                        if (at is None or created and at < created
                                or (workspace.now() - at).total_seconds() >= config['pr']['poll_seconds']):
                            extra.add(configured)
            if extra:
                refreshed = sorted(set(refreshed if not isinstance(refreshed, bool) else ()) | extra)
            if refreshed:
                failed = derive.refresh(root, config, refreshed)  # #907: each due repository on its own
                if failed:
                    print(f'wuwei next: PR listing not refreshed ({failed}); those PR rows are unmeasured '
                          'until wuwei next reads them again after pr.poll_seconds', file=sys.stderr)
            _supervise(root, config, refreshed)
        findings = []
        row = step(root, map(tuple, ran), findings=findings)
        for finding in findings:
            if finding['kind'] not in ('process', 'seat', 'build'):
                print(f"Housekeeping: {finding['why']}; review: {finding['command']}", file=sys.stderr)
        if root is not None:
            from wuwei import dispatch
            from wuwei.commands.build import PortExit
            if row['state'] == 'set' and row['parks']:  # PARK parks in code, recorded once
                for item in row['parks']:
                    dispatch.next_step(item, root)
                row = step(root, map(tuple, ran))
            try:
                action = resolve(row, root)
            except (dispatch.Refused, brief.Refused) as exc:
                action, code = {**row, 'why': str(exc)}, FINDINGS
            except PortExit as exc:
                if exc.code != 1:
                    raise ValueError(str(exc)) from exc
                action, code = {**row, 'why': str(exc)}, FINDINGS
            if any(launch.get('action') == 'refused' for launch in action.get('launches', ())):
                code = FINDINGS  # each refused launch names its reason; the rest still run
            if args.json:  # a person's look-up never moves the day
                _record(root, action, named(action), ran)
            row = action
    except ERRORS as exc:
        row, code = _row('unmeasured', str(exc), 'wuwei doctor'), UNRUN
        print(f'wuwei next: {exc}', file=sys.stderr)
    print(json.dumps(row) if args.json else text(row))
    return code
