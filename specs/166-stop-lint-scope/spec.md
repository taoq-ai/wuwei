# Feature Specification: Scope stop verdict lint to its seat

**Feature Branch**: `166-stop-lint-scope`
**Created**: 2026-09-29
**Status**: Ready
**Input**: Issue #166, design sections 4.1 and 5.3; depends on #13.

## User Scenarios & Testing

### User Story 1 - Stop with only the seat's verdict checked (Priority: P1)

A sentinel can finish without being refused for another seat's verdict, while still
receiving actionable feedback about its own verdict.

**Why this priority**: Cross-seat refusals prevent valid quality seats from finishing.
**Independent Test**: Stop registered sentinels with mixed verdict files and check exits,
refusal messages and rejection events.

**Acceptance Scenarios**:

1. **Given** a security verdict and a valid quality verdict, **When** the quality seat
   stops, **Then** the verdict check passes without linting the security verdict.
2. **Given** the quality seat's verdict lacks a required row, **When** it stops,
   **Then** the refusal names that file and the missing row.
3. **Given** another quality seat has an invalid verdict, **When** a valid quality seat
   stops, **Then** the other seat's file is left for its own stop.
4. **Given** unreadable verdict or ownership evidence, **When** a relevant seat stops,
   **Then** the check fails closed with a reason.

### Edge Cases

- Runtime agent IDs differ from registered seat IDs; roles can carry plugin prefixes.
- A stop can arrive after midnight or after the seat has already been marked stopped.
- A filename that merely starts with the seat ID belongs to a different seat.
- Unrelated workspaces and non-sentinel stops remain unaffected.
- The existing repeated-stop safeguard remains in effect for measured lint findings.

## Requirements

### Functional Requirements

- **FR-001**: Resolve ownership from the stopping seat's registered ID and role.
- **FR-002**: Lint only its existing verdict file in the day associated with its brief.
- **FR-003**: Include the offending filename and lint reason in stop refusals.
- **FR-004**: Leave other seats' verdicts to their own stops, including same-role seats.
- **FR-005**: Preserve PostToolUse verdict lint and unrelated-workspace pass-through.
- **FR-006**: Return 0 for clean, 1 for lint findings and 2 for unreadable or invalid
  ownership evidence or unreadable owned verdicts.

### Key Entities

- Seat reservation: existing registered ID, role and dated brief reference.
- Verdict: existing gate file assigned by the seat's brief.

## Success Criteria

- Both issue acceptance scenarios pass in automated tests.
- Cross-seat verdicts produce zero rejection events during the stopping seat's lint.
- Every owned-file lint refusal identifies its filename and the violated row.
- Existing write-time lint and seat lifecycle tests continue to pass.

## Assumptions

- The brief's existing `gate-<seat-id>.md` naming convention is authoritative.
- Missing verdict files retain the existing behavior: stop lint checks existing files;
  requiring verdict delivery belongs to gate orchestration.
- Transcript brief binding, including the original day, is reused instead of treating
  the runtime agent ID as the registered seat ID.
- No configuration, state schema, or site documentation change is needed.

## Deferred

None. Verdict delivery enforcement is unchanged.
