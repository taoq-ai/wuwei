# Feature Specification: Seat launch contract

**Feature Branch**: `160-launch-contract`
**Created**: 2026-09-29
**Status**: Ready
**Input**: Issue #160: seat launch prompts carry the brief reference the launch guard requires.

## User Scenarios & Testing

### User Story 1 - Launch and continue a briefed seat (Priority: P1)

The planner uses runtime instructions unchanged to launch any briefed Claude role.

**Why this priority**: The documented launch path currently produces a refused prompt.
**Independent Test**: Dispatch a builder with a logged brief, feed the returned prompt to the Agent guard from the workspace, and inspect the seat registration.

**Acceptance Scenarios**:

1. **Given** a valid logged builder brief and measured launch prerequisites, **When** the planner dispatches it through the Claude runtime and submits the returned prompt as an Agent PreToolUse payload, **Then** the guard exits 0 and registers that seat.
2. **Given** a Claude job handle, **When** continuation feedback is supplied, **Then** the returned prompt retains the exact first-line brief reference and the feedback, including on repeated continuations.
3. **Given** a relevant prompt without the brief line, **When** the guard checks it, **Then** it refuses with a message naming `WUWEI brief: <relative brief path>` as the required first line.

### User Story 2 - Launch the closing steward (Priority: P1)

The planner launches the steward directly from the closing command's output.

**Why this priority**: Closing the day must not require manually repairing launch instructions.
**Independent Test**: Run `wuwei steward run --trigger close`, submit its returned launch prompt to the guard and inspect the steward reservation.

**Acceptance Scenarios**:

1. **Given** a workspace ready for a steward, **When** the planner runs the closing steward command and submits its launch prompt to the same guard, **Then** the guard exits 0 and registers the steward.

### Edge Cases

- A nested or absent marker is refused; absolute paths and traversal remain invalid.
- Brief paths are relative to the workspace, including when the worktree differs from it.
- Invalid continuation handles and unavailable brief files fail closed with a reason.
- Continuation does not authorize reusing a consumed brief for a fresh Agent launch.
- Calls outside a workspace and unrelated agent types retain existing guard scope.

## Requirements

### Functional Requirements

- **FR-001**: Every Claude dispatch and continuation prompt, including steward output, starts with `WUWEI brief: <relative brief path>`.
- **FR-002**: One core prompt formatter owns this contract for all roles, sharing the brief marker with the guard and transcript reader.
- **FR-003**: Agent type remains `wuwei:<role>` and the brief path is relative to the workspace root used by the guard.
- **FR-004**: Existing brief, role, evidence, capacity, scope and reuse checks remain enforced.
- **FR-005**: Concepts and planning skill document the first line, workspace path base and agent type. Launching skills and charters direct callers to generated instructions.
- **FR-006**: Missing-marker refusal names the required first line.

### Key Entities

- Logged brief: existing path, role, item and evidence used to authorize a seat.
- Claude job handle: launch prompt, agent type, brief path, worktree and write permission, retained for continuation.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Both documented fresh-launch scenarios register exactly one intended seat without editing the returned prompt.
- **SC-002**: Continued prompts preserve their brief reference and newest feedback.
- **SC-003**: Malformed or missing brief references remain refused with actionable guidance.

## Assumptions

- Existing dispatch syntax is `<role> <brief> <worktree>`; the item is already bound by the logged brief, so no new positional item argument is added.
- The steward continues to use the configured runtime adapter, reaching the shared formatter through Claude dispatch.
- Continuation targets the same seat. A consumed brief still cannot register a second seat.
- Dependencies #21, #24 and #126 already supply brief creation, launch checks and runtime routing.

## Deferred

None. Runtime scheduling, seat resume mechanics and unrelated launch policy changes are outside this fix.
