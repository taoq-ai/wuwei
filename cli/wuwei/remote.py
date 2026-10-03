"""Commands from the owner DM: the vocabulary, the remote-command guards, one session per thread."""

import base64
import binascii
import hmac
import json
import os
import re
from types import SimpleNamespace

from wuwei import (control_plane, decision, inbox, obligations, outward, registry, report, security,
                   sessions, state, watch, workspace)
from wuwei.registry import Result


# Every fixed line passes the default outward lint: messages to the owner DM are linted,
# without the third-person owner rules, since they are addressed to the owner.
VOCABULARY = ('Commands: plan, status, report, ask <question>, stop <session>, stop all. '
              'Decisions: approve D-n, option X on D-n, more D-n, drop it.')
UNAVAILABLE = 'Not available in this version. ' + VOCABULARY
FAILED = 'That command could not run; see the listener log on the host.'
CHANGED = 'Refused: this sender does not match the pinned identity. Confirm it on the host.'
CONFIRM = 'Reply confirm within 2 minutes to run it, or send it again ending with a current code.'
LOW_MEMORY = 'Not started: free memory on the host is below the floor.'
NOTHING = 'Nothing to confirm from the last 2 minutes.'
ANSWERED = ('Not recorded: {identifier} already has option {option} from this DM. '
            'Record the outcome on the host to change it.')
RECORDED = ('Recorded {identifier} option {option} as your outcome; it can be undone, '
            'so no host step is needed.')
NOTED = ('Noted {identifier} option {option}. {identifier} cannot be undone, so confirm it on '
         'the host: decide {identifier} {option}.')
NOT_PENDING = '{identifier} is not waiting on you.'
ON_HOST = 'The full record of {identifier} is on the host.'
FACTOR = frozenset({'plan', 'ask'})  # commands that need a code or a confirm reply
WINDOW = 120  # seconds a code or a confirmation counts
PIN = r'[A-Z0-9]+/[UW][A-Z0-9]+'  # control_plane.owner: <team id>/<user id>
ASK_TOOLS = ('Read', 'Glob', 'Grep')
PLAN_PROMPT = ('Invoke Skill wuwei:wuwei-plan. This run is headless, started from the '
               'control plane: nobody can answer AskUserQuestion. For each question, write '
               'a decision record from `wuwei decision template` to today\'s decisions '
               'directory as the next D-n, run `wuwei decision route <id>`, and end your '
               'turn. The answer resumes this session as "Decision D-n: option X."')
ASK_PROMPT = 'Answer from this workspace and its repositories, read-only; change nothing. Question: '
# A refused tool is never granted from the phone: granting one stays a host change.
DENIAL = '''Question: Session {session} was refused {tool}. How should it continue?
Context: The session runs with its role tools only; {tool} is outside them.
Options:
| Option | Description |
| --- | --- |
| A | Resume the session without {tool} |
| B | Do nothing and leave session {session} idle |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Stays inside the role tools | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Progress | 5 | 5 | 1 |
Recommendation: A
Confidence: medium
Reversibility: two-way
Blast radius: One remote session.
Pre-mortem: The work needs the refused tool.
Revisit: Grant the tool on the host if the work needs it.
Decided-by: owner
Outcome: pending
'''


def parse(text):
    """Return (verb, argument) for one vocabulary command, else None."""
    words = re.sub(r'[.!]$', '', ' '.join(text.split()))
    lower = words.casefold()
    if re.fullmatch(r'plan(?: .*)?', lower):
        return 'plan', ''
    if lower in ('status', 'report'):
        return lower, ''
    if lower == 'confirm':
        return 'confirm', ''
    if lower == 'stop all':
        return 'stop', 'all'
    if match := re.fullmatch(r'run ([a-z0-9][a-z0-9_-]*)', lower):
        return 'run', match[1]
    if match := re.fullmatch(r'(?i:ask) (.+)', words):
        return 'ask', match[1]
    if re.fullmatch(r'cloud \S+ .+', lower):
        return 'cloud', ''
    if match := re.fullmatch(r'stop ([0-9a-f][0-9a-f-]{7,35})', lower):
        return 'stop', match[1]
    if match := re.fullmatch(r'more (d-[1-9][0-9]*)', lower):
        return 'more', match[1].upper()
    return None


