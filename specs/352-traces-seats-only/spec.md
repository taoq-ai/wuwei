# Feature Specification: Tool-sequence decisions apply to item seats only, once per session per day, and never to the planner or lead session

**Feature Branch**: `352-traces-seats-only`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #352, "fix(traces): tool-sequence decisions apply to item seats only,
once per session per day, and never to the planner or lead session". Design spec section 8
(S2 runtime traces). Builds on #260 (session registry), #287 (heartbeat), #331 and #345
(posture profiles) and #342 (doctor). Owner-reported second first-day trial, 2026-10-03,
development build of 0.12.0.

## Evidence (read-only, scratch workspace on `main`)

The trial: the planner session, registered with `wuwei plan session <id> --take-over`, ran
Bash then Write and Bash then Edit on its first commands. The sweep queued D-2 ("critical
tool sequence Bash -> Write, session has no matching item reservation") and D-3 (the same for
Bash -> Edit), both recommending `investigate` and keeping "affected work paused", with the
same session digest, before any seat started. The planner has no item by design.

Reproduced in a scratch workspace built from the `tests/test_watch.py` `case` fixture: a
session with no seat, registered as planner with `wuwei plan session <id>`, one critical
chain from the fake ZIRAN report, one `watch.sweep`: exit 1, `scanner_owed` 1, one
`scanner.finding` page, and `D-1.md` with `Context: Session has no matching item
reservation.` and `Outcome: pending`. Two chains give two decisions.

Root cause, all in `cli/wuwei/scanner.py` (the traces guard only records spans):

1. `_trace_response` (lines 59 to 107) treats every finding the same. It pages first
   (line 65), then queues a decision whether or not the session is a seat: the seat lookup
   (lines 70 and 71, `trace_sessions` of `brief.seats`) only decides which items to park and
   which `Context:` line to write (line 87). Nothing reads the session registry
   (`planner_session_id`, `sessions`), so the planner, its subagents and a shepherd session
   are treated as suspect seats.
2. The dedupe key (line 66) is the hash of the whole finding (`chain`, `risk_level`,
   `session_id`), so one session gets one decision per chain, not per session.
3. Nothing reads the posture: `trace_sweep` (lines 110 to 147) has the config but never
   calls `workspace.posture`, so observe, guarded and strict queue the same decisions, and
   `scanner_owed` (line 143) counts every finding, so every sweep of the day exits 1 while the
   planner's chain stays in `traces.jsonl`.
4. Decisions already written stay pending: the board (`cockpit_snapshot` in
   `cli/wuwei/commands/dashboard.py` line 38), `steward.decision_queue` and `close`
   (`closing.unresolved`, lines 183 to 185: an owner-routed decision without an owner
   outcome) keep them open.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The planner works without owner decisions about its own tools (Priority: P1)

The planner session (and its lead and steward subagents) runs Bash, then Write, then Edit.
No owner decision is created in any posture. One silent event per session per day records
that the chain was seen: `traces.noted` with `note: "traces: planner session, chain noted"`.

**Why this priority**: two spurious owner decisions on day one, before any seat started,
teach the owner to ignore the security decision queue.

**Independent Test**: a seeded day with `plan session P` and a scanner that reports
Bash -> Write and Bash -> Edit for session P; run `scanner.trace_sweep` twice under each
posture.

**Acceptance Scenarios**:

1. **Given** the planner session running Bash then Write then Edit, **When** the sweep runs
   (twice) under observe, guarded or strict, **Then** no decision is created and exactly one
   `traces.noted` event is recorded for that session, with no `scanner.finding` page and
   `scanner_owed` 0.
2. **Given** a subagent of the planner session (trace session id `P:<agent id>`) that is not
   bound to a seat, **When** its chain is swept, **Then** it is treated as the planner (one
   `traces.noted`, no decision).
3. **Given** a session whose registry row has role `shepherd` or `remote`, **When** its chain
   is swept, **Then** it is treated the same way, with that role in the note.

---

### User Story 2 - An unknown session stays visible, decided on only under strict (Priority: P1)

A session that is neither a seat nor registered for non-seat work runs dangerous chains.
Under observe or guarded it gets one `traces.unmatched` event per day and no decision; under
strict it gets one decision per session per day, not one per chain.

**Why this priority**: keeps the security signal for sessions WUWEI cannot account for, at
the weight of the posture the owner chose. `--shadow` is observe (its effective posture
through `workspace.posture`), so a shadow-week workspace stays quiet.

**Independent Test**: the same seeded day with a second session U that has no registry row;
the scanner reports both chains for U.

**Acceptance Scenarios**:

1. **Given** an unknown session with two chains under guarded, **When** the sweep runs twice,
   **Then** one `traces.unmatched` event and no decision.
2. **Given** the same under observe, or under guarded with `guards.mode = "shadow"`, **Then**
   one `traces.unmatched` event and no decision.
3. **Given** the same under strict, **When** the sweep runs twice, **Then** exactly one
   decision for that session, whose `Context:` says the session has no item reservation and
   no registration, and the sweep counts the findings as owed.
4. **Given** a session whose only registry row is `adhoc` (written by SessionStart),
   **Then** it is treated as unknown.

---

### User Story 3 - Seats keep today's response (Priority: P1)

A session bound to a seat through `trace_sessions` keeps the existing response in every
posture: page, park the seat's item, one decision per chain.

**Why this priority**: seats are what the S2 rule exists for; the fix must not weaken it.

**Independent Test**: the existing mapped cases of `test_trace_sweep_parks_queues_and_pages`
and `test_opaque_session_identity_still_maps_without_decision_injection` pass unchanged.

**Acceptance Scenarios**:

1. **Given** a seat session with a critical chain, **When** the sweep runs, **Then** the
   item is parked, one `scanner.finding` page and one owner decision per chain, as today.
