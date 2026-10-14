# Feature Specification: Safer defaults and finite duties

**Feature Branch**: `995-defaults-duties`
**Created**: 2026-10-14
**Status**: Ready
**Input**: Issue #995

## User Scenarios & Testing

### User Story 1 - Trust changes reach the gate (Priority: P1)

**Acceptance Scenarios**:

1. Given a changed auth, session, token, permission or guard file or directory, when a standard gate brief is generated, then step zero runs and names the matching path and rule.
2. Given a custom repository trust path, when a changed file matches it, then the gate brief names the match.

### User Story 2 - Terminal PRs stop asking for pings (Priority: P1)

**Acceptance Scenarios**:

1. Given an open PR without a ping, when duties are listed, then a ping is due.
2. Given a merged or closed PR, when duties are listed, then no ping is due.

### User Story 3 - Reply acknowledgements survive days (Priority: P1)

**Acceptance Scenarios**:

1. Given a verified reply yesterday, when the same target and reply are read today, then that target is not owed.
2. Given a changed target, deleted reply, or newer outside comment, when obligations are read, then the relevant reply is owed.

### User Story 4 - Practical memory floor (Priority: P2)

**Acceptance Scenarios**:

1. Given no owner setting, when config is loaded, then the floor is off and does not hold a seat at startup.
2. Given an explicit owner setting of 30 percent, when config is loaded, then that value is retained.

### Edge Cases

- Malformed historical acknowledgements fail closed rather than clear a duty.
- Unmeasured terminal PR state does not clear an open ping duty.

## Requirements

### Functional Requirements

- **FR-001**: Default trust rules MUST cover the five named path families and allow repository customization.
- **FR-002**: A gate brief MUST state the changed path and matching rule.
- **FR-003**: A merged or closed PR MUST have no ping duty.
- **FR-004**: A verified reply acknowledgement MUST apply across days until its target or reply changes; newer outside comments MUST remain owed.
- **FR-005**: The default memory floor MUST allow startup without a percentage hold and an explicit owner value MUST take precedence.

### Key Entities

- **Trust rule**: A repository path pattern for sensitive changes.
- **Reply acknowledgement**: A verified target and owner reply pair for one PR.
- **PR duty**: An action tied to current PR state.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All five trust families trigger step zero in a standard gate brief.
- **SC-002**: Neither merged nor closed PRs produce a ping duty.
- **SC-003**: A valid prior-day acknowledgement prevents repeat requests while changed or new comments remain due.
- **SC-004**: The default has no percentage hold and an explicit 30 percent setting still governs.

## Assumptions

- The main branch's zero default already meets the issue's lowered-default option; no new host measurement study is needed.
- Existing per-repository `trust_paths` remains the customization point.
- Existing verified reply records in day state remain the source of acknowledgement history.

## Clarifications

- No user questions were needed. The issue's acceptance outcomes and the assumptions above resolve the open choices.

## Deferred

- `bin/wuwei` wording in briefs belongs to issue #988.
- The shepherd requested-reviewer check belongs to issue #980.
