# Feature Specification: Fix round threads and gate receipt

**Feature Branch**: `993-fix-round-threads`
**Created**: 2026-10-14
**Status**: Ready
**Input**: Issue #993.

## User Scenarios & Testing

### User Story 1 - Every owed review thread (Priority: P1)

A shepherd's fix request gives one builder every unanswered human and bot review thread on the PR.

**Independent Test**: Measure several owed threads and inspect one fix action.

**Acceptance Scenarios**:

1. Given several owed threads, when the shepherd requests a fix for one, then one fix round carries all of them and asks the builder to fix or reply to each.
2. Given an open fix round, when a later fix request names another thread, then its feedback reaches that round and the output names the destination.

### User Story 2 - Running round feedback (Priority: P1)

Feedback arriving while the builder runs is delivered after the seat stops, without replacing the build.

**Independent Test**: Add feedback to a running build, record its stop, and inspect its next action.

**Acceptance Scenarios**:

1. Given a running fix round, when later feedback arrives, then the next builder continuation contains it.
2. Given an unlaunched fix round, when later feedback arrives, then its launch action contains it.

### User Story 3 - Gate verdict receipt (Priority: P1)

A gate seat's valid verdict is recorded at its stop; a wrong manual round names the expected one.

**Independent Test**: Stop a gate with a valid verdict file, then try manual receive with the wrong round.

**Acceptance Scenarios**:

1. Given a gate seat and valid verdict, when it stops, then the current round's verdict is recorded.
2. Given a delta round, when manual receive specifies initial, then the error names delta as expected.

### Edge Cases

- Repeated fix requests do not create another round.
- A gate stop without a verdict file leaves manual receive available.
- Invalid gate verdicts fail closed with a reason.

## Requirements

### Functional Requirements

- **FR-001**: One fix request MUST include every currently owed PR review thread across human and bot reviewers.
- **FR-002**: Later feedback MUST reach the active fix round or its builder continuation, with the destination stated.
- **FR-003**: A supplementary request MUST NOT replace a running build.
- **FR-004**: A gate stop with a verdict file MUST record the verdict for the current round.
- **FR-005**: A wrong manual receive round MUST name the expected round.

## Success Criteria

- **SC-001**: A multi-reviewer test shows each owed thread in one fix action.
- **SC-002**: Ready and running tests show later feedback delivered without an unfinished-build error.
- **SC-003**: A stop test records a valid gate verdict; wrong-round error names the expected round.

## Assumptions

- The shepherd's fix reason applies to the selected thread. The builder decides whether to fix or reply to other owed threads.
- Feedback arriving during a running seat is delivered after its stop and before fast checks.
- Supplementary feedback is kept on the build record until the launched prompt contains it or a builder continuation receives it. Feedback arriving after a round finishes is carried into the next round. The logged brief file remains immutable for launch validation.
- A stop with no verdict file leaves the existing manual receive workflow available.
- The issue's explicit test-file command takes precedence over the constitution's full-suite wording.

## Clarifications

No questions asked as instructed. The assumptions above resolve delivery and missing-verdict cases.

## Deferred

- A fix round with no code change belongs to #987 and #997. This feature does not edit `_unbuilt`.
