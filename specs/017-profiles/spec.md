# Feature Specification: Strict and standard guard profiles

**Feature Branch**: `017-profiles`
**Created**: 2026-09-28
**Status**: Draft
**Input**: Issue #17, amended by #75; design sections 4.4 and 9.1.

## User Scenarios & Testing

### User Story 1: Warn on outward lint under standard (Priority: P1)

As the owner, I can select standard to receive mechanical outward-text warnings while
allowing otherwise permitted messages. Strict remains the default.

**Independent Test**: Send an allowed acknowledgement exceeding a channel length limit.

**Acceptance Scenarios**:
1. Given standard, when outward lint finds a violation, then the hook allows the call
   and prints a warning containing the reason without exposing the message text.
2. Given strict or no profile setting, when the same violation occurs, then the hook refuses.
3. Given either profile, when lint cannot run, then the hook refuses with a reason.
4. Given standard, when a message requires owner sending, then the hook still refuses.
5. Given standard, when lint is relaxed, then a `hook.warning` event records the
   redacted reason and tool for the owner and steward.

### User Story 2: Preserve every other guard (Priority: P1)

As the owner, changing the lint profile preserves all other safety boundaries.

**Independent Test**: Replay merge, approve and deploy attempts through the hook under standard.

**Acceptance Scenarios**:
1. Given standard, when a merge is not permitted by the existing policy, then it is refused.
2. Given either profile, when approve or deploy is attempted, then it is refused.
3. Given standard and multiple guard results, a warning never suppresses another refusal.
4. Given an unrelated project, when ordinary commands or outward calls run, they remain allowed.

### Edge Cases

Invalid configuration, malformed guard results and unavailable checks fail closed.
Configured repositories and anchored worktrees use their workspace profile. Payload fields
cannot override configuration. Relevant shell bypasses keep the existing guard behavior.

## Requirements

- **FR-001**: Strict is the default and all guard findings block as before.
- **FR-002**: Standard relaxes only completed outward-text lint findings to warnings.
- **FR-003**: Errors remain blocking in both profiles with a reason.
- **FR-004**: Merge policy, approve refusal, deployment ban and approval tiers are unchanged.
- **FR-005**: Warnings preserve the redacted reason, record `hook.warning` with reason
  and tool, and do not create refusal records.
- **FR-006**: Existing scope and relevance boundaries remain unchanged.
- **FR-007**: Direct text-bearing ports retain the same outward policy as hooks.

## Success Criteria

- **SC-001**: Every profile and lint outcome combination has the expected allow/refuse result.
- **SC-002**: All merge, approve and deploy refusal scenarios remain refused under standard.
- **SC-003**: All existing tests pass alongside the new in-process profile tables.

## Assumptions

- A lint failure means findings (exit 1); inability to measure (exit 2) cannot be relaxed.
- The amendment preserves the existing merge policy; standard grants no merge permission.
- Warnings go to stderr with a warning prefix and the existing redacted reason.
- The existing validated config schema supplies strict when profile is omitted.

## Dependencies and Deferred

Depends on the existing hook harness, outward policy, PR and deployment guards from main.
No missing dependency is required. The existing conservative merge refusal remains;
implementation of the fresh-head merge policy belongs to #77 and is outside this issue.
