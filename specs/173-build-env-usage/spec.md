# Feature Specification: Build environment failures and seat usage

**Feature Branch**: `173-build-env-usage`  
**Created**: 2026-09-29  
**Status**: Ready  
**Input**: GitHub issue 173

## User Scenarios & Testing

### User Story 1 - Stop on environment failure (Priority: P1)

An operator sees a missing test runner or dependency reported as an environment problem on the first failed fast check. The item parks without asking the builder to repair code.

**Independent Test**: Run a build with a missing runner, interpreter, or development dependency and inspect the first check action and parked reason.

**Acceptance Scenarios**:

1. Given pytest is missing, when the first fast check runs, then the item parks with `environment: pytest not found` and no builder feedback.
2. Given a normal failing test, when the first fast check runs, then builder feedback and the existing iteration budget still apply.
3. Given a missing command or interpreter, when a fast check runs, then the item parks with an environment reason on that check.

### User Story 2 - Report measured seat usage (Priority: P1)

An operator can inspect each completed builder seat's reported token use, cost, model, and duration.

**Independent Test**: Complete Codex and Claude seats with and without usage fields, then inspect `seat.usage` events.

**Acceptance Scenarios**:

1. Given a Codex result containing usage, when the seat completes, then `seat.usage` records the supplied values.
2. Given no runtime usage, when the seat completes, then missing usage fields are `unmeasured`.
3. Given a Claude SubagentStop payload with usage, when the seat stops, then `seat.usage` records its available token and duration values.

### User Story 3 - Honor role runtime (Priority: P2)

An approved morning plan selects the runtime for each role, and launches use that runtime.

**Independent Test**: Set a role policy that differs from the workspace default and inspect the selected launch adapter.

**Acceptance Scenarios**:

1. Given a builder role policy selecting Codex and a Claude workspace default, when the builder launches, then Codex is selected.
2. Given a role without an approved policy, when it launches, then the workspace runtime remains the fallback.

### Edge Cases

- An unreadable or malformed check result fails closed with exit 2.
- A code import failure involving application code remains builder feedback.
- Partial usage preserves reported fields and marks only absent fields unmeasured.

## Requirements

### Functional Requirements

- **FR-001**: The fast-check result MUST distinguish environment failures from code failures.
- **FR-002**: The build MUST park on the first environment failure with a reason beginning `environment:` and MUST NOT generate builder feedback for it.
- **FR-003**: The build MUST retain current feedback and iteration behavior for code failures.
- **FR-004**: Each seat usage event MUST include input tokens, output tokens, cost, model, and duration when reported; absent values MUST be `unmeasured`.
- **FR-005**: Runtime selection MUST use the approved per-role seat policy when available and the workspace default otherwise.

## Success Criteria

- **SC-001**: A missing pytest check parks after one failed check with zero feedback actions.
- **SC-002**: Recorded usage matches every reported value in Codex and Claude sample payloads.
- **SC-003**: Runtime selection follows the approved role policy in every tested launch path.

## Assumptions

- A completed seat still consumes its current iteration; an environment check does not trigger another builder iteration.
- `unmeasured` is the literal value for absent usage fields, matching other WUWEI metrics.
- The existing workspace runtime is used when no approved policy exists for a role.

## Deferred

- Historical usage records are not rewritten.
