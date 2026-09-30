# Feature Specification: Session registry: several Claude Code sessions in one workspace, with one planner

**Feature Branch**: `260-session-registry`

**Created**: 2026-09-30

**Status**: Draft

**Input**: GitHub issue #260, "feat(team): session registry: several Claude Code sessions in
one workspace, with one planner". Design spec sections 3.4 (three-state exits), 4.2.1 (Stop
and wake), 5.2 (planner session) and 15.9 (sessions from the control plane). Owner request
2026-09-30: "is there a way to allow wuwei to support multiple sessions?". Depends on
nothing; #65 (control plane) consumes it.

## Evidence (read-only, scratch workspace on `main`)

In a fresh workspace (`.wuwei/` plus an empty `config.toml`), `wuwei plan session AAA` then
`wuwei plan session BBB` both exit 0 and `wuwei state get planner_session_id` prints
`"BBB"`: the second session silently replaces the planner. `wuwei sessions` does not exist
(argparse exit 2). Root causes on `main`:

1. `plan.session` (`cli/wuwei/plan.py` lines 13 to 19) writes `planner_session_id`
   unconditionally; nothing refuses a different session or records a hand-over.
2. `lifecycle.session_start` (`cli/wuwei/guards/lifecycle.py` lines 16 to 53) reads memory,
   health and the wake marker but records nothing about the session. `lifecycle.stop`
   (lines 67 to 80) reads state only to compare `session_id` with `planner_session_id`;
   no lifecycle guard runs on SubagentStop. A non-planner session is guarded but
   invisible.
3. `brief.write` (`cli/wuwei/brief.py` lines 146 to 267) and `wuwei worktree add`
   (`cli/wuwei/commands/worktree.py` lines 19 to 39) do not know which session called
   them, so two sessions can brief the same item.
4. `status --line` (`cli/wuwei/commands/status.py` `run`, lines 183 to 208) and `nudges`
   (`status.scan`) have no notion of sessions or a stale planner.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The owner sees every session in the workspace (Priority: P1)

The owner runs the planner in one Claude Code session and opens a second session in the same
workspace for ad hoc work. `wuwei sessions` lists both with role, age and what each did
last; `wuwei status --line` counts them.

**Why this priority**: every other behaviour (planner uniqueness, stale planner, claims)
reads this registry.

**Independent Test**: seed today's day state, pipe two SessionStart payloads with different
`session_id` through `wuwei hook SessionStart`, run `wuwei sessions` and `wuwei status
--line`.

**Acceptance Scenarios**:

1. **Given** two sessions that started in one workspace with today's day state present,
   **When** `wuwei sessions` runs, **Then** it exits 0 and lists both ids with role
   (`planner` for the registered planner, `adhoc` otherwise), age, idle time, stale flag and
   the last hook, and `status --line` contains `sessions 2`.
2. **Given** a registered session, **When** its Stop or SubagentStop hook runs, **Then** its
   `last_seen` and last hook are updated and no other state field changes.
3. **Given** a session with no hook activity for longer than `sessions.stale_seconds`,
   **When** `wuwei sessions` runs, **Then** that row is `stale: true` and `status --line`
   no longer counts it.
4. **Given** no day state for today, **When** SessionStart runs, **Then** no `state.json`
   is created (the day is created by its own producers, as today).

---

### User Story 2 - Exactly one planner, handed over on purpose (Priority: P1)

A second session running `wuwei plan session <id>` is refused with the current planner's id.
With `--take-over` the hand-over is recorded as an event and wakes go to the new planner.

**Why this priority**: today a second session silently steals planner wakes.

**Independent Test**: `plan session A`, then `plan session B` with and without
`--take-over`, then a wake marker and the lifecycle Stop guard for A and B.

**Acceptance Scenarios**:

1. **Given** planner A registered today, **When** `wuwei plan session B` runs, **Then** it
   exits 2, stderr names A and `--take-over`, `planner_session_id` stays A and no event is
   appended.
2. **Given** planner A registered today, **When** `wuwei plan session B --take-over` runs,
   **Then** it exits 0, `planner_session_id` is B, a `plan.session` event records
   `session_id: B` and `previous: A`, and a pending planner wake is consumed by B's Stop and
   not by A's.
