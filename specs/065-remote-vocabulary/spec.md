# Feature Specification: command vocabulary and session-per-thread over headless Claude Code

**Feature Branch**: `065-remote-vocabulary`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #65, feat(control-plane). Design section 15.9. Wave G2 (M5-lite): one
channel, Slack DMs, on top of #48 (inbound interface, redactor), #49 (`wuwei listen`,
inbox, cursor, kill switch, planner wake), #50 (Slack inbound polling), #57
(control-plane interface and reply parser) and #260 (session registry). No routines, no
cloud sessions, no budget governor, no second factor (#66).

## Root cause (read on main, e8800e5)

This is a new capability, not a regression. The notes name no dry-run failure; the probe
is the listener on main with a command in the owner DM. What exists and why it does not
cover the issue:

- Nothing reads the inbox for commands. `listen.tick` (`cli/wuwei/listen.py:32-67`) polls,
  stores and marks the planner wake (`listen.py:60-66`); a stored "status" or "plan today"
  in the owner DM only wakes the planner. There is no parser for the 15.9 vocabulary
  anywhere in `cli/`.
- The control plane has no messaging transport. `control_plane.escalate`, `notify` and
  `poll_replies` (`cli/wuwei/control_plane.py:84-129`) take a duck-typed transport
  (`control_plane.py:17`, "promote to an adapter kind when a second messaging transport
  lands"); no caller passes one. The 057 spec deferred "wire `poll_replies` into `wuwei
  listen` with the Slack transport" to this issue.
- The obvious transport, the chat port's `dm`, can never reach the phone. The port is an
  `outward_operation` that marks every DM `is_dm` (`cli/wuwei/registry.py:149-150`), and
  the tier classifier drafts any call with a true audience flag
  (`cli/wuwei/outward.py:249`); `tests/test_outbound.py:80` pins
  `('Thanks', {'channel': 'Cwork', 'is_dm': True}) -> (1, 'draft')`. A reply to the owner
  through `chat.dm` becomes a draft that only `wuwei drafts approve` in a host terminal can
  send. The watch digest already treats that as expected (`cli/wuwei/watch.py:110-113`).
- No headless session exists. `adapters/runtime/claude.py` returns dispatch instructions
  for the host (`dispatch`, `continue_job`) and never starts a process; `status` and
  `result` exit 2 by design. `scripts/headless_adapter.py:33-39` (a paid e2e runner, not
  runtime code) is the only place that builds a `claude -p` command line; it passes the
  prompt on stdin.
- The session registry is ready for this issue: role `remote` and a `thread` reference
  exist (`cli/wuwei/sessions.py:11`, `record` and `touch` at `sessions.py:25-49`), with no
  producer yet (260 spec, User Story 4).
- The status line is built inline in `commands/status.run`
  (`cli/wuwei/commands/status.py:209-220`) and starts with `WUWEI`, a word the default
  outward lint refuses (`cli/wuwei/workspace.py:120`), so it cannot be reused as a message
  without a small extraction.

## User Scenarios & Testing

### User Story 1 - Commands from the owner DM are parsed; anything else gets the vocabulary (Priority: P1)

The owner types a command in the Slack DM with the workspace app. The listener stores it in
the inbox (#49, #50), reads it once, and answers in the same DM.

**Independent Test**: `python -m pytest -q tests/test_remote.py -k "parse or vocabulary or unavailable or handled"`.

**Acceptance Scenarios**:

1. Given "run rm -rf" from the owner DM, then nothing runs (no runtime call, no state
   write) and the vocabulary is returned.
2. Given any text that is neither a command nor a decision reply, then the vocabulary is
   returned.
3. Given `run <routine>` or `cloud <repo> <task>`, then the answer is "Not available in
   this version." followed by the vocabulary; nothing runs.
4. Given a message in any channel other than the owner DM (a mention in a work channel),
   then it is not treated as a command and nothing is sent.
5. Given the same inbox line on a second tick, or after a listener restart, then it is
   not handled again.
6. Given `responder.enabled = false`, then no command is handled (events are still
   stored, as today).

### User Story 2 - Until #66, only read-only commands run from a message (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_remote.py -k "gate or status or report"`.

**Acceptance Scenarios**:

1. Given "status", then the owner DM receives the status line (without the `WUWEI`
   prefix) through the control plane's content policy.
2. Given "report", then today's report is written and the owner DM receives a one-line
   summary (counts of merged, open, parked and answered decisions).
3. Given "plan today", "ask <question>", "stop <session>", "stop all", or a decision
   reply that belongs to a remote session, then nothing runs, a `remote.pending` event
   records the inbox id and the command word, and the answer says it needs the
   remote-command guards.

### User Story 3 - One thread, one headless session (Priority: P1)

The machinery #66 unlocks. Tested directly and through the message path with the gate
widened inside the test.

**Independent Test**: `python -m pytest -q tests/test_remote.py -k "session or resume or denial or stop"`.

**Acceptance Scenarios**:

1. Given "plan today" from the owner (gate open), then a session starts with
   `claude -p --output-format json`, the returned `session_id` is registered with role
   `remote` and the command message as its thread, each decision the run routed arrives
   as a message, and a reply "option B on D-n" resumes the same session id with
   `--resume`.
2. Given a tool call outside the role allowlist, then Claude Code refuses it
   (`--permission-mode dontAsk`), the run reports it in `permission_denials`, and it
   surfaces as a routed owner decision delivered like any other.
3. Given "stop <session>" (a unique prefix of at least 8 characters) or "stop all", then
   the matching remote sessions are marked stopped and a later reply to one of their
   decisions is recorded but resumes nothing.
4. Given the headless run cannot start (missing `claude`, timeout, non-JSON output, no
   `session_id`), then nothing is registered, the owner DM gets a fixed failure line, and
   the handler exits 2 with the reason in the listener log.

### Edge Cases

- A decision reply with no remote session behind it (a decision from the interactive
  planner) is recorded as `decision.replied` evidence exactly like #57 and acknowledged;
  it never becomes an owner outcome.
- A message the outward lint refuses (for example a decision question naming the owner)
  is not sent; the owner gets the fixed line "D-n is waiting in the workspace." instead.
- `SLACK_OWNER_DM_CHANNEL` unset: no event matches the owner DM and nothing is handled
  (the Slack inbound poll already exits 2 without it).
- First tick after upgrading: inbox lines already covered by the previous planner wake
  are not replayed as commands.
- A crash between marking a line handled and acting on it drops that command (at most
  once); a command never runs twice.
- Commands that arrive while `responder.enabled = false` are handled, in order, once the
  switch is back on (the handled count does not move while it is off). Staleness is the
  second factor's concern (#66: confirmation within 2 minutes).
- A resumed run that returns a different `session_id` is exit 2; nothing is recorded
  against either id.
- Day rollover: remote rows live in the day's session registry; after midnight a reply to
  yesterday's decision finds no session and is only recorded.
- Any unexpected error while handling one line (corrupt state, unreadable decision) is
  exit 2 with the reason printed; the owner gets one fixed failure line when it can be
  sent.

## Requirements

### Functional Requirements

- **FR-001**: The listener MUST hand each new inbox line, once and in order, to one
  handler while `responder.enabled` is true; the handled count persists in
  `.wuwei/inbox/cursor.json` and is saved before the line is acted on.
- **FR-002**: Only events whose `channel` equals `SLACK_OWNER_DM_CHANNEL` are handled.
- **FR-003**: The parser MUST accept exactly: `plan` (any trailing words ignored),
  `status`, `report`, `run <routine>`, `ask <question>`, `cloud <repo> <task>`,
  `stop <session>`, `stop all`; case-insensitive, whitespace-collapsed, one trailing `.`
  or `!` ignored. Anything else is not a command.
- **FR-004**: A non-command that `control_plane.parse` maps to a pending decision is a
  decision reply; anything else gets the vocabulary. No owner text ever reaches a shell,
  and only an `ask` question reaches a session prompt.
- **FR-005**: Until #66, only `status` and `report` execute from a message. Every other
  command, and every reply that would resume a session, is recorded as `remote.pending`
  and answered with the guards line.
- **FR-006**: A session starts with `claude -p --output-format json --permission-mode
  dontAsk --allowedTools <role tools>` and the prompt on stdin, in the workspace root,
  with workspace credentials removed from the environment; a reply resumes it with the
  same flags plus `--resume <session_id>`. `plan` uses the planner's tools from
  `agents/allowlist.json` plus `Skill`; `ask` uses `Read`, `Glob`, `Grep`.
- **FR-007**: The started session MUST be registered in the session registry with role
  `remote`, the command message's inbox id as `thread`, the command word, and the ids of
  decisions its turns raised.
- **FR-008**: After each turn, every decision that became pending during the turn and one
  routed owner decision per refused tool call MUST be sent to the owner DM through
  `control_plane.escalate`; the turn always ends with one summary line, so a turn is never
  silent.
- **FR-009**: Messages to the owner DM go through one control-plane send: the security
  canary and honeytoken check, the outward lint for the DM channel, then the chat
  adapter's undecorated `dm`. It does not draft: the recipient is the owner's own control
  plane.
- **FR-010**: `remote.pending`, `remote.started`, `remote.resumed` and `remote.stopped`
  are reserved to the listener (the event command names it) and classified silent.
- **FR-011**: No existing behaviour changes: the chat port still drafts every other DM;
  the watch digest, `poll_replies`, the reply parser, `wuwei status` output and every
  existing test stay as they are.

### Key Entities

- **Cursor file** `.wuwei/inbox/cursor.json`: gains optional `handled` (int >= 0), the
  number of inbox lines handed to the handler. Missing means "start at `woken`".
- **Remote session row** (day state `sessions.<session_id>`, written by the listener):
  the #260 row with `role: "remote"` and `thread: "<inbox id>"`, plus `command`
  (`plan` or `ask`), `decisions` (list of `D-n`) and, once stopped, `stopped` (ISO time).
- **Denial decision**: a fixed, valid decision record (options "resume without it" and
  "do nothing"), `Decided-by: owner`, routed to the owner, naming the refused tool.
- **Events**: `remote.pending {id, command}`, `remote.started {session, command}`,
  `remote.resumed {session}`, `remote.stopped {sessions}`; plus the existing
  `decision.replied {id, option}` and `decision.routed`.

## Success Criteria

- **SC-001**: Each of the issue's three acceptance scenarios has one test that fails on
  main and passes after the change.
- **SC-002**: The core never spawns a process (the existing boundary scan passes); the
  only new subprocess call is one function in `adapters/runtime/claude.py`.
- **SC-003**: No message text, question text or command argument is written to events or
  state; events carry ids and command words only.
- **SC-004**: The full suite passes with no existing assertion changed; the emitted-kinds
  table in `tests/test_signal_status.py` gains the four `remote.*` kinds as silent.

## Assumptions

- **Gate until #66 (notes, binding).** "Plan today starts a session" is satisfied by the
  machinery and tested with the gate widened inside the test; the shipped gate executes
  only `status` and `report`. #66 widens `remote.EXECUTABLE` behind its guards and
  consumes `remote.pending`.
- **Owner DM only, no sender pin.** A command counts when it arrives in
  `SLACK_OWNER_DM_CHANNEL`, the channel only the owner and the workspace app share. The
  sender pin (owner Slack user id plus team id) and the second factor are #66.
- **Control-plane messages are not drafts.** The chat port drafts every DM
  (`outward.py:249`), which would make the control plane mute. Messages to the owner's own
  DM keep the security check and the outward lint but skip the approval tier, mirroring
  the send step of `drafts.approve` without host confirmation. Messages to people are
  unchanged. This is a trust-boundary decision for review.
- **Threads.** Slack inbound reads top-level messages only (#50), so the owner cannot
  reply inside a Slack thread. The thread reference is the inbox id of the command
  message (`<channel>/<ts>`); a reply finds its session through the decision id it
  answers. One command message, one session id.
- **Only decision replies resume a session.** The resume prompt is built by WUWEI
  ("Decision D-n: option X."), never the owner's free text.
- **A refused tool is not granted from the phone.** The denial decision offers "resume
  without it" or "do nothing"; granting a tool stays a host change to the role allowlist.
- **Synchronous turns.** A headless turn runs inside the listener tick with a fixed
  timeout; `stop` therefore acts between turns (there is no process to kill) and prevents
  further resumes. Background turns are later work if turns outgrow the poll interval.
- **Headless planner.** The prompt tells the planner it runs headless: invoke the
  `wuwei:wuwei-plan` skill, write each question as a decision record, route it and end the
  turn. The installed WUWEI plugin supplies the skill. `AskUserQuestion` is denied under
  `dontAsk` (Claude Code docs), so a planner that asks anyway surfaces as a denial
  decision rather than a stall.
- **CLI flags verified 2026-09-30** against the Claude Code CLI reference and headless
  docs: `-p`, `--output-format json` (result has `session_id`, `result`, `is_error`,
  `permission_denials`), `--resume <id>`, `--allowedTools`, `--permission-mode dontAsk`
  (denies anything that would prompt, including `AskUserQuestion`). Only `tool_name` is
  read from a permission denial. Session ids are UUIDs (`--session-id` requires one).
- **Decisions raised by a turn** are those pending after the turn and not before it. A
  decision routed by another session during the turn is attributed to this one.
- **No budget governor, quiet hours or routines** in this wave (15.8 not built).
- **`report` summary** counts list lines under Merged, Open at close, Parked and
  Decisions answered in the report `report.write` already produces; detail stays in the
  workspace.

## Deferred

- #66: sender pin, second factor, widening `EXECUTABLE`, executing `remote.pending`.
- `cloud` (cloud sessions) and `run` (routines): later waves.
- Background turns and killing a running turn on `stop`: when turns outgrow the tick.
