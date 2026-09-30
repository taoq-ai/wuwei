# Feature Specification: An answered owner decision clears close, and Stop never traps the session

**Feature Branch**: `206-decision-close`
**Created**: 2026-09-30
**Status**: Draft
**Input**: Issue #206, design sections 4.1, 5.4 and 5.8. Depends on #175 (owner
`decision outcome`) and #167 (day close). Evidence: the v0.5.0 operator dry run of
2026-09-30, rows 36, 44 and 51.

## Root cause (reproduced on main, read-only, on a copy of the dry-run workspace)

In the dry run the owner answered D-1 (an owner-routed PR scope decision) with
`wuwei decision outcome D-1 defer`. State then held
`decision_outcomes["D-1"] = {"option": "defer", "decided_by": "owner", ...}` and the
report listed `D-1: defer` under "Decisions answered", yet:

- `wuwei close` kept printing `D-1: pending owner decision: ...`. Calling
  `closing.unresolved(root, [])` on the copied workspace with main's code returns
  exit 1 with that line. Cause: `cli/wuwei/closing.py:183-185` treats every routed or
  owner-routed record as pending unless a verified PR disposition cites it; it never
  reads the owner outcome.
- `wuwei pr act` kept returning `{"action": "owner_decision", ...}` for the same PR.
  Cause: `cli/wuwei/pr_actions.py:351-356` returns `owner_decision` for any recorded
  scope decision whose comment fingerprint still matches, without checking for an answer.
- `wuwei pr disposition` could not cite the answered decision. Cause:
  `cli/wuwei/pr_actions.py:19-21` (`_verify`) rejects any decision present in
  `decision_outcomes`, including an owner outcome.
- The record kept `Outcome: pending`. Cause: `cli/wuwei/commands/decision.py:92-111`
  (`owner_outcome`) writes state only, so the cockpit filter at
  `cli/wuwei/commands/dashboard.py:28` still showed D-1 as pending.
- The report (`cli/wuwei/report.py:40-49`) and the steward queue
  (`cli/wuwei/steward.py:62-69`) already treat any recorded outcome as answered. Each
  reader decides "answered" on its own, so report and close disagree.
- With close requested and D-1 still listed, the planner Stop hook blocked with
  `stop_hook_active: false` and again with `stop_hook_active: true` (exit 2 both times).
  Cause: `cli/wuwei/guards/stop.py:33-35` validates the flag but ignores it on purpose
  ("Retry flags suppress advisory wakes, never unresolved correctness obligations").
  The session cannot end while any finding remains. The sibling Stop guard
  `cli/wuwei/guards/lifecycle.py:69-70` already returns 0 on retry.

## User Scenarios & Testing

### US1: An owner answer clears every reader (P1)

As the owner, once I answer a routed decision with `wuwei decision outcome`, I need
close, `pr act`, the report, the steward queue and the cockpit to agree it is answered,
and the record to show my choice.

Acceptance scenarios:
1. Given an owner-routed decision answered with `decision outcome`, when `wuwei close`
   runs, then it no longer lists that decision, and the report lists it under
   "Decisions answered", so report and close agree.
2. Given a PR scope decision that `pr act` created and the owner answered, when
   `pr act` runs again, then it no longer returns `owner_decision` for it: an answer of
   `change` opens a fix round with the reviewer's text; any other answer returns the
   `reply` action carrying the decision path and chosen option.
3. Given an owner-answered decision, when `wuwei pr disposition` cites it with a fresh
   owner comment, then the disposition is recorded.
4. Given `decision outcome` succeeds, then the record's `Outcome:` line reads the chosen
   option and the record still passes `decision lint`; a declined or failed confirmation
   leaves the record unchanged.
5. Given an owner outcome recorded in state while the record still reads
   `Outcome: pending` (a workspace answered under v0.5.0), then close and the cockpit
   treat the decision as answered.
6. Given a seat outcome recorded against an owner-routed decision, or a record whose
   `Outcome:` line was edited without `decision outcome`, then close still lists the
   decision as pending, and `pr disposition` still rejects a seat outcome.

### US2: Stop blocks at most once per stop attempt (P1)

As the planner, I need the Stop hook to refuse once with its reasons and then let the
session end, so an unresolved day never traps the session.

Acceptance scenarios:
1. Given close requested and unresolved work, when Stop runs with
   `stop_hook_active: false`, then it blocks (exit 2, `decision: block`, reasons listed).
2. Called again for the same stop attempt with `stop_hook_active: true`, then it exits
   0 and prints no second refusal; the first refusal stays in the session context.
3. Given `stop_hook_active` that is not a boolean, then a registered planner's Stop is
   still exit 2 (fail closed on a malformed payload).
4. `wuwei close` itself is unchanged: it still reports every unresolved finding.

## Requirements

- FR-001: One function, `decision.answered(data, identifier)`, decides whether a
  decision has a recorded owner outcome. Only a `decision_outcomes` record with
  `decided_by == "owner"` counts; a seat record, a missing record or an edited file line
  does not.
- FR-002: Day close (`closing.unresolved`) does not report an owner-routed decision that
  `answered` accepts.
- FR-003: `pr act` does not return `owner_decision` for a recorded scope decision that
  `answered` accepts; it routes by the owner's option as in US1 scenario 2.
- FR-004: `pr disposition` accepts an owner-answered decision and still rejects any
  other recorded outcome.
- FR-005: `decision outcome` rewrites the record's `Outcome:` line to the chosen option
  after the state write succeeds.
- FR-006: The cockpit hides a decision that `answered` accepts, even when its record
  still reads `Outcome: pending`.
- FR-007: The planner Stop guard returns `(0, '')` when `stop_hook_active` is `True`.
- FR-008: The day-close docs describe both changes.

## Success Criteria

- SC-001: Replaying the dry-run sequence (route, owner outcome, close) in tests gives
  close exit 0 for the decision and a report line `D-1: <option>`.
- SC-002: A Stop retry with `stop_hook_active: true` never returns a nonzero code.
- SC-003: The full suite passes with the updated retry expectations.

## Assumptions

- The notes name the helper `answered(root, id)`. It takes the already-read state
  mapping instead, because every caller already holds one and the cockpit reads state by
  day directory, not by workspace root. It returns the owner's option or `None`.
- "Answered" means an owner outcome only. A seat outcome is not proof of an owner
  action (a seat can re-route an edited record), so it never clears an owner decision.
- The steward queue and the report already treat a recorded owner outcome as answered;
  they get a regression test, not a code change. The steward keeps skipping seat-decided
  records, since those are not pending owner decisions.
- `pr act` scope decisions always carry the options `change` and `defer`
  (`pr_actions.py` writes them), so `change` means start a fix round and anything else
  means reply to the reviewer.
- The `Outcome:` rewrite replaces the first `Outcome:` line of the record. Records WUWEI
  writes have exactly one. A PR disposition recorded before the owner answers its
  decision must be verified again afterwards, because the record changed; this is the
  existing "disposition decision changed; verify again" contract.
- Stop returning 0 on retry matches Claude Code's `stop_hook_active` contract and the
  existing lifecycle Stop guard. Design 4.1 still holds: the first stop attempt refuses.
  The earlier "retry flags never bypass" rule is replaced by this issue.
- No new config keys.

## Deferred

- The dry run also showed `pr disposition --comment` rejecting free text (it takes a
  comment id) and the `/dev/tty` failure of `decision outcome` without a terminal. Both
  are outside this issue.
