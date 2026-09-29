# Feature Specification: Step-wise build loop

**Feature Branch**: `161-build-next`
**Created**: 2026-09-29
**Status**: Approved for implementation
**Input**: Issue #161, step-wise build loop for Claude Code subagent seats.

## User Scenarios & Testing

### User Story 1 - Build in the planner session (Priority: P1)

The planner launches and resumes Claude builders without waiting inside the CLI.

**Independent Test**: Drive recorded Agent and SubagentStop payloads and inspect each action.

**Acceptance Scenarios**:

1. Given a Claude item with a logged brief, build next returns launch with the shared dispatch prompt.
2. Given a stopped builder with measured failing fast checks, the next action is continue with feedback for that same seat.
3. Given repeated identical signatures, the item parks at the stuck threshold or maximum iteration budget, whichever is first, with a valid D-<n> decision.
4. Given no changed state, repeated next calls return identical actions without repeating usage or decisions.
5. Given no measured check after the seat stops, the next action is check; measured success yields done.
6. Given the old blocking Claude command, it exits 2 and names build next.

### User Story 2 - Preserve Codex builds (Priority: P1)

Codex executes the same actions using its polling adapter.

**Independent Test**: Existing build tests pass through the shared next-action function.

**Acceptance Scenarios**:

1. Given Codex, failures resume the job, success completes it, and stuck or exhausted builds park.
2. Missing tools, invalid usage and unmeasured checks exit 2 with a reason.

### User Story 3 - Fit parallel gates (Priority: P2)

The default host ceiling accommodates the build cap plus three gates.

**Independent Test**: Register one builder and three gate seats using default configuration.

**Acceptance Scenarios**:

1. Default host.seats is four, matching default cap one plus three.
2. A ceiling refusal names host.seats. CAP restricts builders only.

### Edge Cases

Missing or changed briefs, unmatched stop payloads, duplicate hooks, early checks,
resuming the wrong agent, stale check evidence, malformed adapter responses, and day rollover
must not advance a build with invented evidence. Unrelated hooks remain out of scope.

## Requirements

- FR-001: Return exactly one JSON action: launch, continue, check, park or done.
- FR-002: Hooks own Claude seat identity and results; generic state/event writes cannot forge them.
- FR-003: Preserve fast-check backpressure, signatures, iteration limits and seat.usage accounting.
- FR-004: Resume the original builder and enforce the existing launch guards.
- FR-005: Keep Codex execution behind adapters and use the same action selection.
- FR-006: Document the dated design amendment, planner execution and host default.

### Key Entities

- Build: item, brief, worktree, runtime, iteration, result, checks and next action.
- Seat: existing reservation plus runtime agent identity for continuation.
- Park decision: numbered, validated decision record scoped to the item.

## Success Criteria

- All five actions are reproducible with offline tests.
- No Claude seat polling occurs in the CLI.
- Four seats fit by default, including three concurrent gates.
- Existing build acceptance and the full test suite pass.

## Assumptions

- The existing stuck_after threshold remains effective even when below max_iterations.
- The latest logged builder brief selects a new build; next accepts optional explicit brief and worktree for Codex compatibility.
- The planner executes a check action via a dedicated build check command that measures results itself.
- A stopped seat's already recorded checks may be reused only if measured during that iteration at the current HEAD, with a clean tree at measurement and stop.
- Stops require a fresh assistant completion in the transcript and the recorded agent identity; replayed stops cannot free a resumed seat.
- Calling next while a seat runs fails closed with exit 2; the planner calls it after the Agent returns.
- Default cap is one, so the schema and template use four host seats; custom caps require a corresponding host.seats setting.

## Deferred

No external dependencies or additional issue scope are required.
