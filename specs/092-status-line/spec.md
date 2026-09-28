# Feature Specification: Signal classification and status line

**Feature Branch**: `092-status-line`
**Created**: 2026-09-28
**Status**: Ready
**Input**: GitHub issue #92

## User Scenarios & Testing

### User Story 1 - Classify attention (Priority: P1)

The owner sees each event in one urgency tier and one lane.

**Independent Test**: Classify fixture events for all tier triggers.

**Acceptance Scenarios**:

1. Given an escalated item blocking a running seat, when classified, then it is a page in Decisions.
2. Given an unreadable event, when classified, then it is a nudge.
3. Given each page, nudge or silent trigger in design section 5.9, when classified, then its tier and lane match that trigger.

### User Story 2 - Glance at the day (Priority: P1)

The owner sees a single status line or structured status with attention counts, phase counts against CAP, and upcoming people and calendar obligations.

**Independent Test**: Read a fixture day and compare line and JSON output without changing files.

**Acceptance Scenarios**:

1. Given readable day state and events, when status is requested, then both surfaces show the same counts and next due times.
2. Given unreadable state, when line status is requested, then it prints `WUWEI ? unmeasured` and exits 2.
3. Given the benchmark fixture, when line status runs repeatedly, then p95 CPU is below 50 ms.

### User Story 3 - Install guidance (Priority: P2)

The owner receives a Claude Code status line snippet at initialization.

**Independent Test**: Initialize a temporary workspace and inspect printed guidance and files.

**Acceptance Scenarios**:

1. Given a new workspace, when initialized, then the command prints a valid `statusLine` snippet and does not edit the owner's settings.

### Edge Cases

- Unknown or malformed events count as nudges so they cannot hide.
- A missing or invalid day state is unmeasured.
- Missing optional reply and meeting data leaves those fields absent from the line.
- Status counts ongoing escalation from current state: an escalated item is a page while it blocks a running seat, and a nudge otherwise. It clears when the item leaves escalated state.
- Event signals count through the current day boundary. Security findings, base branch failures, dead-man hits, and budget caps remain pages for the day. Other page and nudge events also remain counted for the day until their owners provide trusted resolution producers. A seat-written event cannot clear an earlier signal.
- Every event line is inspected. Routine silent kinds may skip JSON decoding; an unread remainder must be shown as `?`, never silently omitted.

## Requirements

### Functional Requirements

- **FR-001**: Classify events into exactly one of page, nudge, silent and one of Work, Decisions, People.
- **FR-002**: Cover every trigger listed in design section 5.9.
- **FR-003**: Provide one line and JSON status from the same read-only snapshot.
- **FR-004**: Count items by the shared build phase definitions and show CAP.
- **FR-005**: Fail closed with `WUWEI ? unmeasured` and exit 2 when state cannot be read.
- **FR-006**: Print owner-owned status line setup guidance during init without editing owner settings.
- **FR-007**: Derive ongoing escalation from current state and count event signals through the day boundary without seat-written resolution events clearing them.

## Success Criteria

- **SC-001**: Every listed page and nudge trigger passes table tests.
- **SC-002**: Unreadable state yields the required line and exit code.
- **SC-003**: Status line p95 CPU stays below 50 ms under the existing benchmark rule.

## Assumptions

- Event records use `kind` and optional `payload` as the existing event writer does. Classification uses explicit kind names and payload markers for the ambiguous decision and budget cases.
- Optional `reply_obligations` and `meetings` lists in day state hold objects with `due` and `start` ISO timestamps respectively. Their producers belong to later issues.
- A missing day `state.json` is unmeasured for status, even though the generic state reader returns defaults for an absent file.
- Resolution producers and their ownership belong to later issues.

## Deferred

- Cockpit lanes, SwiftBar adapter, phone delivery, reply obligation and calendar producers belong to their separate issues.
