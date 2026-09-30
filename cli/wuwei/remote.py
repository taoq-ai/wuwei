"""Commands from the owner DM: the vocabulary, the read-only gate, one session per thread."""

import json
import os
import re
from types import SimpleNamespace

from wuwei import (control_plane, decision, outward, registry, report, security, sessions, state,
                   workspace)
from wuwei.registry import Result


# Every fixed line passes the default outward lint: messages to the owner DM are linted.
VOCABULARY = ('Commands: plan, status, report, ask <question>, stop <session>, stop all. '
              'Decisions: approve D-n, option X on D-n, drop it.')
UNAVAILABLE = 'Not available in this version. ' + VOCABULARY
GUARDED = 'Recorded, not run: this command needs the remote-command guards.'
FAILED = 'That command could not run; see the listener log on the host.'
EXECUTABLE = frozenset({'status', 'report'})  # #66 adds plan, ask, stop and reply behind its guards
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
    return None


def dm(text, *, root=None):
    """The control-plane send: security check and outward lint, then send, never a draft.

    The recipient is the owner's own DM, so this is the send step of drafts.approve
    without the host confirmation. Every other DM still drafts through the chat port.
    """
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    code, reason = security.outbound({'text': text}, root)
    if not code:
        code, reason = outward.check_lint(
            {'text': text, 'channel': os.environ.get('SLACK_OWNER_DM_CHANNEL', 'owner DM')},
            root, config, {'chat'})
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
        return 0
    try:
        if event['id'] in sent(root):
            return 0
        command = parse(event['text'])
        if command is None:
            answer = control_plane.parse(event['text'], control_plane.pending(root))
            if answer is None:
                return _say(transport, root, VOCABULARY, 1)
            identifier, option = answer
            state.append_event('decision.replied', {'id': identifier, 'option': option}, root=root)
            session = owner_session(state.read_state(root), identifier)
            if session is None:
                return _say(transport, root, f'Recorded {identifier} option {option}. '
                            'Confirm it on the host.', 0)
            command = ('reply', session)
        verb, argument = command
        if verb in ('run', 'cloud'):
            return _say(transport, root, UNAVAILABLE, 1)
        if verb not in EXECUTABLE:
            state.append_event('remote.pending', {'id': event['id'], 'command': verb}, root=root)
            return _say(transport, root, GUARDED, 1)
        if verb == 'status':
            from wuwei.commands import status
            text = status.line(status.snapshot(workspace.day_dir(root))).removeprefix('WUWEI ')
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
        return resume(root, argument, identifier, option, transport=transport, runtime=runtime)
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


def start(root, command, thread, prompt, *, transport=TRANSPORT, runtime=None):
    return _turn(root, command, thread, prompt, None, transport, runtime)


def resume(root, session, identifier, option, *, transport=TRANSPORT, runtime=None):
    row = state.read_state(root)['sessions'][session]
    return _turn(root, row['command'], row['thread'], f'Decision {identifier}: option {option}.',
                 session, transport, runtime)


# ponytail: a turn blocks the listener tick for up to the adapter TIMEOUT; move turns to a
# background process when they outgrow the poll interval.
def _turn(root, command, thread, prompt, session, transport, runtime):
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
    code = result.exit
    for identifier in new:
        sent = control_plane.escalate(identifier, root=root, transport=transport)
        if sent.exit == 1:
            sent = transport.dm(f'{identifier} is waiting in the workspace.', root=root)
        code = max(code, sent.exit)
    if command == 'ask' and result.data['result'].strip():
        sent = control_plane.notify(result.data['result'], root=root, transport=transport)
        if sent.exit == 1:
            sent = transport.dm(f'The answer is held in session {sid[:8]}; open it on the host.', root=root)
        code = max(code, sent.exit)
    return _say(transport, root, f'Session {sid[:8]}: turn ended, {len(new)} decisions waiting.', code)


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
