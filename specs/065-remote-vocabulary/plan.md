# Implementation Plan: command vocabulary and session-per-thread over headless Claude Code

**Branch**: `065-remote-vocabulary` | **Date**: 2026-09-30 | **Spec**: spec.md

## Summary

One new core module, `cli/wuwei/remote.py`: the vocabulary parser, the control-plane send
to the owner DM, the per-line handler the listener calls, and the session turn (start,
resume, relay, stop). One new adapter function, `headless` in `adapters/runtime/claude.py`,
the only place that runs `claude -p`. Small edits: the listener hands new inbox lines to
the handler; the status line is extracted into a function; two producer tables and the
silent list name the new event kinds. Everything else is reused: `control_plane.parse`,
`pending`, `escalate`, `notify`; `sessions.record`; `decision.write`, `evaluate`,
`route_owner`; `security.outbound`; `outward.check_lint`; `report.write`;
`env.child_environment`.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. The core imports no subprocess (the boundary
scan in `tests/test_adapters.py::test_core_does_not_access_process_launchers` must still
pass). Tests are in process with a fake transport (`dm` records texts, returns
`Result(0)`) and a fake runtime (`headless` returns scripted results and routes decisions
as a side effect); one adapter test replaces `subprocess.run` in the adapter module the
way `tests/test_runtime.py` does for Codex. No network, no real `claude`.

## Constitution Check