3. **Given** planner A registered today, **When** `wuwei plan session A` runs again,
   **Then** it exits 0 (re-registration of the same session is unchanged).
4. **Given** the planner's registry row is stale, **When** `wuwei nudges` runs, **Then** one
   nudge names the stale planner and the command `wuwei plan session <session id>
   --take-over`.

---

### User Story 3 - One session builds an item at a time (Priority: P2)

`wuwei brief builder <item> <name>` and `wuwei worktree add <item>` record the calling
session as the item's claimant. A different live session briefing or adding a worktree for
the same item is refused with the claimant's id.

**Why this priority**: prevents two sessions building one item; needs Story 1 for liveness.

**Independent Test**: set `WUWEI_SESSION_ID=A`, brief a builder for ITEM-1; set
`WUWEI_SESSION_ID=B`, brief a builder for ITEM-1 again.

**Acceptance Scenarios**:

1. **Given** session A briefed a builder for ITEM-1 and A is live, **When** session B runs
   `wuwei brief builder ITEM-1 <name>`, **Then** it exits 2, stderr names A, and no brief
   file or event is written.
2. **Given** the same claim, **When** session B runs `wuwei worktree add ITEM-1`, **Then** it
   exits 2 naming A and the vcs port is not called.
3. **Given** A's registry row is stale, **When** B briefs ITEM-1, **Then** the brief is
   written and the claim moves to B.
4. **Given** no claim on ITEM-1, **When** a caller without a session id briefs it, **Then**
   the brief is written as today and no claim is recorded.
5. **Given** a live claim by A, **When** a gate brief (sentinel role) for ITEM-1 is written
   from any session, **Then** it is not refused by the claim.

---

### User Story 4 - Remote sessions are visible (Priority: P3)

