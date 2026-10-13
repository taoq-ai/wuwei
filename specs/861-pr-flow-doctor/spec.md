# Feature Specification: PR flow doctor completion

**Feature Branch**: `941-ruling-lint` | **Created**: 2026-10-13 | **Status**: Ready

**Input**: Issue #861 and review follow-up, a doctor command in a compound Bash call reports ok but `next` repeats the step.

## User Scenarios & Testing

### User Story 1 - Complete the PR flow check in any command form (Priority: P1)

**Independent Test**: On a started day, run `wuwei doctor --section pr-flow` inside a compound Bash command; `next` advances to the lead step.

**Acceptance Scenarios**:

1. Given a due PR flow check, when doctor runs in a compound command, then it records completion and the next row advances.
2. Given a standalone doctor run, when `next` runs again, then it advances.
3. Given a due PR flow check, when `next` returns the row, then its text still says to run the command on its own.

## Requirements

- **FR-001**: The process that diagnoses the PR flow section records completion on a started day.
- **FR-002**: The existing standalone completion path remains functional.
- **FR-003**: The PR flow row keeps its standalone guidance.

## Success Criteria

- **SC-001**: A compound doctor call followed by `next` advances without repeating the PR flow row.

## Assumptions

- A check counts as done once doctor diagnoses the PR flow section, regardless of whether its result is ok or a finding, matching the prior Bash-span behavior.
- A duplicate pass is harmless because `next` collects completed rows as a set.
- The owner-only design spec remains unchanged.
