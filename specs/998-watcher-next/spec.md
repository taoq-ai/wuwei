# Feature Specification: Arm the PR stream watcher from next

**Feature Branch**: `998-watcher-next`
**Created**: 2026-10-14
**Status**: Ready
**Input**: Issue #998, pr watch: the loop arms the PR stream watcher itself.

## User Scenarios & Testing

### User Story 1 - Watch PRs during other work (Priority: P1)

As the planner, I receive a runnable background action to watch owned PRs while other work continues.

**Independent Test**: Give an approved day one open owned PR and runnable work, then inspect `next`.

**Acceptance Scenarios**:

1. Given an open WUWEI PR, other ready work and no live watcher, when `next` runs, then its runnable set includes arming `wuwei pr wait` in the background alongside other work.
2. Given an open WUWEI PR, no other work and no live watcher, when `next` runs, then it offers watcher arming as runnable work that the Stop wake sees.

### User Story 2 - Keep one live watcher (Priority: P1)

As the planner, I do not receive a second watcher action while this workspace's recorded PR wait is alive.

**Independent Test**: Record a live PR wait, then inspect `next` with fake process measurements.

**Acceptance Scenarios**:

1. Given a live recorded PR wait for the current workspace and session, when `next` runs, then it omits a second watcher while preserving other work.
2. Given no open WUWEI PR, when `next` runs, then it does not offer watcher arming.

### Edge Cases

- A stale, dead or other-session wait does not count as live ownership; existing housekeeping handles it first.
- Unreadable process measurement is unmeasured, not proof of a live watcher.
- Closed or merged PRs do not require a watcher.

## Requirements

### Functional Requirements

- **FR-001**: `next` must include one runnable background watcher action when an approved day has an open owned PR and no live PR wait for the workspace.
- **FR-002**: Watcher arming must coexist with other work and need no owner card.
- **FR-003**: A live recorded PR wait must suppress a duplicate action.
- **FR-004**: The existing Stop wake must see missing watcher arming as runnable work, without a hook change.
- **FR-005**: Planner instructions must say to arm the returned watcher while seats run.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Tests show exactly one watcher action with open owned PRs and no live watcher, with or without other work.
- **SC-002**: Tests show zero duplicate actions when a watcher is live.
- **SC-003**: The existing Stop wake recognizes missing watcher arming as owed work.

## Assumptions

- An owned PR is one the day raised or claimed. Existing listing and process records establish openness and liveness; a terminal item's PR no longer needs watching.
- The existing `wuwei next --background -- wuwei pr wait` path is the arming command.
- No owner decision or new persistent state is needed.

## Deferred

- Thread handling belongs to #993 and rate-limit handling to #994.
