# Feature Specification: Guard mutation coverage

**Feature Branch**: `018-guard-mutation`
**Created**: 2026-09-29
**Status**: Ready

## User Scenarios & Testing

### User Story 1 - Detect untested guards (Priority: P1)

A maintainer adds a registered guard and CI identifies it until a mutation test covers it.

**Acceptance Scenarios**:

1. Given a new guard without a mutation test, when CI runs, then it fails naming the guard.
2. Given a registered guard with a mutation test, when its check is disabled, then its test fails.

### User Story 2 - Cover bypass forms (Priority: P1)

A maintainer can see every matching bypass form from design section 4.5 in the relevant guard tables.

**Acceptance Scenarios**:

1. Given a wrapper or opaque command listed in section 4.5, when its guard table runs, then it asserts the expected refusal.
2. Given the merge policy, deployment ban, or decision lint, when coverage is enumerated, then each is required by the meta-check.

## Requirements

- **FR-001**: Enumerate registered guards at test time and name every uncovered guard.
- **FR-002**: Disable each covered guard in process and prove its associated assertion fails.
- **FR-003**: Include each listed bypass form in relevant guard tables.
- **FR-004**: Cover merge policy, deployment ban, and decision lint.
- **FR-005**: Keep the default test suite fast and independent of network or real external tools.

## Success Criteria

- **SC-001**: An untested newly registered guard causes a named CI failure.
- **SC-002**: Disabling every covered guard produces a failing assertion.
- **SC-003**: The full pytest suite passes without external services.

## Assumptions

- A guard identity is its module-qualified check function plus hook event and matcher.
- Non-refusal lifecycle and tracing guards may be tested through their observable result or side effect.
- Existing guard tables are extended in place where bypass rows are missing.
