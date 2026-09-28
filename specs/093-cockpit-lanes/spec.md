# Feature Specification: Read-only cockpit lanes

**Feature Branch**: `093-cockpit-lanes`
**Created**: 2026-09-28
**Status**: Ready
**Input**: GitHub issue #93 and binding orchestrator amendment

## User Scenarios & Testing

### User Story 1 - See owner decisions (Priority: P1)

The owner sees pending decision and clarification records, their question, options, and the route for answering in the session or later control plane.

**Independent Test**: Save pending D- and C- records for today and load the cockpit.

**Acceptance Scenarios**:

1. Given a pending one-way-door decision, when the owner opens the cockpit, then Decisions shows its record, options, and owner route; the owner answers in the session, with no cockpit approval write.
2. Given a pending clarification, when the owner opens the cockpit, then Decisions shows its question and options.

### User Story 2 - Glance at team work (Priority: P1)

The owner sees Work by phase, People reply obligations, PR ownership, and attention tiers in one view.

**Independent Test**: Load a fixture day with items, obligations, PR references, and events.

**Acceptance Scenarios**:

1. Given day state, when the cockpit loads, then Work retains its phase board, People lists reply obligations, and signals show page and nudge counts.
2. Given owned PRs, when the cockpit loads, then each has a row for state, last action, waiting on, and deadline. Unavailable PR measurement is labeled unmeasured.

### User Story 3 - Read a briefing (Priority: P2)

The owner can read a produced briefing pack from the cockpit.

**Independent Test**: Save a briefing pack and load the cockpit.

**Acceptance Scenarios**:

1. Given a briefing pack for today, when the cockpit loads, then its text is readable.

### User Story 4 - Refuse browser writes (Priority: P1)

The browser cannot change workspace state through the local server.

**Independent Test**: Send POST requests with missing or supplied tokens and foreign Hosts; compare workspace bytes.

**Acceptance Scenarios**:

1. Given a POST without a session token or with a foreign Host, when it reaches the server, then it is refused and nothing is written.
2. Given any POST with any token, when it reaches the server, then it is refused and nothing is written.

### Edge Cases

- Unreadable or malformed required data appears as unmeasured, never clean.
- Every workspace-sourced field is rendered as text or escaped HTML; unsafe destinations never become links.
- A missing optional producer leaves its lane explicitly unmeasured.

## Requirements

### Functional Requirements

- **FR-001**: Show Work, Decisions, People, and PR lanes plus a briefing pack view.
- **FR-002**: Show pending D- and C- records with questions, options, and decision route.
- **FR-003**: Show one row per owned PR with state, last action, waiting on, and time to deadline, or unmeasured for unavailable PR state.
- **FR-004**: Show reply obligations and shared attention counts.
- **FR-005**: Refuse all POST requests and preserve loopback binding and exact Host checks.
- **FR-006**: Render all workspace text safely.

### Key Entities

- **Decision record**: Today's pending D- or C- record, question, options, and route.
- **PR row**: Owned PR reference and its measured or unmeasured action state.
- **Reply obligation**: Person, reason, and due time when produced.
- **Briefing pack**: Today's generated text when available.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every pending fixture decision and owned PR appears in the correct lane.
- **SC-002**: All tested POST requests write zero bytes to the workspace.
- **SC-003**: Malicious fixture text produces no executable markup in rendered lanes.

## Assumptions

- The binding orchestrator decision supersedes the issue's original approval acceptance and design section 5.9: this cockpit is read-only. A page token is forgeable by a seat that can fetch the page, so there is no POST approval endpoint or local approval record. Owner decisions are answered in the session or later control plane; outbound drafts are sent by the owner at their destination.
- The existing dashboard from issue #28 supplies Work and the HTTP boundary.
- Issue #92 supplies signal classification and status counts.
- `wuwei pr state` and a briefing pack producer are not present on this branch. Their displays report unmeasured until producers exist.
- An optional `reply_obligations` list uses the state shape already consumed by `status --json`.

## Deferred

- Live PR state fields belong to #120. The out-of-process approval control plane belongs to M5. A dedicated briefing producer and outbound draft feed are not present on this branch; their producers remain outside this issue.
