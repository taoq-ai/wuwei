# Feature Specification: remote-command guards (pinned identity, second factor, stop all)

**Feature Branch**: `066-remote-guards`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #66, feat(guards). Design section 15.9 (Guards bullet). Wave G2
(M5-lite): one channel, Slack DMs, on top of #65 (command vocabulary and
session-per-thread, `cli/wuwei/remote.py`), #57 (control plane), #49/#50 (listener and
Slack inbound) and #260 (session registry). No Signal, no routines, no cloud sessions,
no budget governor in this wave.

## Root cause (read on main, f614b5b)

This is the guard layer #65 left out on purpose. The notes name no dry-run workspace; the
probe is `remote.handle` on main with a message in the owner DM.

- The sender is never read. `remote.handle` (`cli/wuwei/remote.py:130-185`) accepts any
  event whose `channel` equals `SLACK_OWNER_DM_CHANNEL` (`remote.py:132`); `event['sender']`
  is not consulted anywhere in `cli/`. `SLACK_OWNER_DM_CHANNEL` lives in `.wuwei/env`; if it
  names a channel other people can write to, their messages are commands.
- The Slack event carries no team. `adapters/inbound/slack.py:34-42` builds
  `sender` from `row['user']` only and drops the `team` field Slack returns on user
  messages, so the pinned identity the notes require (owner user id plus workspace team id)
  cannot be checked.
- Nothing can run `plan`, `ask`, `stop` or a resuming reply from a message. The shipped
  gate is `EXECUTABLE = frozenset({'status', 'report'})` (`remote.py:19`); every other verb
  is recorded as `remote.pending` and answered with `GUARDED` (`remote.py:152-154`).
  Nothing consumes `remote.pending`, and no second factor exists.
- A started session is not held to the memory floor. `remote._turn` (`remote.py:216-250`)
  calls `runtime.headless` directly; the floor check lives only in the agent-launch guard
  (`cli/wuwei/guards/agent_launch.py:108-111`), which fires for `Agent` seats, not for the
  top-level `claude -p` the listener starts.
- MCP tools are unscoped in headless sessions. `adapters/runtime/claude.py:79-82` limits
  built-in tools with `--tools` and says "MCP tools are not built-ins: #66 scopes them";
  an MCP server from user or project settings still loads into an `ask` session that is
  meant to be read-only.

## User Scenarios & Testing

### User Story 1 - Only the pinned owner identity commands (Priority: P1)

The owner pins their Slack identity on the host once (`control_plane.owner =
"<team id>/<user id>"`). Messages in the owner DM from anyone else are ignored; a message
from the owner's user id under another team is treated as a changed identity.

**Independent Test**: `python -m pytest -q tests/test_remote.py -k "sender or identity or pin"`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given a command after the sender's identity changed (the owner's
   user id with a different or missing team id), then it is refused: nothing runs, a
   `remote.refused {id}` event is recorded (a page on the host) and the owner DM receives a
   fixed alert line.
2. Given a message in the owner DM from a user id that is not the pinned one, then nothing
   runs and nothing is sent; a `remote.ignored {sender}` event is recorded the first time
   that sender is seen that day, and never again that day.
3. Given `control_plane.owner` unset or malformed, then no owner-DM message is handled: the
   handler exits 2, the listener log names the missing pin and the sender id it saw, and
   the owner DM gets the fixed failure line.
4. Given the Slack inbound poll, then each event's `sender` is `<team>/<user>` built from
   the history row's `team` and `user` (team empty when Slack omits it).

### User Story 2 - A second factor for `plan` and `ask` (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_remote.py -k "factor or totp or confirm"`.

**Acceptance Scenarios**:

1. (Issue acceptance 2) Given `plan` or `ask <question>` without a valid second factor,
   then nothing starts (no runtime call, no session row), a `remote.pending {id, command}`
   event is recorded and the owner DM receives the confirmation prompt.
2. Given `plan today 123456` where `123456` is the current TOTP code for
   `WUWEI_TOTP_SECRET` at the message time, handled within 2 minutes of the message, then
   the session starts and `remote.confirmed {id, factor: "code", step}` is recorded first.
3. Given the same code again (a replay), a code for a time step already used, or a code
   in a message older than 2 minutes when handled, then it counts as no factor (scenario 1).
4. Given a pending `plan` or `ask` and then the reply `confirm` within 2 minutes of the
   prompt, then `remote.confirmed {id, factor: "reply"}` is recorded and the pending
   command runs exactly as sent (the `ask` question is read back from the inbox line).
