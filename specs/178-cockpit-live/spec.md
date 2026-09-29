# Feature Specification: Live cockpit owner surfaces

**Feature Branch**: `178-cockpit-live`  
**Created**: 2026-09-29  
**Status**: Ready  
**Input**: GitHub issue #178

## User Scenarios & Testing

### User Story 1 - See owned PR actions (Priority: P1)

The owner opens the cockpit and sees each owned PR's measured state, action, wait, and deadline.

**Acceptance Scenarios**:

1. Given two owned PRs, when the cockpit refreshes, then both rows show their state, action, and deadline.
2. Given a PR measurement failure, when the cockpit refreshes, then that row says unmeasured with a reason.

### User Story 2 - Read today's briefing and pending work (Priority: P1)

The owner sees the pack written today, pending decisions, and any available drafts with CLI commands for action.

**Acceptance Scenarios**:

1. Given a briefing pack written today, when the cockpit refreshes, then the briefing lane shows its contents.
2. Given pending decision records, when the cockpit refreshes, then the lane shows their commands.

### User Story 3 - See next commitments (Priority: P1)

The owner sees the next reply due and next meeting in the status line.

**Acceptance Scenarios**:

1. Given a reply obligation due at 15:00, when status is read, then the line shows 15:00.
2. Given a configured calendar with an upcoming meeting, when status is read, then the line shows its start.
3. Given a calendar read failure, when status is read, then the meeting is unmeasured and the line still shows measurable pages, nudges, and phases.

## Edge Cases

- A missing pack remains unmeasured; an unreadable or linked pack fails the cockpit read.
- An unconfigured calendar remains unmeasured.
- Invalid timestamps fail the status read with a reason.

## Requirements

### Functional Requirements

- **FR-001**: The cockpit must present fresh owned PR state, action, and deadline per PR.
- **FR-002**: The cockpit must read the daily pack from the path recorded by its producer.
- **FR-003**: The cockpit must list pending decisions with their CLI commands and show drafts when a draft producer exists.
- **FR-004**: The status line must show the earliest due reply obligation.
- **FR-005**: The status line must show the next upcoming calendar meeting when configured.
- **FR-006**: Unavailable or invalid measurements must be visibly unmeasured.

## Success Criteria

- Two owned PRs appear as separate measured rows on one refresh.
- A pack produced today appears on the next refresh.
- A reply due at 15:00 appears on the next status read.
- No external network or real tool is needed to test these outcomes.

## Assumptions

- Existing `wuwei pr state` is the source of PR action and deadline data.
- `brief_packs.daily.path` is the source of the daily pack location.
- Existing `reply_obligations` rows supply person reply deadlines. Population of these rows is outside this issue.
- Issue #174's draft producer is absent from this branch. The cockpit displays draft records if supplied and otherwise does not invent them.
