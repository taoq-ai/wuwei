# Feature Specification: PR ownership loop

**Feature Branch**: `120-pr-ownership`
**Created**: 2026-09-29
**Status**: Ready for implementation
**Input**: GitHub issue #120 and binding orchestrator notes.

## User Scenarios & Testing

### US1: Fresh state and dispatch (P1)

The shepherd needs one measured state and required action for every owned PR.
Independent test: replay code-host evidence through the command, without external tools.

1. Given a PR not mergeable against its base, state is `conflicted`, with rebase,
   resolve, fast checks and push dispatch steps in the item's worktree.
2. Given a new review comment after our last reply, state is `threads_unanswered`
   until answered, using the existing obligations evaluator.
3. Given an API error body, that PR returns exit 2 and a reason; other PRs remain visible.
4. CI failures, outstanding change requests, overdue review, current approvals and
   merged evidence select their corresponding actions; no actions execute here.

### US2: Persistent action deadlines and turn-end anchor (P1)

The planner cannot forget an overdue PR across turns or watch restarts.
Independent test: advance the shared clock over a recorded conflict deadline.

1. After the action deadline, Stop refuses naming the PR, state and required action.
2. A verified owner parking decision exempts the PR; a seat-written decision does not.
3. Repeated polling and head/comment churn do not reset an unresolved action deadline.
4. Resolved actions clear; a later recurrence starts a new deadline.
5. Overdue actions emit one nudge, then one page at twice the action interval.
6. Outside WUWEI scope and on non-planner turns Stop remains inert.

### US3: Producer-only trust (P1)

Seats cannot forge deadlines, signals or parking evidence.
Independent test: generic state/event writes and native outbound calls are refused.

1. Generic writers refuse action state and event kinds.
2. An existing body file containing a parking or carry marker is refused when passed
   to a native code-host outbound command, including without security tokens configured.
3. Unrelated shell commands and calls outside a WUWEI workspace are unaffected.

### Edge cases

Unknown mergeability, malformed evidence and missing tools are unmeasured, never clean.
Closed but unmerged PRs require a decision. An empty owned set needs today's state evidence.
Parked records retain the existing external owner-comment verification on every check.

## Requirements

- FR-001: Use the append-only union of raised and claimed PRs; optional references filter it.
- FR-002: Read code_host for state on every invocation, with exit 0 clean, 1 actionable,
  2 unmeasured, including per-PR exits in structured output.
- FR-003: Dispatch data specifies fix rounds, thread triage branches and outward tiers,
  owner decisions, review request then channel post, or `wuwei merge` with decision fallback.
- FR-004: Persist action timing only through the dedicated producer and shared locked writer.
- FR-005: Reuse watch polling/wake, obligations, Stop scope, disposition verification and signals.
- FR-006: Document and validate positive integer `pr.action_minutes` and `pr.review_window`.

### Key entities

Owned PR, fresh evidence, dispatch, action episode, verified disposition and overdue signal.

## Success Criteria

All four issue acceptance scenarios pass through fake ports. Deadlines survive repeat reads
and restarts; forged parking and generic writes fail. The full test suite passes offline.

## Assumptions

- `pr.review_window` is minutes, default 120. Waiting without an actionable finding uses
  `waiting`, with no action deadline; it is not prematurely labeled review_stale.
- Closed, unmerged PRs use `closed` and require an owner decision, never report merged.
- Precedence: merged, closed, conflicted, ci_red, changes_requested, threads_unanswered,
  approved, review_stale, waiting. Approval requires a non-author human approval at the head;
  actual merge eligibility remains exclusively the merge policy's responsibility.
- Review waiting starts when first measured and restarts on a head change. Ordinary comment
  updates do not postpone it. Action intervals start at first observation of an actionable
  state and reset only on a measured state transition. Failures preserve prior deadlines.
- Thread intent is returned as conditional dispatch data; no heuristic guesses about intent.
- Parking and carry retain #16's verified owner-comment protocol. Carry only waives day close.

## Deferred

#23 executes rebase/fix/reply/review/merge dispatch and thread intent triage. Cockpit rendering
and carry-forward scheduling remain with their respective features. This issue emits #92
signals; existing delivery surfaces handle them. No new external execution adapters are needed.