def split(text):
    """(text, code): a trailing six-digit code is the second factor, not part of the command."""
    match = re.fullmatch(r'(.*\S)\s+([0-9]{6})', text.strip(), re.S)
    return (match[1], match[2]) if match else (text, '')


def totp(key, step):
    """RFC 6238 with HMAC-SHA1 and six digits, for one 30 s step."""
    digest = hmac.digest(key, step.to_bytes(8, 'big'), 'sha1')
    offset = digest[-1] & 15
    return f'{(int.from_bytes(digest[offset:offset + 4], "big") & 0x7fffffff) % 10**6:06d}'


def sender(config, event):
    """owner, changed (same user id, other or no team) or other, against control_plane.owner."""
    pin = config['control_plane']['owner']
    if not re.fullmatch(PIN, pin):
        raise ValueError(f'control_plane.owner must pin <team>/<user>; this message came from {event["sender"]}; the owner checks control_plane.owner with bin/wuwei config check')
    if event['sender'] == pin:
        return 'owner'
    return 'changed' if event['sender'].rsplit('/', 1)[-1] == pin.rsplit('/', 1)[-1] else 'other'


def _today(root):
    return watch.records(workspace.day_dir(root) / 'events.jsonl')


def acknowledge(root):
    """Owner action: clear today's refused-sender pages after host confirmation; (code, message)."""
    from hashlib import sha256
    from wuwei import integrity
    rows = _today(root)
    done = {identifier for row in rows if row['kind'] == 'remote.acknowledged'
            for identifier in row['payload'].get('ids', [])}
    ids = [row['payload']['id'] for row in rows if row['kind'] == 'remote.refused'
           and row['payload'].get('id') and row['payload']['id'] not in done]
    if not ids:
        return 0, 'remote ack: no refused sender message today'
    token = sha256('\n'.join(ids).encode()).hexdigest()[:12]
    if not integrity._host_confirm(token, prompt=f'Acknowledge the refused sender messages '
                                   f'{", ".join(ids)} on this host.'):
        return 1, 'remote ack: owner confirmation declined; rerun bin/wuwei remote ack in a host terminal and answer y'
    state.append_event('remote.acknowledged', {'ids': ids}, root=root)
    return 0, f'remote ack: acknowledged {len(ids)} refused sender messages'


def replied(root, identifier):
    """The option of today's first decision.replied for this id, else None."""
    return next((row['payload'].get('option') for row in _today(root)
                 if row['kind'] == 'decision.replied' and row['payload'].get('id') == identifier), None)


def confirmation(root):
    """The inbox line of the latest plan or ask pending under WINDOW seconds, once, else None."""
    rows = _today(root)
    row = next((row for row in reversed(rows) if row['kind'] == 'remote.pending'
                and row['payload'].get('command') in FACTOR), None)
    if row is None or (workspace.now() - obligations._time(row['ts'])).total_seconds() > WINDOW \
            or any(other['kind'] == 'remote.confirmed' and other['payload'].get('id') == row['payload']['id']
                   for other in rows):
        return None
    return next((line for line in inbox.read(root) if line['id'] == row['payload']['id']), None)


