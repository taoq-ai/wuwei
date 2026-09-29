# Feature Specification: Planner dispatch and receive

**Feature Branch**: `022-planner-dispatch`  
**Created**: 2026-09-29  
**Status**: Draft

## User Scenarios & Testing

### User Story 1 - Pre-PR gates (Priority: P1)

The planner stands down a builder, dispatches arch, quality and security gates in parallel, and records their file verdicts.

**Acceptance Scenarios**:

1. Given a clean item at its gate phase with no live builder, when dispatch is requested, then the three gates are returned together.
2. Given an active builder or an unmeasured worktree, when dispatch is requested, then dispatch is refused with a reason.

### User Story 2 - Bounded fix and delta (Priority: P1)

The planner receives each verdict and decides the next step within one fix round and one delta per gate.

**Acceptance Scenarios**:

1. Given a FIX from quality and PASS from the others, when all three are received, then one fix round runs, only quality gets a delta check, and the item proceeds or escalates.
2. Given a blocking trust-boundary security finding after delta, then the item escalates.
3. Given non-blocking residuals after delta, then the item proceeds with PR review notes.

### User Story 3 - Discovery trigger (Priority: P2)

The planner requests discovery at each sweep and when a build seat frees with a short queue.

**Acceptance Scenarios**:

1. Given a sweep or a seat-free event with a short queue, then the planner requests discovery.

## Edge Cases

- Missing, malformed or unreadable verdicts cannot count as PASS.
- A verdict for the wrong role, round or HEAD is refused.
- A builder and its gates cannot own the same worktree at once.

## Requirements

- **FR-001**: Decide gate dispatch from approved item state and recorded seat status.
- **FR-002**: Receive only linted verdict files at the current item HEAD and record each through a dedicated producer.
- **FR-003**: Start at most one fix round and one delta per failing gate; retain passing gates without rerunning them.
- **FR-004**: Escalate blocking residuals, including trust-boundary security findings; carry non-blocking residuals into PR notes.
- **FR-005**: Signal discovery on sweeps and on a freed build seat with a short queue.

## Success Criteria

- The accepted FIX/PASS scenario reaches fix, delta and proceed or escalate in order.
- All dispatch and receive decisions have three-state exits and a reason when blocked or unmeasured.
- Tests use fakes and do not launch agents.

## Assumptions

- Gate verdicts are recorded after the sentinel stops and use the existing verdict lint format.
- `gate` and `delta` are the existing pre-PR state phases; a fix round is a builder phase.
- Discovery ranking and `autostart` policy are owned by issue #79.

## Deferred

- Ranking, goal matching, and autostart decisions belong to #79.