2. **Given** a seat session whose id is also the registered planner id, **Then** the seat
   response wins.

---

### User Story 4 - doctor --fix closes the decisions the old rule wrote (Priority: P2)

Today's pending D-n of the old shape (the critical tool-sequence question with
`Context: Session has no matching item reservation.`) show as one Day row in `wuwei doctor`
and are closed by `wuwei doctor --fix` with `Outcome: superseded` and the reason, once.

**Why this priority**: the trial board still shows D-2 and D-3 after the fix ships.

**Independent Test**: write two decisions of the old shape into today's decisions directory,
run `doctor` and `doctor --fix` with a confirming callback.

**Acceptance Scenarios**:

1. **Given** two pending D-n of this shape from before the fix, **When** `doctor --fix` runs
   and the owner confirms, **Then** both records read `Outcome: superseded` with a `Notes:`
   line naming the reason, both are answered owner outcomes in state, the board, the steward
   decision queue and `close` no longer list them, and one `doctor.fixed` event records the
   fix.
2. **Given** the fix already applied, **When** `doctor` runs again, **Then** no row offers it.
3. **Given** a seat decision (`Context: Affected reserved items parked where active.`) or an
   answered one, **Then** doctor does not touch it.

### Edge Cases

- A trace session id that redaction replaced with a hash cannot be matched to the registry;
  it is unknown (fails toward visibility).
- A corrupt `events.jsonl` while checking the once-per-day event: the sweep reports
  `scanner: unmeasured` (exit 2), as for any unreadable trace input.
- A planner subagent bound to a seat through its transcript is a seat.
- A session holding an item claim (`claims`) is not a seat by that alone: the planner holds
  the claims for the builders it briefs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The sweep MUST classify each critical finding's session as seat (in some
  seat's `trace_sessions`), registered (the session id, or for a subagent its part before
  the first `:`, equals `planner_session_id` or has a registry row whose role is not
  `adhoc`) or unknown, in that order.
- **FR-002**: A seat finding MUST keep today's response (page, park, one decision per chain).
- **FR-003**: A registered finding MUST create no decision and no page in any posture, and
  MUST append at most one `traces.noted` event per session per day with the session digest,
  the role, the chain and `note: "traces: <role> session, chain noted"`.
- **FR-004**: An unknown finding under observe or guarded MUST create no decision and no
  page, and MUST append at most one `traces.unmatched` event per session per day with the
  session digest, the chain and the posture.
- **FR-005**: An unknown finding under strict MUST page as today and queue at most one
  decision per session per day, with a `Context:` distinct from the old one.
- **FR-006**: The posture MUST be the effective one from `workspace.posture(config)`, so
  `guards.mode = "shadow"` is observe.
- **FR-007**: `scanner_owed` MUST count only findings that paged (seat or strict unknown).
- **FR-008**: `traces.noted` MUST be silent; `traces.unmatched` MUST be silent under observe
  and a nudge otherwise, as `guard.would_refuse` is. Both kinds name the sweep as producer.
- **FR-009**: `wuwei doctor` MUST show a Day row `trace decisions` (warn, `apply:
  trace-decisions`) when today has pending, unanswered decisions of the old shape, and no row
  otherwise. `doctor --fix` MUST preview them in its batch and, after the one digest, set
  each record's `Outcome:` to `superseded`, add a `Notes:` line with the reason, and record
  an owner outcome `superseded` in `decision_outcomes`, bound to what the preview showed.

### Key Entities

- **Session class**: seat, registered (with its role) or unknown; derived from day state on
  each sweep, never stored.
- **`traces.noted` and `traces.unmatched` events**: one per session per day, keyed by the
  session digest the decisions already print.

## Success Criteria *(mandatory)*

- **SC-001**: In the issue's seeded day (planner P and unknown U, Bash -> Write and
  Bash -> Edit twice each, two sweeps), the decision count is 0 under observe, 0 under
  guarded and 1 under strict.
- **SC-002**: The existing seat trace tests pass unchanged.
- **SC-003**: After `doctor --fix` on a day holding the trial's two decisions, the board
  shows no pending decision and `doctor` shows no `trace decisions` row.

## Assumptions

- "Registered" means `planner_session_id`, or a registry row with role `shepherd`, `remote`
  or `seat-host`. An `adhoc` row is unknown: SessionStart writes one for every Claude Code
  session in the workspace, build seats included, so exempting it would exempt every session
  and leave strict nothing to decide. The issue's "lead" and "steward" run as subagents of
  the planner session and are matched through the parent session id.
- A planner subagent that is a seat but whose transcript binding failed is now treated as the
  planner (event, no decision). That narrows the rule as the issue asks; binding runs on
  every PostToolUse from the brief reference, so it is the exception.
- "Once per day" for the events is checked against today's `events.jsonl`, the pattern
  `trace_sweep` already uses for its "not configured" line. No new state key or file, as the
  notes require; strict decisions reuse `scanner_decisions` with the session digest as key.
- doctor matches the old shape on the old `Context:` line, which the new code no longer
  writes, so it never supersedes a decision the new rule made.
- doctor supersedes only today's decisions; earlier days are closed and archived.
- The owner outcome `doctor --fix` records is `decided_by: owner` because the fix runs only
  after the owner types the digest on the host terminal. Without it `close` keeps reporting
  the decisions as pending owner decisions.
- The owner's point that `--shadow` should mean posture observe: #355 fixes the config file;
  this issue reads the effective posture, which already maps `guards.mode = "shadow"` to
  observe, so a shadow workspace gets events and no decisions for unknown sessions.
- The issue says "the traces guard"; the rule lives in the sweep (`scanner.py`), so that is
  where it changes. The guard keeps recording spans as it does.
