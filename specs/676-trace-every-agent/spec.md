# Feature Specification: every subagent launched in a workspace is traced as a seat

**Feature Branch**: `676-trace-every-agent`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #676 (owner, 2026-10-10, item 44): a review run as a general-purpose
agent left no trace records; when it breached a data-access rule there was nothing to audit.
Deliver: the agent-launch guard registers any subagent launched inside a workspace, whatever
its type, as an ad-hoc seat (`role: adhoc`, the type and the first line of the prompt
recorded); its hooks inherit the workspace posture and write traces like a seat;
`wuwei seat start --role reviewer --adhoc "<prompt>"` gives the planner a traced reviewer
without a charter; `doctor` reports untraced subagents when the Claude Code session recorded
a launch the guard did not see (SubagentStop with no seat). Under strict an untyped launch is
refused with the adhoc command.

## Root cause

Reproduced read-only on the owner's workspace for 2026-10-10 (copies of `traces.jsonl` and
`events.jsonl`, and the review agent's own transcript under the Claude Code project
directory). The review was launched by the planner with `subagent_type: general-purpose`
(description `Fable review of prereg PR 16`).

- Its transcript holds 21 tool calls. `traces.jsonl` holds 17 spans for it: 16 calls plus
  the hand-back, each with `gen_ai.agent.name = general-purpose` and session
  `<planner session>:<agent id>`. So most of its calls did reach `traces.jsonl`; the owner's
  report that they "never reached" it is not exact. What was missing is everything that
  makes those spans auditable:
  - `cli/wuwei/guards/agent_launch.py:50-52` and `:64-65` (`_seat`) return None for any type
    that is not a WUWEI role, so `check` records nothing for the launch: no seat, no
    `seat launched` event, no type, no prompt. `stop` returns early for the same types
    (`agent_launch.py:254`), so its end is not recorded either.
  - `cli/wuwei/guards/traces.py:61-73` (`_record`) binds a trace session to a seat only
    through the `WUWEI brief:` reference in the transcript, so this session is in no seat's
    `trace_sessions`.
  - `cli/wuwei/scanner.py:71-79` therefore treats a dangerous chain from that session as
    unknown: one silent `traces.unmatched` per day under observe and guarded, no page, no
    decision, no parked work. `wuwei why` has no view of the agent at all.
- The other 4 calls are absent from `traces.jsonl` for reasons that apply to every seat,
  not only untyped agents (see Deferred): 2 failed, and Claude Code reports a failed call as
  `PostToolUseFailure`, which `hooks/hooks.json` does not register; 2 ran after the agent's
  shell had `cd`-ed into a repository outside the workspace, and `traces.check` scopes by
  `workspace.guard_scope(payload)` (`traces.py:92`), which reads only the cwd and file
  targets.
- The subagent transcript's first user message equals the Agent call's prompt byte for byte
  (same length and sha256). That is what lets a launch be matched to its later tool calls
  and its stop without a brief.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which launches are untyped? A: an `Agent` call whose `subagent_type` is missing, blank
  or not a WUWEI role (`guards.wuwei_role`): `general-purpose`, `Explore`, `Plan`, another
  plugin's agent. A missing or blank type is recorded as `general-purpose`, the type Claude
  Code runs for it. WUWEI roles keep the brief path unchanged.
- Q: What decides refuse versus register? A: the resolved `seats` area level
  (`workspace.posture(config)[1]['seats']`). `block` (strict, or an owner override) refuses
  an untyped launch that `seat start --adhoc` did not record; `warn` and `off` (observe and
  guarded by default) register it and return 0. Returning a refusal under `warn` would let
  the launch through unregistered, which is the defect.
- Q: How is a launch matched to its tool calls and its stop with no brief? A: by the sha256
  of the stripped prompt. The launch guard stores it on the seat; the traces guard and the
  stop guard hash the subagent transcript's first user message and match a running adhoc
  seat with the same digest.
- Q: What does `seat start --adhoc` record? A: one reserved event `seat adhoc` with the role,
  the prompt digest and the redacted first line. The launch guard accepts an untyped launch
  under `block` when today's events hold a `seat adhoc` row with the same digest, and labels
  the seat with that role. It prints the launch instruction; it never launches anything.
- Q: Seat shape? A: in `data['seats']` like every seat, so `in_flight`, the host seat count,
  the scanner and `stuck` see it: name `adhoc-<n>` (next free number today), `role: adhoc`,
  `item` equal to the name (no plan item; the field must be a nonempty string), `type`,
  `label` (the `--role` value, else the type), `launcher` (the launching session's role:
  `planner`, a registered session role, else `adhoc`), `prompt` (first line, redacted, at
  most 200 characters), `prompt_sha256`, `status`, `started_at`. No `brief`.
- Q: What does `why` show? A: `wuwei why adhoc` prints one line per adhoc seat today: name,
  type, label, launcher, status, prompt line and its trace sessions. No adhoc seat today is
  exit 1 with the next step.
- Q: What does doctor show? A: a `day` row `untraced subagents`: `ok` with `none today`, or
  `warn` with the count of today's `subagent.untraced` events and the way to register them.
