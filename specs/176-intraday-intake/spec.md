# Feature Specification: Intraday intake and autostart

**Feature Branch**: `176-intraday-intake`
**Created**: 2026-09-29
**Status**: Draft

## User Scenarios & Testing

### User Story 1 - Admit safe intraday work (Priority: P1)

Given `autostart = goal`, a free seat and a goal-linked SLICE candidate, discovery admits the item under CAP and makes it available to the build loop.

### User Story 2 - Route work requiring a decision (Priority: P1)

Given `autostart = strict` and a FULL candidate, discovery queues a decision and starts nothing. Risk flags, never-auto paths and over-budget items also go to the owner. In `off` mode, candidates wait for the next morning.

### User Story 3 - Add a discovered item explicitly (Priority: P2)

After the morning gate, `wuwei plan add <item>` applies the same policy and plan lint to a discovered candidate.

### Edge Cases

- A duplicate candidate is not admitted twice.
- Incomplete risk, path, score or budget evidence cannot trigger autostart.
- Discovery failures report an unmeasured result with a reason.

## Requirements

- **FR-001**: Each sweep and qualifying seat-free event processes discovery candidates.
- **FR-002**: Candidate admission validates plan evidence, goal, track, risk flags, paths and capacity.
- **FR-003**: `goal` mode may autostart confirmed-goal SLICE work under CAP and budget.
- **FR-004**: `strict` mode routes FULL work to the owner decision batch without starting it.
- **FR-005**: `off` mode carries candidates to the next morning for owner review.
- **FR-006**: Admitted work enters the existing build path.
- **FR-007**: Candidate and decision records trusted by policy have dedicated writers.

## Success Criteria

- A safe SLICE candidate is admitted after the gate with a free seat.
- A FULL candidate under strict policy creates a pending owner decision and no build launch.
- Existing and new behavior tests pass without external tools or network.

## Assumptions

- Intraday budget uses the configured rank size component (`job_size` for WSJF, `effort` for RICE) for both morning and added items. An item without a saved size cannot autostart.
- A candidate needs complete plan evidence before admission. Partial adapter results remain proposals for the owner.
- The existing build loop requires a logged builder brief and worktree. Admission can request build dispatch, but launch waits until those inputs exist.