The control plane (#65) registers the sessions it starts with role `remote` and a thread
reference, so `wuwei sessions` shows them and `stop <session>` (in #65) can find them.

**Independent Test**: call the registry producer with `role='remote'` and a thread
reference; `wuwei sessions` shows the row with both.

**Acceptance Scenarios**:

1. **Given** a session registered with role `remote` and thread `T`, **When** `wuwei
   sessions` runs, **Then** the row shows role `remote` and thread `T`, and a later Stop for
   that session keeps both.
2. **Given** an unknown role, **When** the producer is called, **Then** it raises and
   nothing is written.

### Edge Cases

- A session outside any WUWEI workspace: every new hook path returns 0 with no write.
- A registry write that fails on Stop or SubagentStop (lock timeout, unreadable state):
  the guard still returns 0 with a reason (Stop keeps its existing `planner wake
  unmeasured: <reason>`, SubagentStop returns `session registry unmeasured: <reason>`),
  because a Stop that exits 2 would block the turn end; on SessionStart the reason
  `session registry unmeasured: <reason>` joins the session context with code 2, as the
  other SessionStart checks do.
- Malformed `sessions` or `claims` in state: readers raise and commands exit 2 with the
  reason.
- Stop with `stop_hook_active` true: unchanged early return, no registry write.
- `--take-over` when no planner is registered, or naming the current planner: behaves as a
  plain registration.
- The previous planner after a take-over: still named by its earlier `plan.session` event,
  so the planner Stop anchor (`guards/stop.py`) keeps applying to it, as for a replaced
  planner today (`tests/test_stop.py::test_planner_handoff_does_not_exempt_original_session`).
- Day rollover: the registry is day state; a session started yesterday reappears at its next
  Stop or SubagentStop.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SessionStart, Stop and SubagentStop inside a workspace MUST upsert
  `sessions[<session_id>]` in today's state with `role`, `started`, `last_seen`, `cwd` and
  `last_hook`, in one state write per hook, only when today's `state.json` exists.
  SessionStart MUST NOT add any other state read or write.
- **FR-002**: The registry MUST be writable only by its producers: `sessions` and `claims`
  are reserved in `state.STATE_PRODUCERS`, `session.seen` and `item.claimed` in
  `EVENT_PRODUCERS`; `wuwei state set` and `wuwei event` refuse them (meta-test).
- **FR-003**: The role shown for a session MUST be `planner` when its id equals
  `planner_session_id`, otherwise the stored role (`adhoc`, `seat-host` or `remote`).
- **FR-004**: `wuwei sessions` MUST print a JSON list of rows (session id, role, started,
  last seen, age and idle seconds, stale flag, last hook, claimed items, cwd, thread when
  set), exit 0, `[]` with no day state, and exit 2 with the reason on unreadable state.
- **FR-005**: `status --line` MUST show `sessions N` (live sessions) when N is at least 1;
  `status --json` MUST carry `sessions`.
- **FR-006**: `wuwei plan session <id>` MUST exit 2 naming the current planner when another
  session is registered, unless `--take-over`; a take-over MUST append `plan.session` with
  `previous`.
- **FR-007**: `nudges` (and every surface built on `status.scan`) MUST add one nudge when the
  registered planner's registry row is stale, naming the take-over command.
- **FR-008**: `brief builder` and `worktree add` MUST refuse (exit 2, naming the claimant)
  when the item is claimed by a different live session, and record the calling session as
  claimant when it is known.
- **FR-009**: SessionStart MUST export the session id to later Bash commands of that session
  (`WUWEI_SESSION_ID`, through Claude Code's `CLAUDE_ENV_FILE`) so the CLI knows its caller.
- **FR-010**: New config key `sessions.stale_seconds` (integer, minimum 1, default 3600).

### Key Entities

- **Session row** (`state.sessions[<id>]`): `role`, `started`, `last_seen`, `cwd`,
  `last_hook`, optional `thread`.
- **Item claim** (`state.claims[<item>]`): the claiming session id.

## Success Criteria *(mandatory)*

- **SC-001**: The four acceptance lines of issue #260 pass as tests: two sessions listed and
  counted; second `plan session` exits 2 and `--take-over` hands over wakes; a builder brief
  for an item claimed by another live session exits 2 naming the claimant; guard, mutation
  and hook-level tests pass with the producer-only meta-test covering the new keys.
- **SC-002**: The full suite passes; the SessionStart, Stop and SubagentStop hook latency
  tests stay green.

## Assumptions

- Registry storage is today's day state (`state.json`), as the orchestrator notes require
  ("one state write"). It is day-scoped like `planner_session_id`; there is no cross-day
  registry.
- Hooks register only into an existing day state and never create it: `close`, `report`,
  `pr_actions.evaluate`, `brief.read_day` and the Stop anchor treat a missing `state.json`
  as meaningful, and a session opening before the morning plan must not change that. The
  planner's own row is written by `plan session` in the same write that registers it.
- The CLI learns its calling session from `WUWEI_SESSION_ID`, exported at SessionStart via
  `CLAUDE_ENV_FILE` (the Claude Code mechanism for SessionStart hooks to set environment for
  the session's later Bash commands). Seats inherit it: Claude subagents share the parent
  session's environment and Codex seats are launched from it. A host terminal has no id:
  it records no claim and is refused on an item a live session claims.
- Claims are coordination, not trust evidence: nothing in guards, merge or metrics treats a
  claim as proof of anything, so an environment value a seat could change is acceptable.
  The registry keys themselves are producer-only.
- "Stale" is measured only from hook activity (SessionStart, Stop, SubagentStop, plan
  session, claims). A long subagent run inside the planner produces no Stop until it ends,
  so the default is 3600 seconds rather than `watch.stale_seconds` (900).
- Refusals exit 2 as the issue states, even though they are policy outcomes.
- The hand-over event reuses kind `plan.session` with a `previous` field instead of a new
  kind, so the Stop anchor's planner history (`guards/stop.py` lines 22 to 26) stays one
  query.
- `seat-host` is an accepted role value with no producer in this issue; the caller that
  knows a session hosts seats sets it. `remote` is set by #65 through the same producer
  function. `stop <session>` belongs to #65 and is not built here.
- "What it is doing" is the last hook name (with SessionStart source or SubagentStop agent
  type) plus the items the session claims; no message text is stored (constitution VII).