- Q: Does an untyped launch before the morning plan (no `state.json` today) register? A: no.
  There is no seat store yet and the guard never creates the day (as `sessions.touch`); it
  returns 0 under every posture, and its calls are still traced by cwd as today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - an untyped agent is a seat whose calls can be audited (Priority: P1)

The planner launches a general-purpose (or Explore, or any non-WUWEI) agent inside the
workspace. Under observe or guarded the launch goes ahead as before, and WUWEI records it as
an adhoc seat: its tool calls are bound to that seat in the trace records, a dangerous chain
from it is handled like any seat's, its stop is recorded, and `wuwei why adhoc` lists it.

**Why this priority**: the owner's defect; without it an untyped agent leaves no auditable
record.

**Independent Test**: in a test workspace with a day, run the launch guard on a
general-purpose Agent payload, then the traces guard on one of its PostToolUse payloads,
then the stop guard on its SubagentStop; assert the seat, the span, the binding, the stop and
the `why adhoc` line.

**Acceptance Scenarios**:

1. **Given** a workspace under observe with today's state, **When** the planner launches an
   Agent with `subagent_type: general-purpose`, **Then** the launch passes (exit 0), a seat
   `adhoc-1` exists with `role: adhoc`, `type: general-purpose`, the prompt's first line and
   status `running`, and a `seat launched` event names it.
2. **Given** that seat, **When** the subagent's tool call fires PostToolUse in the workspace,
   **Then** `traces.jsonl` holds its span and the seat's `trace_sessions` holds the
   subagent's trace session.
3. **Given** that seat, **When** `wuwei why adhoc` runs, **Then** it lists `adhoc-1` as an
   adhoc seat with its type, prompt line and trace session.
4. **Given** that seat, **When** the subagent's SubagentStop fires, **Then** the seat is
   `stopped` and the hook exits 0.
5. **Given** guarded, or a launch with no `subagent_type`, **Then** the same as scenario 1
   (the missing type recorded as `general-purpose`).

### User Story 2 - strict refuses an untyped launch; the planner registers it first (Priority: P1)

Under strict the planner cannot launch an untyped agent silently. The refusal names the
command; the planner runs `wuwei seat start --role reviewer --adhoc "<prompt>"`, then
launches with the same prompt, and the launch is accepted as an adhoc seat labelled
`reviewer`.

**Why this priority**: the issue's second acceptance line; strict is the posture where an
untraced agent is not acceptable.

**Independent Test**: under strict, run the launch guard on a general-purpose payload
(refused, naming the command); run `seat start --adhoc` with that prompt; run the guard
again (registered, label `reviewer`).

**Acceptance Scenarios**:

1. **Given** strict, **When** the planner launches an untyped Agent, **Then** it is refused
   (exit 1) and the reason names `bin/wuwei seat start --role <role> --adhoc "<prompt>"`.
2. **Given** strict and `wuwei seat start --role reviewer --adhoc "<prompt>"` recorded today,
   **When** the planner launches a general-purpose Agent with the same prompt, **Then** the
   launch passes and the seat has `label: reviewer`.
3. **Given** any posture, **When** `seat start --adhoc` runs without today's state, **Then**
   it exits 2 naming the morning plan; with an invalid role it exits 2 naming the role rule.
4. **Given** strict, **When** a WUWEI seat (brief) launch runs, **Then** it behaves exactly as
   before.

### User Story 3 - doctor names subagents the guard never saw (Priority: P2)

When a SubagentStop in the workspace matches no seat (launched before the upgrade, before
the day's state existed and stopped after it, or while the launch guard could not run), the
stop records `subagent.untraced`, and `wuwei doctor` warns with the count and the fix.

**Why this priority**: closes the audit loop for launches that still slip past the guard.

**Independent Test**: fire the stop guard on an Explore SubagentStop with no seat; assert
the event and the doctor row.

**Acceptance Scenarios**:

1. **Given** today's state and no adhoc seat for the prompt, **When** an untyped SubagentStop
   fires in the workspace, **Then** the hook exits 0 and `subagent.untraced` is recorded with
   the agent type and id.
2. **Given** one such event today, **When** `wuwei doctor` runs, **Then** its `day` section
   has `untraced subagents` at `warn` naming the count and `seat start --adhoc`; with none,
   `ok`.

### Edge Cases

- Two running adhoc seats with the same prompt: a trace session binds to the seat that
  already holds it, else to the oldest one with no session yet; the stop prefers the seat
  holding its trace session. (`ponytail:` ceiling: identical parallel prompts can swap
  seats; both are adhoc with the same prompt, so the audit record is the same.)
- The subagent transcript is unreadable at a tool call: the span is still written (as
  today); only the binding is skipped. At the stop: `subagent.untraced` with the reason.
- An untyped PostToolUse with no matching adhoc seat (launched before the day): span written
  as today, no state write, today's state never created.
- `seat stop <adhoc-n> --verdict <file>`: refused (exit 1) naming `--unmeasured`; an adhoc
  seat has no report to record. `--unmeasured` works as for any seat.
- The heartbeat never probes `Agent`, so it registers no seat.
- The watch sweep's running-seat brief check skips adhoc seats (they have no brief).
- The MCP launch gate (`check_mcp`) stays a WUWEI-seat gate; untyped launches are not
  scanned by it (unchanged).
- A dangerous chain from an adhoc seat's session keeps the #352 rule: tool-sequence
  decisions apply to item seats only, so the scanner does not count an adhoc seat as a seat
  and handles the session as its launcher's (a planner subagent is one silent
  `traces.noted`). The audit record is the seat itself: `why adhoc` names the trace session
  the chain belongs to.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Agent launch guard MUST, inside a workspace with today's state, register
  every untyped launch as an adhoc seat with the fields in Clarifications and append
  `seat launched`, and return 0 when the `seats` level is not `block`.