# ponytail: used steps are read from today's events only; a code accepted in the last minute
# of a day can be replayed in the first minute of the next. Keep the last step in the inbox
# directory if that matters.
def code_step(root, event, code):
    """The TOTP step a fresh, unused code in this message matches, else None."""
    secret = os.environ.get('WUWEI_TOTP_SECRET', '')
    ts = float(event['ts'])
    if not code or not secret or workspace.now().timestamp() - ts > WINDOW:
        return None
    secret = secret.replace(' ', '').upper()
    try:
        key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    except binascii.Error:
        raise ValueError('WUWEI_TOTP_SECRET is not base32; set WUWEI_TOTP_SECRET in .wuwei/env to the base32 secret from setup') from None
    used = max((row['payload']['step'] for row in _today(root) if row['kind'] == 'remote.confirmed'
                and row['payload'].get('factor') == 'code'), default=-1)
    return next((step for step in (int(ts // 30) + d for d in (-1, 0, 1))
                 if step > used and hmac.compare_digest(totp(key, step), code)), None)


def dm(text, *, root=None):
    """The control-plane send: security check and outward lint, then send, never a draft.

    The recipient is the owner's own DM, so this is the send step of drafts.approve
    without the host confirmation. Every other DM still drafts through the chat port.
    """
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    code, reason = security.outbound({'text': text}, root)
    if not code:
        # Only a Slack DM id (D...) is the owner alone; a C or G id gets the full lint.
        channel = os.environ.get('SLACK_OWNER_DM_CHANNEL', '')
        code, reason = outward.check_lint({'text': text, 'channel': channel}, root, config,
                                          {'chat'}, to_owner=channel.startswith('D'))
    if code:
        return Result(code, None, reason)
    send = registry.load('chat', config).dm
    result = getattr(send, '__wrapped__', send)(text, root=root)
    data = result.data if isinstance(result.data, dict) else {}
    if not result.exit and data.get('channel') and data.get('ts'):
        # A reply sent with a user token polls back as an owner message; handle skips it.
        _sent_path(root).parent.mkdir(parents=True, exist_ok=True)
        workspace.atomic_write(_sent_path(root), json.dumps(
            [*sent(root), f'{data["channel"]}/{data["ts"]}'][-SENT_KEPT:]) + '\n', mode=0o600)
    return result


SENT_KEPT = 200


def _sent_path(root):
    return root / '.wuwei' / 'inbox' / 'sent.json'


def sent(root):
    """Inbox ids of the last messages this listener sent to the owner DM."""
    try:
        return json.loads(_sent_path(root).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return []


TRANSPORT = SimpleNamespace(dm=dm)


def owner_session(data, identifier):
    """The live remote session whose turns raised this decision, or None."""
    return next((session for session, row in data.get('sessions', {}).items()
                 if row.get('role') == 'remote' and 'stopped' not in row
                 and identifier in row.get('decisions', [])), None)


def _say(transport, root, text, code):
    return max(code, transport.dm(text, root=root).exit)


def handle(root, event, *, transport=TRANSPORT, runtime=None):
    """Answer one inbox line from the owner DM; 0 done, 1 refused or not run, 2 unrun."""
    if event.get('channel') != os.environ.get('SLACK_OWNER_DM_CHANNEL'):
        print(f'listen remote.unmatched: {event.get("id")} is not in the owner DM channel', flush=True)
        return 0
    try:
        if event['id'] in sent(root):
            return 0
        text, code = split(event['text'])
        command = parse(text)
        config = workspace.load_config(root)
        who = sender(config, event)
        if who == 'other':
            if not any(row['kind'] == 'remote.ignored' and row['payload'].get('sender') == event['sender']
                       for row in _today(root)):
                state.append_event('remote.ignored', {'sender': event['sender']}, root=root)
            return 0
        if who == 'changed' and command != ('stop', 'all'):
            # The pin it was checked against: editing the pin (the re-confirmation) clears the page.
            state.append_event('remote.refused', {'id': event['id'], 'pin': config['control_plane']['owner']},
                               root=root)
            return _say(transport, root, CHANGED, 1)
        if command == ('confirm', ''):
            line = confirmation(root)
            if line is None:
                return _say(transport, root, NOTHING, 1)
            state.append_event('remote.confirmed', {'id': line['id'], 'factor': 'reply'}, root=root)
            event, command = line, parse(split(line['text'])[0])
        elif command and command[0] in FACTOR:
            step = code_step(root, event, code)
            if step is None:
                state.append_event('remote.pending', {'id': event['id'], 'command': command[0]}, root=root)
                return _say(transport, root, CONFIRM, 1)
            state.append_event('remote.confirmed', {'id': event['id'], 'factor': 'code', 'step': step},
                               root=root)
        if command is None:
            decisions = control_plane.pending(root)
            answer = control_plane.parse(text, decisions)
            if answer is None:
                return _say(transport, root, VOCABULARY, 1)
            identifier, option = answer
            two_way = decisions[identifier]['Reversibility'] == 'two-way'
            # A one-way answer stays evidence: the first stands until the outcome on the host.
            first = None if two_way else replied(root, identifier)
            if first is not None:
                if first != option:
                    return _say(transport, root, ANSWERED.format(identifier=identifier, option=first), 1)
                return _say(transport, root, NOTED.format(identifier=identifier, option=option), 0)
            state.append_event('decision.replied', {'id': identifier, 'option': option}, root=root)
            said = 0
            if two_way:
                # The pinned DM sender is the confirmation for a two-way door; one-way keeps the host (#364).
                from wuwei.commands import decision as decision_command
                code, reason = decision_command.owner_outcome(
                    SimpleNamespace(id=identifier, option=option), root=root, where='in the owner DM')
                if code:
                    raise RuntimeError(reason)
                said = transport.dm(RECORDED.format(identifier=identifier, option=option), root=root).exit
            session = owner_session(state.read_state(root), identifier)
            if session is None:
                return said if two_way else _say(transport, root, NOTED.format(
                    identifier=identifier, option=option), 0)
            command = ('reply', session)
        verb, argument = command
        if verb == 'more':
            return more(root, argument, transport=transport)
        if verb in ('run', 'cloud'):
            return _say(transport, root, UNAVAILABLE, 1)
        if verb == 'status':
            from wuwei.commands import status
            text = status.line(status.snapshot(workspace.day_dir(root))).removeprefix('WUWEI ')
            if control_plane._level(root) == 'full':
                from wuwei import drafts
                count = sum(len(row.get('style') or []) for row in drafts.read(state.read_state(root)).values()
                            if row['status'] == 'pending')
                if count:
                    text += f' | ai tells {count}'
            return control_plane.notify(text, root=root, transport=transport).exit
        if verb == 'report':
            path = report.write(root)
            counts, heading = {}, None
            for line in path.read_text(encoding='utf-8').splitlines():
                if line.startswith('## '):
                    heading = line[3:]
                elif line.startswith('- '):
                    counts[heading] = counts.get(heading, 0) + 1
            text = (f'Report {path.parent.name}: merged {counts.get("Merged", 0)}, '
                    f'open {counts.get("Open at close", 0)}, parked {counts.get("Parked", 0)}, '
                    f'decisions answered {counts.get("Decisions answered", 0)}.')
            return control_plane.notify(text, root=root, transport=transport).exit
        if verb == 'plan':
            return start(root, 'plan', event['id'], PLAN_PROMPT, transport=transport, runtime=runtime)
        if verb == 'ask':
            return start(root, 'ask', event['id'], ASK_PROMPT + argument,
                         transport=transport, runtime=runtime)
        if verb == 'stop':
            return stop(root, argument, transport=transport)
        return max(said, resume(root, argument, identifier, option, transport=transport, runtime=runtime))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f'listen remote unmeasured: {exc}', flush=True)
        try:
            transport.dm(FAILED, root=root)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, RuntimeError):
            pass
        return 2


def tools(command):
    if command == 'ask':
        return list(ASK_TOOLS)
    path = registry.ADAPTERS.parent / 'agents/allowlist.json'
    return [*json.loads(path.read_text(encoding='utf-8'))['planner'], 'Skill']


def deny(root, session, tool):
    """Turn one refused tool call into a routed owner decision."""
    name = tool if re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}', tool) else 'a tool'
    text = DENIAL.format(session=session[:8], tool=name)
    path = decision.write(text, root)
    fields, _ = decision.evaluate(text)
    decision.route_owner(path.stem, fields, root)


