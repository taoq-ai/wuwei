# Feature Specification: Decision outcomes and two-way digest

**Feature Branch**: `175-decision-outcome`  
**Created**: 2026-09-29  
**Status**: Ready  
**Input**: GitHub issue 175

## User Scenarios & Testing

### User Story 1 - Answer a routed decision (Priority: P1)

The owner chooses a recorded option for a pending decision. The linked blocked item resumes and the report lists the answer.

**Acceptance Scenarios**:

1. Given a pending owner decision, when `decision outcome` records a valid option, then the linked blocked item resumes and the report lists it as answered.
2. Given an invalid option or a decision that is already answered, when an outcome is attempted, then no outcome or item transition is recorded.
3. Given an agent without host owner confirmation, when an outcome is attempted, then it is refused.

### User Story 2 - Count reversals (Priority: P1)

The owner can override a recorded seat decision, with the change visible in outcome metrics.

**Acceptance Scenarios**:

1. Given a seat decision, when the owner chooses a different option, then one `decision.reversed` event is recorded and the metric counts one reversal.
2. Given the same option, when the owner confirms it, then no reversal is recorded and the metric counts zero.

### User Story 3 - Receive a two-way digest (Priority: P1)

The owner gets one batched digest of new two-way seat decisions at most every two hours.

**Acceptance Scenarios**:

1. Given two pending two-way decisions within an hour, when the sweep runs, then exactly one digest is produced.
2. Given another sweep inside two hours, when it runs, then no second digest is produced.
3. Given an outbound message requiring approval, when the digest is produced, then it is retained for owner review.

## Requirements

- **FR-001**: Only a confirmed owner host action may record an outcome.
- **FR-002**: An outcome must name an option in the validated decision record.
- **FR-003**: An owner outcome must be recorded in trusted state and appear in the report.
- **FR-004**: A linked blocked item must resume from its prior phase.
- **FR-005**: A different owner choice after a seat choice must record one reversal and make the metric measured.
- **FR-006**: Sweeps must batch undigested two-way seat choices and enforce a two-hour minimum between digests.
- **FR-007**: Digest delivery must pass through the chat port and outward tiers; approval-tier text must be retained as a draft.

## Success Criteria

- An answered linked item is no longer blocked and its answer appears in the same day's report.
- One override produces one reversal event and a metric value of one; a same-option confirmation produces zero.
- Two new eligible decisions within one hour produce one digest and no repeat within two hours.

## Assumptions

- A host terminal challenge is the existing owner-action boundary. It is local friction, not identity proof against another process with the same user account.
- The decision ID is linked to an item through its existing `decision` field or build park action.
- A two-way digest reports seat decisions already taken, including an item parked by the build loop. "Pending" means not yet included in a digest.
- A chat direct message is the owner digest destination. The current outward tier requires a local draft for review.

## Deferred

- Issue 174 owns the general approval draft and send workflow; this feature keeps a local digest draft until that workflow exists.
