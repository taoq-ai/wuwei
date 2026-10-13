# Feature Specification: Restore the test function budget

**Feature Branch**: `977-test-budget`  
**Created**: 2026-10-13  
**Status**: Ready  
**Input**: GitHub issue #977

## User Scenarios & Testing

### User Story 1 - CI accepts the suite (Priority: P1)

The test job counts fewer than 2810 test function definitions, leaving room for pending features.

**Independent Test**: Run the workflow's regex over `tests/**/*.py`.

**Acceptance Scenarios**:

1. Given the current 3037 function definitions, when CI counts them, then the count exceeds its 3000 cap.
2. Given the consolidated suite, when CI counts them, then the count is below 2810.

### User Story 2 - Existing coverage remains (Priority: P1)

Each consolidated case runs with its original inputs and assertions. The collected count of each changed test file stays at or above its baseline, except for documented exact duplicates.

**Independent Test**: Compare collected node counts by file before and after and run all test files.

**Acceptance Scenarios**:

1. Given a family of near-duplicate tests, when they become parameter cases, then each old case still runs and checks the same result.
2. Given an exact duplicate on the same input and assertion, when it is deleted, then the deleted pair is listed for review.

### Edge Cases

- Existing parameterized cases must retain all parameter combinations.
- Test identifiers can change, but fixtures and assertions must retain their behavior.

## Requirements

### Functional Requirements

- **FR-001**: Keep the CI regex count below 2810.
- **FR-002**: Preserve each distinct test case's exact input and assertions.
- **FR-003**: Never change runtime code, skip tests, or weaken assertions.
- **FR-004**: Keep collected cases per changed file at or above baseline, except documented exact duplicates.
- **FR-005**: Run the full suite with explicit test file arguments and no network or real GitHub calls.

## Success Criteria

### Measurable Outcomes

- **SC-001**: CI regex reports at most 2809 function definitions.
- **SC-002**: All explicitly named suite files pass.
- **SC-003**: Per-file collected counts meet FR-004.

## Assumptions

- The branch's 3037 definitions and 7859 collected cases are the baseline for this issue.
- The CI regex in `.github/workflows/tests.yml` is the source of truth for the function count.
- A repeated test body with distinct parameter values is not an exact duplicate; its cases stay.
- No design specification wording needs to change for this test-only maintenance issue.