5. Given `confirm` with nothing pending, after 2 minutes, or a second time for the same
   command, then nothing runs and the owner DM receives "Nothing to confirm".
6. `status`, `report`, `stop <session>`, `stop all` and decision replies never need a
   second factor.

### User Story 3 - `stop all` always works (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_listen.py tests/test_remote.py -k "stop"`.

**Acceptance Scenarios**:

1. (Issue acceptance 3) Given live remote sessions and `stop all` in the owner DM, then one
   listener tick marks every live remote session stopped, with no second factor.
2. Given `stop all` from the owner's user id under a changed identity, then it is still
   accepted; every other command from that identity is refused (US1 scenario 1).
3. Given `stop <session>` from the pinned owner, then it runs without a second factor.

### User Story 4 - Host limits apply to every started session (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_remote.py tests/test_runtime.py -k "memory or mcp"`.

**Acceptance Scenarios**:

1. Given free host memory below `host.free_memory_mb`, then no headless turn starts or
   resumes; the owner DM receives a fixed line and the handler returns 1. Memory that
   cannot be measured is exit 2 (fail closed).
2. Given any headless turn, then the argv carries `--strict-mcp-config` with no
   `--mcp-config`, so no MCP server loads into a remote session.

### User Story 5 - Mutation test per guard (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_guard_mutation.py`.

1. For each guard function (`remote.sender`, `remote.code_step`, `remote.confirmation`,
   `remote.memory_floor`), replacing it with a permissive stub turns its probe red.

### Edge Cases

- A message the listener itself sent (in `.wuwei/inbox/sent.json`) is skipped before the
  sender check, as today.
- A trailing six-digit token is always read as a code: `ask about PR 123456` asks "about
  PR" with code `123456`. End the question with `?` to keep the number.
- An invalid code is not a separate error: the command becomes pending and can be
  confirmed. A malformed `WUWEI_TOTP_SECRET` (not base32) is exit 2 with a reason that
  never contains the secret.
- `WUWEI_TOTP_SECRET` unset: codes never match; `confirm` still works.
- Two factor commands within 2 minutes: `confirm` applies to the latest pending one only.
- Day rollover: pending and confirmed events are per day; a `confirm` after midnight
  finds nothing; a code accepted at 23:59 could be replayed in the first minute of the next
  day (documented ceiling).
- Old `remote.pending` events recorded by #65 for `stop` or `reply` are never confirmed
  (only `plan` and `ask` are).
