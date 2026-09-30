# Feature Specification: control-plane interface with Remote Control and push as default

**Feature Branch**: `057-control-plane-default`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #57, feat(control-plane). Design section 15.4; wave G notes (one messaging
channel, Slack DMs polled with urllib, arriving with #50 and #65). Depends on #48 (inbound
adapter interface), which is being built in parallel.

## Starting point (read on main, a61fe34)

This is a feature, not a bug; nothing fails today. What exists and what is missing:

- Owner decisions are records `days/<date>/decisions/D-n.md` validated by
  `cli/wuwei/decision.py:44` (`evaluate`). An owner-routed decision is listed in the
  `decision_routes` state key by `decision.route_owner` (`cli/wuwei/decision.py:183`) and is
  pending until `decision.answered` (`cli/wuwei/decision.py:194`) finds an owner outcome.
  `cli/wuwei/commands/status.py:122-130` uses exactly that pair to raise the
  `decision.pending` nudge.
- The planner asks each owner decision as an `AskUserQuestion` widget; the PreToolUse guard
  `cli/wuwei/guards/decision.py:99` (`check_question`) refuses a question that does not cite
  a D-n or C-n record that exists today and passes lint. Its docstring already names
  "future control-plane escalation" as a caller.
- The owner's answer becomes an outcome only through `wuwei decision outcome <id> <option>`
  in a host terminal with a typed digest (`cli/wuwei/commands/decision.py:56-80`).
  `docs/site/configuration.md:238-239` states that remote authenticated decisions remain M5
  work.
- There is no control-plane module, no reply parser, and no `control_plane` config section.
  Reproduced read-only in a scratch workspace: a `.wuwei/config.toml` holding
  `[control_plane] content = "summary"` makes `workspace.load_config` raise
  `ConfigError: config.toml: unknown key control_plane at line 1`
  (schema `cli/wuwei/workspace.py:35-133`).
- The only owner-bound sender today is the chat port's `dm(text)`
  (`adapters/chat/slack.py:36-41`), used by the two-way decision digest
  (`cli/wuwei/watch.py:117`).

What Claude Code provides today and what WUWEI adds is recorded in research.md (verified
against the Claude Code docs on 2026-09-30). In short: Claude Code already delivers the
default control plane (Remote Control plus mobile push for questions); WUWEI adds the
decision rendering, the content policy, the shared reply parser and the reply record.

## User Scenarios & Testing

### User Story 1 - A pending decision reaches the owner with its options (Priority: P1)

The owner is away from the host. A decision routed to the owner is escalated through the
control plane: by default it is the question widget in the planner session, which Claude
Code Remote Control pushes to the phone; through a messaging transport it is a short
message. Either way it carries the decision id and its options.

**Independent Test**: `python -m pytest -q tests/test_control_plane.py -k escalate`.

**Acceptance Scenarios**:

1. Given a pending decision D-3 and a messaging transport, when it is escalated, then the
   transport receives one message that names D-3, its one-line question and each option id
   with its description, and nothing else from the record (no context, scores or
   pre-mortem).
2. Given `control_plane.content = "none"`, then the message names D-3 and the option ids
   only: no question text and no option descriptions.
3. Given no transport (the default), then escalate sends nothing, returns exit 0 with the
   widget text, and that text passes the existing question citation guard for D-3.
4. Given a decision id that is not pending (unknown, seat-decided or already answered by the
   owner), then escalate exits 1 and sends nothing.

### User Story 2 - A reply is recorded against the decision id (Priority: P1)

The owner answers with a short reply. The shared parser maps "approve D-3", "option B on
D-5" and "drop it" to a decision answer, and the answer is recorded against the decision id.

**Independent Test**: `python -m pytest -q tests/test_control_plane.py -k "parse or reply"`.

**Acceptance Scenarios**:

1. Given a pending decision and the reply "option B on D-3", then a `decision.replied` event
   `{id: "D-3", option: "B"}` is recorded and the result lists that answer.
2. Given "approve D-3", then the recorded option is the record's Recommendation.
3. Given "drop it" while exactly one decision is pending, then the recorded option is that
   decision's single Do nothing or Defer option.
4. Given "approve something" with no matching decision, then the options of every pending
   decision are echoed back through the transport, nothing is recorded, and the exit is 1.
5. Given a reply that names a pending decision with an option it does not have, "drop it"
   while zero or several decisions are pending, or any other text, then the options are
   echoed back and nothing is recorded (never guessed).
6. Given a transport that could not poll, or a pending record that cannot be read or fails
   lint, then the exit is 2 with the reason and nothing is recorded.

### User Story 3 - Milestone notifications (Priority: P2)

Milestone digests reach the owner as notifications.

**Independent Test**: `python -m pytest -q tests/test_control_plane.py -k notify`.

**Acceptance Scenarios**:

1. Given a transport, then notify sends the summary; given `content = "none"`, it sends a
   fixed line that carries no workspace content.
