# Feature Specification: Skip fast checks for an empty item diff

**Feature Branch**: `865-zero-diff-checks`  
**Created**: 2026-10-14  
**Status**: Ready  
**Input**: Issue #865

## User Scenarios & Testing

### User Story 1 - Check a clean item with no diff (Priority: P1)

A builder finishes a read-only item in a fresh worktree without installing its linter. The check step identifies that there are no changed files and records the configured fast checks as `not applicable: no diff` without invoking the linter.

**Independent Test**: Run `build check` for a clean worktree with an empty diff and an unavailable configured linter. Inspect the check result and build event.

**Acceptance Scenarios**:

1. **Given** a clean item worktree with an empty diff and a missing linter, **when** `build check` runs, **then** it never parks on that missing linter.
2. **Given** a clean item worktree with an empty diff, **when** `build check` runs, **then** fast checks are skipped and recorded as `not applicable: no diff`.

### User Story 2 - Check an item that has changes (Priority: P2)

A builder with a real diff still gets the configured fast checks and their existing failure handling.

**Independent Test**: Run `build check` with a changed file and verify the configured check runs.

**Acceptance Scenarios**:

1. **Given** a nonempty diff, **when** `build check` runs, **then** configured fast checks still run.
2. **Given** an uncommitted change, **when** `build check` runs, **then** it is not classified as no diff.

### Edge Cases

- An unavailable or malformed diff is unmeasured and stops the command with a reason.
- A diff with zero net lines but a changed file is still a nonempty diff.
- The existing no-change build rule may still refuse a code-producing item after its fast checks are skipped.

## Requirements

### Functional Requirements

- **FR-001**: `build check` MUST determine whether the item's diff and worktree status are both empty before invoking configured fast checks.
- **FR-002**: A clean empty-diff item MUST skip configured fast checks and record the exact reason `not applicable: no diff` in its build result.
- **FR-003**: A changed or dirty item MUST continue through configured fast checks.
- **FR-004**: A diff that cannot be measured MUST exit 2 with a reason and MUST NOT be recorded as clean.
- **FR-005**: The existing no-change build rule for code-producing items MUST remain in force.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All clean empty-diff test cases invoke zero configured fast checks.
- **SC-002**: Zero clean empty-diff test cases park because a linter is missing.
- **SC-003**: Changed and dirty test cases retain the existing check behavior.

## Assumptions

- Empty diff means no changed files between the item head and its configured base, plus no uncommitted or untracked changes.
- Skipping fast checks does not override the existing no-change build rule for code-producing items; this issue changes only the check path.
- For items with a real diff, the existing relative executable fallback and optional `[checks] bootstrap` remain the supported ways to provide check tools. Broadening fallback for commands such as `npm run lint` is deferred because it changes the shared check runner or worktree setup outside this issue's requested scope.

## Deferred

- Support `npm run lint` when its script requires a binary available only in the main checkout. The current fallback covers a command whose first word is under `node_modules/.bin/`.