- **FR-002**: When the `seats` level is `block`, the guard MUST refuse (exit 1) an untyped
  launch whose prompt digest has no `seat adhoc` event today, naming
  `bin/wuwei seat start --role <role> --adhoc "<prompt>"`; with a matching event it MUST
  register the seat with that role as its label.
- **FR-003**: The traces guard MUST bind a subagent's trace session (and transcript path) to
  the running adhoc seat whose `prompt_sha256` matches the subagent transcript's first user
  message, writing state only when a seat matches.
- **FR-004**: The SubagentStop guard MUST stop the matching adhoc seat for an untyped
  SubagentStop in a workspace with today's state, and otherwise append `subagent.untraced`
  (agent type and id, redacted, and the reason); it MUST exit 0 either way.
- **FR-005**: `wuwei seat start --role <role> --adhoc "<prompt>"` MUST validate the role as
  an identifier and the prompt as nonblank, require today's state, append `seat adhoc`
  (role, digest, redacted first line) and print how to launch it; errors exit 2 with the
  reason.
- **FR-006**: `seat adhoc` and `subagent.untraced` MUST be reserved event kinds with their
  producers named (`wuwei seat start`, `wuwei hook SubagentStop`); `seat adhoc` is silent,
  `subagent.untraced` a nudge.
- **FR-007**: `wuwei why adhoc` MUST list today's adhoc seats, one line each.
- **FR-008**: `wuwei doctor` MUST show the `untraced subagents` row.
- **FR-009**: Consumers that assume a seat has a brief MUST skip adhoc seats: the watch
  sweep's running-seat check, the compact memory's current briefs line, and
  `seat stop --verdict`. The scanner's item-seat test (`scanner._trace_response`) MUST not
  count adhoc seats, so #352 holds.
- **FR-010**: Design spec 4.1 (Agent launch row) and 9.2 (a new invariant row) and the
  reference docs MUST describe adhoc seats, the strict refusal and `seat start --adhoc`.

## Success Criteria *(mandatory)*

- **SC-001**: A test drives launch, tool call, `why adhoc` and stop of a general-purpose
  agent under observe and asserts seat, span, binding and stop (US1 scenarios 1 to 4).
- **SC-002**: A test under strict asserts the refusal text and the accepted launch after
  `seat start --adhoc` (US2 scenarios 1 and 2).
- **SC-003**: The invariant walk covers: below strict an untyped launch is never refused;
  under strict it is refused naming `seat start --adhoc` unless recorded.
- **SC-004**: The full suite passes.

## Assumptions

- No orchestrator notes file exists for #676; the issue is the only input, and the
  reproduction above was run on the owner's live workspace read-only (copies only).
- The seats area level, not the posture name, decides the strict refusal, so an owner's
  `security.areas.seats = "block"` under guarded refuses too, consistent with every other
  guard (#331).
- A `seat adhoc` record allows any number of launches with that prompt today; it is not
  consumed. The planner owns the command, as it owns `wuwei brief`.
- An adhoc seat counts toward the running seats (host ceiling, dispatch free slots,
  `seats_launched` metrics) because it is a running agent on the host.
- "The launcher's role" in the issue title is recorded as `launcher` on the seat (the
  launching session's registry role); the seat's own role is `adhoc` as the body says, and
  `--role` becomes its `label`.
- "Its hooks inherit the workspace posture" holds already: every PreToolUse guard runs on an
  untyped agent's calls under the workspace config; no guard exempts a type. No change.
- A stale adhoc seat (its launch refused by a later PreToolUse guard, or its stop never
  seen) stays `running` like a brief seat in the same case; `seat stop <name> --unmeasured`
  clears it, and `stuck` names it once its transcript ends in the hand-back.

## Deferred

- Failed tool calls are not traced for any agent: Claude Code fires `PostToolUseFailure`
  for them, which `hooks/hooks.json`, `guards.EVENTS` and the traces guard do not handle. A
  follow-up issue registers it for the traces guard.
- A seat's calls after its shell `cd`s out of the workspace are not traced:
  `traces.check` scopes by `guard_scope(payload)` (cwd and file targets) and `hook.run`
  returns before the guards. A follow-up can scope a subagent call by its launch cwd (the
  first row of its transcript). Both apply to brief seats too, so they are not this issue.