def memory_floor(root):
    """True when free memory is at the host floor; unmeasured memory raises ValueError."""
    from wuwei.guards import agent_launch
    config = workspace.load_config(root)
    return agent_launch.free_memory(config, root) >= config['host']['free_memory_mb'] * 1024**2


def start(root, command, thread, prompt, *, transport=TRANSPORT, runtime=None):
    return _turn(root, command, thread, prompt, None, transport, runtime)


def resume(root, session, identifier, option, *, transport=TRANSPORT, runtime=None):
    row = state.read_state(root)['sessions'][session]
    return _turn(root, row['command'], row['thread'], f'Decision {identifier}: option {option}.',
                 session, transport, runtime)


# ponytail: a turn blocks the listener tick for up to the adapter TIMEOUT; move turns to a
# background process when they outgrow the poll interval.
def _turn(root, command, thread, prompt, session, transport, runtime):
    if not memory_floor(root):
        return _say(transport, root, LOW_MEMORY, 1)
    # Fixed selection: headless sessions exist only in the Claude Code runtime adapter.
    runtime = runtime or registry.load('runtime', {'adapters': {'runtime': 'claude'}})
    before = set(control_plane.pending(root))
    result = runtime.headless(prompt, session, tools(command), root=root)
    if result.exit == 2 or not isinstance(result.data, dict):
        print(f'listen remote unmeasured: {result.reason}', flush=True)
        return _say(transport, root, FAILED, 2)
    sid = result.data['session_id']
    for tool in result.data['denials']:
        deny(root, sid, tool)
    # ponytail: a decision another session routes during the turn is attributed to this one;
    # record the session in the decision when that happens.
    new = [identifier for identifier in control_plane.pending(root) if identifier not in before]

    def update(data):
        sessions.record(data, sid, hook=f'remote {command}', cwd=str(root), role='remote', thread=thread)
        row = data['sessions'][sid]
        row['command'] = command
        row['decisions'] = [*row.get('decisions', []), *new]
    state._write_state(update, root, reserved=False,
                       kind='remote.resumed' if session else 'remote.started',
                       payload={'session': sid, **({} if session else {'command': command})})
    code = max(result.exit, escalate_new(root, transport))
    if command == 'ask' and result.data['result'].strip():
        sent = control_plane.notify(result.data['result'], root=root, transport=transport)
        if sent.exit == 1:
            sent = transport.dm(f'The answer is held in session {sid[:8]}; open it on the host.', root=root)
        code = max(code, sent.exit)
    return _say(transport, root, f'Session {sid[:8]}: turn ended, {len(new)} decisions waiting.', code)