2. Given no transport, then notify sends nothing and returns exit 0 with the summary for the
   session to show (Claude Code decides whether to push it).

### User Story 4 - The owner sets the content policy (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_control_plane.py -k config`.

**Acceptance Scenarios**:

1. Given no `[control_plane]` section, then `control_plane.content` is `summary`.
2. Given `content = "none"`, it loads; given any other value, config loading reports a
   configuration finding naming `control_plane.content`.

### Edge Cases

- Replies are matched case-insensitively, with whitespace collapsed and one trailing `.`
  or `!` dropped; the recorded id and option use the record's spelling.
- Extra words ("approve D-3 please") are not a match: echo, never guess.
- An option id that matches two options case-insensitively is ambiguous: echo.
- A second reply for a still-pending decision records a second event; the decision stays
  pending until the owner outcome is recorded on the host.
- With no pending decisions, the echo says so and records nothing.
- The echo obeys the content policy exactly like an escalation.

## Requirements

### Functional Requirements

- **FR-001**: The control plane offers `escalate(decision)`, `notify(summary)` and
  `poll_replies(since)`, each taking an optional transport; without one they implement the
  default (Remote Control plus push, delivered by Claude Code).
- **FR-002**: Pending decisions are exactly the owner-routed decisions that have no owner
  outcome, the same set the `decision.pending` nudge uses.
- **FR-003**: One shared parser maps "approve D-n", "option X on D-n" and "drop it" to
  `(decision id, option id)` against the pending decisions and returns nothing for anything
  else.
- **FR-004**: A parsed answer appends one `decision.replied` event holding only the decision
  id and the option id; the reply text is never stored.
- **FR-005**: An unparseable or unmatched reply is answered with the pending options through
  the transport and records nothing.
- **FR-006**: A recorded reply is not an owner outcome: `decision_outcomes`, item phases and
  the `decision.pending` nudge are unchanged; `wuwei decision outcome` on the host stays the
  only owner-outcome writer.
- **FR-007**: `control_plane.content = "summary" | "none"`, default `summary`, governs every
  message sent through a transport (escalation, echo, notify).
- **FR-008**: Exits follow the three-state rule: 0 clean, 1 finding (echoed reply, decision
  not pending), 2 could not run (transport failure, unreadable or invalid record,
  unreadable state).
- **FR-009**: `decision.replied` cannot be written through `wuwei event` and does not raise
  a nudge on its own.

### Key Entities

- **Pending decision**: a D-n in `decision_routes` with no owner outcome; its Question,
  Options and Recommendation come from the validated record.
- **Reply**: one inbound text from the transport's poll; only its parsed id and option are
  kept.
- **`decision.replied` event**: `{id, option}` in today's `events.jsonl`.

## Success Criteria

- **SC-001**: Both issue acceptance scenarios pass as unit tests with a fake transport.
- **SC-002**: No reply text, question text or option description is stored in events or
  state by this feature.
- **SC-003**: The full suite stays green.

## Assumptions

- The default control plane needs no WUWEI transport: Claude Code Remote Control with
  "Push when actions required" already pushes the planner's question widgets to the phone
  and keeps them open until answered (research.md). WUWEI's default implementation renders
  the widget text and sends nothing; the CLI has no way to trigger a push.
- A reply recorded through the control plane is evidence, not an owner outcome. Promoting a
  transport-authenticated reply to an owner outcome (the sender allowlist of 15.3, the second
  factor of 15.9) is a trust-boundary change under design 9.1 and belongs to #65 with the
  real Slack transport. Until then the owner confirms on the host with
  `wuwei decision outcome`, as `docs/site/configuration.md` already says.
- "drop it" means: answer the only pending decision with its Do nothing or Defer option
  (every valid record has one, `decision.evaluate`). It is not a draft action; drafts keep
  their own `wuwei drafts drop` path.
- "approve D-n" means: take the record's Recommendation.
- The transport is duck-typed: `dm(text, *, root)` (the existing chat port) and
  `poll(since, *, root)` returning a registry `Result` whose data is a list of normalised
  inbound events with at least `text` (the #48 inbound interface). Sender filtering is the
  transport's job (#50 allowlist); the parser trusts nothing beyond matching text to pending
  decisions.
- `content = "summary"` renders the decision id, the one-line Question and each option id with
  its description; `none` renders the decision id and option ids only. The default (no
  transport) always renders the summary form: the widget stays inside Claude Code, and 15.4
  scopes the content policy to messaging adapters.
- No new CLI command, no listener and no adapter kind in this issue: the notes scope #57 to a
  unit-level interface and parser with a fake transport; `wuwei listen` and the Slack wiring
  arrive with #50 and #65.
- Signal, WhatsApp, routines, quiet hours and urgency tiers are out of scope for wave G.

## Deferred

- #65: wire `poll_replies` into `wuwei listen` with the Slack transport, and decide whether
  an authenticated reply may record an owner outcome.
- #50: Slack inbound polling that satisfies the transport's `poll`.