- A turn blocks the listener tick (#65 ceiling), so `stop all` sent during a turn is
  handled in the tick after the turn ends; it acts before any later line and before any
  further resume.

## Requirements

### Functional Requirements

- **FR-001**: `control_plane.owner` (string, default empty) in `config.toml` is the pinned
  identity `<team id>/<user id>`. Changing it is an owner edit on the host
  (`protect_state` already refuses agent writes to `config.toml`); that is the
  re-confirmation.
- **FR-002**: Slack inbound events carry `sender = "<team>/<user>"`.
- **FR-003**: `remote.sender(config, event)` returns `owner` (sender equals the pin),
  `changed` (same user id, other team) or `other`; an unset or malformed pin raises
  `ValueError` (exit 2 in `handle`).
- **FR-004**: `other`: record `remote.ignored {sender}` once per sender per day, send
  nothing, return 0. `changed`: unless the command is `stop all`, record
  `remote.refused {id}`, send the fixed alert, return 1.
- **FR-005**: `plan` and `ask` need a second factor: a TOTP code (RFC 6238, HMAC-SHA1,
  30 s step, 6 digits, one step of drift either side of the message time) ending the
  message, not reused, in a message handled within 2 minutes; or a `confirm` reply handled
  within 2 minutes of the `remote.pending` event. Without one: `remote.pending`, prompt,
  return 1.
- **FR-006**: The TOTP secret is `WUWEI_TOTP_SECRET`, base32, read from the environment
  that `.wuwei/env` populates, listed in `env.CREDENTIALS` so child processes never get it,
  and never printed, logged or written.
- **FR-007**: `stop <session>`, `stop all`, `status`, `report` and decision replies run
  without a second factor; `EXECUTABLE` and `GUARDED` are removed.
- **FR-008**: Every headless turn (start and resume) first checks the memory floor with
  the agent-launch guard's `free_memory`.
- **FR-009**: The headless argv adds `--strict-mcp-config`.
- **FR-010**: New event kinds `remote.confirmed`, `remote.ignored`, `remote.refused` are
  reserved to `wuwei listen`; `remote.refused` is a page, the other two silent.
- **FR-011**: Every fixed line sent to the owner DM passes the default outward lint.
- **FR-012**: No existing behaviour outside `remote.handle`, `_turn`, the Slack inbound
  sender and the headless argv changes.

### Key Entities

- **Pin**: `control_plane.owner`, `"T0123ABC/U0456DEF"`.
- **Events**: `remote.pending {id, command}` (now only `plan`/`ask`),
  `remote.confirmed {id, factor: "code" | "reply", step?}`, `remote.ignored {sender}`,
  `remote.refused {id}`. No message text in any payload.

## Success Criteria

- **SC-001**: Each of the issue's three acceptance scenarios has one test that fails on
  main and passes after the change.
- **SC-002**: Each guard function has a mutation test registered in
  `tests/test_guard_mutation.py::SPECIAL_TESTS`.
- **SC-003**: The TOTP function matches the RFC 6238 SHA1 test vectors (6-digit
  truncation).
- **SC-004**: The full suite passes; changed existing tests are fixture updates (pinned
  sender, factor satisfied, memory measured) or the #65 gate tests this issue replaces.

## Assumptions

- **Pin for Slack (notes, binding).** The Signal safety number maps to the Slack
  `<team id>/<user id>` pair. The pin is a config value rather than trust-on-first-use:
  `config.toml` is the owner's host file, so editing it is the host re-confirmation, and no
  new pin file or confirm command is needed. A "changed identity" is the owner's user id
  arriving with another or no team id.
- **`team` on history rows.** Real `conversations.history` user messages include `team`,
  though Slack's minimal examples omit it. When it is missing the sender is `/<user>`,
  which is a changed identity: commands are refused and the owner is alerted, so the
  failure is visible, never silent.
- **Alert through push.** For the Slack control plane the push is the DM itself (Slack
  notifies the phone), plus a `remote.refused` page on the host in case the DM channel is
  the thing that changed.
- **Other senders are logged, not answered.** One `remote.ignored` event per sender per
  day; replying would talk to the stranger.
- **Second factor scope (notes).** `plan` and `ask` need it. `run` and `cloud` stay
  unavailable. Nothing in the vocabulary posts to people: replies go to the owner's own DM,
  and a session's outward posts go through the outward guards and drafts as on the host.
  A decision reply resumes a session without a new factor: the session's start carried
  one, the resume prompt is built by WUWEI, and a refused tool is never granted by reply.
- **Confirmation reply.** A bare `confirm` binds to the latest pending command; no nonce,
  because anything that can post in the DM can read a nonce there too. The 2-minute window
  is measured on the host clock from the `remote.pending` event to handling the reply.
- **Staleness (deferred by #65 to this issue).** A code counts only in a message handled
  within 2 minutes of its Slack timestamp; a stale coded command becomes pending and can be
  confirmed.
- **Replay.** A TOTP step is accepted once: steps recorded in today's `remote.confirmed`
  events are refused (RFC 6238 section 5.2).
- **CAP.** Turns are synchronous in the listener, so at most one remote session runs at a
  time; seats a remote planner launches go through the `Agent` launch guard, which
  enforces CAP, `host.seats` and the memory floor, because plugin hooks run in headless
  sessions. No new CAP code.
- **Quiet hours.** Only merge quiet hours exist (`repos.merge.quiet_hours`), enforced by
  the merge policy for every caller. Owner and audience quiet hours (15.8) are not built.
- **Budget.** No budget governor exists (15.8 not built); "spend above a threshold" has no
  threshold to check.
- **`stop all` scope.** It stops every live remote session in the registry (#65
  semantics). Interactive sessions and their seats are not the listener's to stop.
- **Threat model (9.1).** A process running as the owner can read `.wuwei/env` and forge
  inbox lines; these guards raise the bar against a stranger in the channel, a stolen
  Slack session without the authenticator, and mistakes, not against the owner's own user.

## Deferred

- Planner `Bash` scoping in remote sessions (named in #65 tasks): the planner needs Bash
  for the `wuwei` CLI, the same hooks guard it as on the host, and `headless` accepts
  bare tool names only. Revisit with the responder role.
- Budget threshold for the second factor: with the budget governor (15.8).
- Owner quiet hours for started sessions: with 15.8.
- Signal safety-number pinning: with the Signal adapter.