- I stdlib only: yes. II three-state exits: `handle` returns 0, 1 or 2; the adapter
  returns a `Result`; every error path prints its reason. III one behaviour, one function:
  parse, send, handle, turn, stop, deny each live once in `remote.py`. IV test first:
  tasks.md orders every test before its code. V ponytail: no transport class, no adapter
  kind, no new config key, no new state key (remote rows live in the #260 registry). VII
  security: owner text never reaches a shell; only an `ask` question reaches a prompt; a
  resume prompt is built by WUWEI; refused tools are never granted by message; child
  processes get no workspace credentials; events carry ids and command words only.

## Design

### 1. `adapters/runtime/claude.py`: add `headless`

```python
SESSION = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TIMEOUT = 1800

# ponytail: not a runtime port operation; only Claude Code has headless sessions. Add it to
# registry.PARAMETERS when a second runtime does.
def headless(prompt, session, tools, *, root=None):
    """One headless turn: start a session, or resume one by id; the prompt goes on stdin."""
```

- Validate: `prompt` nonempty `str`; `session` is `None` or `SESSION.fullmatch`; `tools` a
  nonempty list of `re.fullmatch(r'[A-Za-z]+', t)` names. Otherwise
  `Result(2, reason='invalid headless call')`.
- argv, closed (flags verified against the Claude Code CLI reference and headless docs,
  2026-09-30; the prompt on stdin follows `scripts/headless_adapter.py`, which avoids the
  variadic `--allowedTools` swallowing a positional prompt):
  `['claude', '-p', '--output-format', 'json', '--permission-mode', 'dontAsk',
  '--allowedTools', ','.join(tools), *(['--resume', session] if session else [])]`.
- `subprocess.run(argv, input=prompt, cwd=str(workspace.find_workspace(root)),
  capture_output=True, text=True, env=env.child_environment(), timeout=TIMEOUT)`.
- Parse `json.loads(process.stdout)`; require a dict with `session_id` matching `SESSION`
  (and equal to `session` when resuming), `result` a `str`, `is_error` a `bool`,
  `permission_denials` a list of dicts each with a `str` `tool_name`. Anything else:
  `Result(2, reason='Claude headless: invalid result')`.
- Return `Result(0 if process.returncode == 0 and not is_error else 1,
  {'session_id', 'result', 'denials': [row['tool_name'] for row in denials]})`.
- `(OSError, ValueError, subprocess.SubprocessError)` becomes
  `Result(2, reason=f'Claude headless could not run: {type(exc).__name__}')` (no stderr
  or stdout text in the reason: it may carry prompt content).

### 2. `cli/wuwei/commands/status.py`: extract `line`

Move the body that builds `parts` (lines 209-220) into `def line(data): return ' | '.join(parts)`
and have `run` print `line(data)`. Output is byte-identical; existing tests cover it.

### 3. `cli/wuwei/remote.py` (new)

Imports: `json`, `os`, `re`, `types.SimpleNamespace`; from `wuwei`: `control_plane`,
`decision`, `outward`, `registry`, `report`, `security`, `sessions`, `state`,
`workspace`; `Result` from `wuwei.registry`; `status` from `wuwei.commands` imported
inside the status branch (precedent: `dispatch.py:108`).

Constants (every line passes the default outward lint: no `wuwei`, `queue`, `agent`,
`seat`, `claude`, `the owner`):

```python
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
```

`DENIAL` routes to the owner (`decision.route`: blast radius is not own branch or PR) and
passes `decision.evaluate` (A 25, B 5, both pass the must). One test pins both.

Functions:

- `parse(text) -> (verb, argument) | None`, pure. `words = re.sub(r'[.!]$', '',
  ' '.join(text.split()))`, `lower = words.casefold()`:
  `plan(?: .*)?` -> `('plan', '')`; `status`, `report` -> `(lower, '')`;
  `stop all` -> `('stop', 'all')`; `run ([a-z0-9][a-z0-9_-]*)` -> `('run', name)`;
  `ask (.+)` on `words` (case kept, `re.I` on the verb) -> `('ask', question)`;
  `cloud \S+ .+` -> `('cloud', '')`; `stop ([0-9a-f][0-9a-f-]{7,35})` ->
  `('stop', prefix)`; else `None`. "run rm -rf" is `None` (two words after `run`).
- `dm(text, *, root=None) -> Result`, the control-plane send:
  `root = workspace.find_workspace(root)`; `config = workspace.load_config(root)`;
  `code, reason = security.outbound({'text': text}, root)`; if clean,
  `code, reason = outward.check_lint({'text': text, 'channel':
  os.environ.get('SLACK_OWNER_DM_CHANNEL', 'owner DM')}, root, config, {'chat'})` (the
  same two checks and channel as `drafts.approve`, `drafts.py:133-138`); a finding
  returns `Result(code, None, reason)` and sends nothing. Then
  `send = registry.load('chat', config).dm` and return
  `getattr(send, '__wrapped__', send)(text, root=root)` (the undecorated operation, as
  `drafts.approve` does at `drafts.py:130`; the `none` adapter has no wrapper and
  returns exit 2).
- `TRANSPORT = SimpleNamespace(dm=dm)`: what `control_plane.escalate` and `notify` take.
- `handle(root, event, *, transport=TRANSPORT, runtime=None) -> int`: returns 0
  at once when `event['channel'] != os.environ.get('SLACK_OWNER_DM_CHANNEL')`. Otherwise
  runs the steps below inside `try`; `(OSError, UnicodeError, ValueError, KeyError,
  TypeError, RuntimeError)` prints `listen remote unmeasured: {exc}`, sends `FAILED`
  (itself guarded: a failing send is ignored), returns 2.
  1. `command = parse(event['text'])`.
  2. `None`: `answer = control_plane.parse(event['text'], control_plane.pending(root))`.
     No answer: send `VOCABULARY`, return 1. Answer `(identifier, option)`:
     `state.append_event('decision.replied', {'id': identifier, 'option': option},
     root=root)` (the #57 evidence event), then `session = owner_session(
     state.read_state(root), identifier)`; no session: send
     `f'Recorded {identifier} option {option}. Confirm it on the host.'`, return 0; else
     `command = ('reply', session)` and continue with `identifier, option` kept.
  3. `run` or `cloud`: send `UNAVAILABLE`, return 1.
  4. Verb not in `EXECUTABLE`: `state.append_event('remote.pending', {'id': event['id'],
     'command': verb}, root=root)`, send `GUARDED`, return 1.
  5. Execute: `status`: `text = status.line(status.snapshot(workspace.day_dir(root)))
     .removeprefix('WUWEI ')`, return `control_plane.notify(text, root=root,
     transport=transport).exit`. `report`: `path = report.write(root)`, count `- ` lines
     under each `## ` heading of `path.read_text()`, send through `notify`
     `f'Report {path.parent.name}: merged {m}, open {o}, parked {p}, decisions answered
     {d}.'`. `plan`: `start(root, 'plan', event['id'], PLAN_PROMPT, ...)`. `ask`:
     `start(root, 'ask', event['id'], ASK_PROMPT + question, ...)`. `stop`:
     `stop(root, argument, transport=transport)`. `reply`: `resume(root, session,
     identifier, option, ...)`.
  A send helper `_say(transport, root, text, code)` returns `max(code,
  transport.dm(text, root=root).exit)`.
- `owner_session(data, identifier) -> str | None`: the id of the row in
  `data.get('sessions', {})` with `role == 'remote'`, no `stopped`, and `identifier` in
  `row.get('decisions', [])`.
- `tools(command) -> list`: `ask` -> `list(ASK_TOOLS)`; `plan` ->
  `[*json.loads((registry.ADAPTERS.parent / 'agents/allowlist.json').read_text(
  encoding='utf-8'))['planner'], 'Skill']` (the file `commands/agents.render` reads;
  `Skill` because the prompt invokes the skill, as in `scripts/headless_adapter.py:37-38`).
- `start(root, command, thread, prompt, *, transport=TRANSPORT, runtime=None)` and
  `resume(root, session_id, identifier, option, *, transport=TRANSPORT, runtime=None)`:
  both call `_turn`; `resume` reads the row (`command`, `thread`) from
  `state.read_state(root)['sessions'][session_id]` and passes the prompt
  `f'Decision {identifier}: option {option}.'`.
- `_turn(root, command, thread, prompt, session, transport, runtime) -> int`:
  1. `runtime = runtime or registry.load('runtime', {'adapters': {'runtime': 'claude'}})`
     (fixed selection, precedent `drafts._edit` loading `editor.local`).
  2. `before = set(control_plane.pending(root))`.
  3. `result = runtime.headless(prompt, session, tools(command), root=root)`. Exit 2 or
     data not a dict: print `listen remote unmeasured: {result.reason}`, send `FAILED`,
     return 2. Nothing is registered.
  4. `sid = result.data['session_id']`; for each tool in `result.data['denials']`:
     `deny(root, sid, tool)`.
  5. `new = [i for i in control_plane.pending(root) if i not in before]`.
  6. One `state._write_state(update, root, reserved=False, kind='remote.resumed' if
     session else 'remote.started', payload={'session': sid, **({} if session else
     {'command': command})})` where `update` calls `sessions.record(data, sid,
     hook=f'remote {command}', cwd=str(root), role='remote', thread=thread)` then sets
     `row['command'] = command` and `row['decisions'] = [*row.get('decisions', []),
     *new]`.
  7. `code = result.exit` (0 or 1). For each id in `new`: `sent =
     control_plane.escalate(id, root=root, transport=transport)`; `sent.exit == 1`
     (lint finding or not pending) sends the fixed `f'{id} is waiting in the
     workspace.'`; `code = max(code, sent.exit)`.
  8. `ask` with a nonempty `result`: `control_plane.notify(result, ...)`; exit 1 sends
     `f'The answer is held in session {sid[:8]}; open it on the host.'`.
  9. Always send `f'Session {sid[:8]}: turn ended, {len(new)} decisions waiting.'`;
     return `code`.
- `deny(root, session, tool)`: `name = tool if re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}',
  tool) else 'a tool'`; `text = DENIAL.format(session=session[:8], tool=name)`;
  `path = decision.write(text, root)`; `fields, _ = decision.evaluate(text)`;
  `decision.route_owner(path.stem, fields, root)`.
- `stop(root, target, *, transport=TRANSPORT) -> int`: live remote rows (role `remote`,
  no `stopped`); `all` takes every one, otherwise exactly one id must start with
  `target`, else send `f'No single session matches {target}.'` and return 1. Chosen rows
  get `stopped = workspace.now().isoformat()` in one `state._write_state(...,
  reserved=False, kind='remote.stopped', payload={'sessions': chosen})` (skip the write
  when none); send `f'Stopped {len(chosen)} sessions.'`, return 0.

### 4. `cli/wuwei/listen.py`

- `cursor`: accept an optional `handled` (`type(...) is int and >= 0`), same validation
  style as `woken`.
- `tick`, inside `if config['responder']['enabled']:`, before the wake: read the inbox
  once (`rows = inbox.read(root)`, replacing the existing `len(inbox.read(root))` call),
  `data.setdefault('handled', data['woken'])`, then for each index from `handled` to
  `len(rows)`: set `handled = index + 1`, `_save(root, data)` (at most once: saved before
  acting), `code = max(code, remote.handle(root, rows[index]))`. The wake uses
  `count = len(rows)` as before.

### 5. Producer tables, silent list, test isolation

- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `remote.pending`, `remote.started`,
  `remote.resumed`, `remote.stopped`: `'wuwei listen'`; `decision.replied` becomes
  `'wuwei control plane poll_replies or wuwei listen'`.
- `cli/wuwei/state.py` `STATE_PRODUCERS['sessions']`: append `or wuwei listen (remote
  sessions)`.
- `cli/wuwei/signal.py` `SILENT`: add the four `remote.*` kinds (the owner already gets a
  message for each; a nudge would duplicate it).
- `tests/conftest.py` autouse fixture: `monkeypatch.delenv('SLACK_OWNER_DM_CHANNEL',
  raising=False)` so a developer's environment never turns test events into commands.

### 6. Docs

`docs/site/configuration.md`, section "Running the listener": a short "Commands from the
owner DM" paragraph: the vocabulary; `run` and `cloud` are not available in this version;
until the remote-command guards land only `status` and `report` run and the rest are
recorded as pending; replies use the decision forms; messages to the owner DM are sent,
not drafted, after the security check and outward lint; `responder.enabled = false`
stops command handling too. Update the `responder.enabled` row (line 89) to say it also
stops command handling. Keep every phrase `tests/test_docs.py` asserts.

### Shared helpers reused (do not copy)

`control_plane.parse`, `pending`, `escalate`, `notify`; `sessions.record`;
`decision.write`, `evaluate`, `route_owner`; `security.outbound`; `outward.check_lint`;
`report.write`; `commands.status.snapshot` and the new `line`; `state.append_event`,
`state._write_state`, `state.read_state`; `inbox.read`; `listen._save`;
`env.child_environment`; `registry.load`, `registry.ADAPTERS`, `Result`.

### Must not change

- `outward.classify` and the chat port's `outward_operation`: every other DM still
  drafts; `tests/test_outbound.py` unchanged.
- `control_plane.py` (parser, renderer, `poll_replies`, `HELP`): reused as is.
- `registry.PARAMETERS`, `tests/test_adapters.py::CALLS`: no new port operation.
- `sessions.record`, `touch`, `rows`, and `wuwei sessions` output.
- `wuwei status` text and JSON output; `report.build` text.
- `decision_outcomes`: a message never records an owner outcome.
- The watch, its digest, and the listener's poll, store, cursor and wake behaviour.

## Data

- Cursor `.wuwei/inbox/cursor.json`: `{"cursors": {...}, "woken": N, "handled": M}`.
- Remote row in day state `sessions`: `{"role": "remote", "thread": "<channel>/<ts>",
  "command": "plan" | "ask", "decisions": ["D-3"], "started", "last_seen", "last_hook",
  "cwd", "stopped"?}`.
- Events: `remote.pending {id, command}`, `remote.started {session, command}`,
  `remote.resumed {session}`, `remote.stopped {sessions}`, `decision.replied {id,
  option}`, and `decision.routed` for denial decisions.

## Complexity Tracking

None. Marked shortcuts: `headless` outside the port (ponytail comment above); synchronous
turns inside the tick (`# ponytail: a turn blocks the listener tick for up to TIMEOUT;
move turns to a background process when they outgrow the poll interval.` on `_turn`);
decisions raised by a turn are the pending-set difference (`# ponytail: a decision another
session routes during the turn is attributed to this one; record the session in the
decision when that happens.`).