def more(root, identifier, *, transport=TRANSPORT):
    """Send the full record of one owner-pending decision; read-only, so no second factor."""
    decisions = control_plane.pending(root)
    if identifier not in decisions:
        return _say(transport, root, NOT_PENDING.format(identifier=identifier), 1)
    text = control_plane.render(identifier, decisions[identifier], control_plane._content(root), 'full', root)
    sent = transport.dm(text, root=root)
    if sent.exit == 1:
        sent = transport.dm(ON_HOST.format(identifier=identifier), root=root)
    return sent.exit


def escalate_new(root, transport):
    """Send each owner-pending decision the DM has not had today; record each send."""
    done = {row['payload'].get('id') for row in _today(root) if row['kind'] == 'decision.escalated'}
    code = 0
    for identifier in control_plane.pending(root):
        if identifier in done:
            continue
        sent = control_plane.escalate(identifier, root=root, transport=transport)
        if sent.exit == 1:
            sent = transport.dm(f'{identifier} is waiting in the workspace.', root=root)
        if sent.exit == 0:
            state.append_event('decision.escalated', {'id': identifier}, root=root)
        code = max(code, sent.exit)
    return code


def stop(root, target, *, transport=TRANSPORT):
    """Mark remote sessions stopped between turns; a stopped session is never resumed."""
    live = [session for session, row in state.read_state(root).get('sessions', {}).items()
            if row.get('role') == 'remote' and 'stopped' not in row]
    chosen = live if target == 'all' else [session for session in live if session.startswith(target)]
    if target != 'all' and len(chosen) != 1:
        return _say(transport, root, f'No single session matches {target}.', 1)
    def mark(data):
        for session in chosen:
            data['sessions'][session]['stopped'] = workspace.now().isoformat()
    if chosen:
        state._write_state(mark, root, reserved=False, kind='remote.stopped',
                           payload={'sessions': chosen})
    return _say(transport, root, f'Stopped {len(chosen)} sessions.', 0)
