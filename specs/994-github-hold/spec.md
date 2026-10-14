# Feature Specification: Shared GitHub hold

**Feature Branch**: `994-github-hold`  
**Created**: 2026-10-14  
**Status**: In progress

## User Scenarios & Testing

### User Story 1 - Share a refusal hold (Priority: P1)

When GitHub refuses a call for a rate limit, every WUWEI process using that workspace stops calling GitHub until the hold expires.

**Acceptance Scenarios**:

1. Given several processes in one workspace, when the first receives a rate-limit refusal, then it records the resource, until time and reason, and the others make no GitHub request during that hold.
2. Given an expired hold, when a process next calls GitHub, then the hold clears and the call proceeds.
3. Given a call outside a WUWEI workspace, when it runs, then no workspace hold is applied.
4. Given unreadable hold state, when a process attempts a GitHub call, then it fails closed with a reason.

### User Story 2 - Reuse cached PR state (Priority: P1)

Seats and shepherds make PR decisions from the shared PR listing. The planner's `next` and `pr wait` refresh that listing no more frequently than `pr.poll_seconds`.

**Acceptance Scenarios**:

1. Given several seats and a recent listing, when they inspect a PR, then they use the listed state and do not poll GitHub for PR state.
2. Given a listing due for refresh, when `next` or `pr wait` runs, then it refreshes at the configured interval.
3. Given a failed refresh, when the hold expires and a read succeeds, then every review comment and thread since the last successful read is visible.

### User Story 3 - Explain a refusal (Priority: P2)

A refusal states how long WUWEI holds and which evidence it acted on when the refused reply and quota endpoint disagree.

**Acceptance Scenario**:

1. Given a refused reply reporting zero remaining and a quota endpoint reporting a full bucket, when WUWEI refuses, then the message says it chose a short hold and names both readings without implying both are true.

## Requirements

- FR-1: A GitHub rate-limit refusal creates one workspace hold with resource, until time and safe reason.
- FR-2: All WUWEI GitHub calls in the workspace consult the hold before invoking GitHub.
- FR-3: Holds expire automatically; corrupt hold state fails closed.
- FR-4: Seats and shepherds consume the cached PR listing for PR state. Only `next` and `pr wait` refresh it at the configured cadence.
- FR-5: A deferred review read must retain the previous last-seen boundary so the next successful read includes all missed comments and threads.
- FR-6: A contradictory refusal explains which hold decision was made.

## Success Criteria

- SC-1: Concurrent calls during a hold result in zero additional GitHub requests.
- SC-2: Eight seats inspecting one unchanged PR result in zero PR-state refresh requests.
- SC-3: A successful read after a hold exposes 100% of newly arrived comments and threads in a recorded test case.

## Assumptions

- A workspace hold applies to all GitHub resources, even when the refusal names one resource, because the account's secondary limit may span endpoints.
- A call during a hold returns exit 2 promptly with the hold reason rather than sleeping inside a seat; `pr wait` handles its own wait.
- The existing full-list review and thread reads preserve missed items; reply acknowledgements remain separate. A skipped shepherd duty clears the activity in the listing at skip time; later activity is due again.
- Explicit `pr act` actions still read full review, thread and check evidence so a new reply in an existing thread cannot be hidden by an unchanged listing row. An action verifies the cached PR head and state against GitHub before changing anything; routine seat reads use the listing.

## Deferred

- None.
