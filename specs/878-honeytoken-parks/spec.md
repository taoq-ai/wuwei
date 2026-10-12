# Feature Specification: a seat's honeytoken read parks its item and holds the close

**Feature Branch**: `878-honeytoken-parks`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #878: "fix(security): a seat's honeytoken read parks its item and holds the close"

## Root cause

- `cli/wuwei/security.py:108-109` (`record`): a honeytoken read is appended as
  `scanner.finding` with `tier`, `source` and `rule` only. It carries no `risk_level` and no
  `session_id`, and nothing parks.
- `cli/wuwei/scanner.py:137-147` (`_trace_response`) is the only place a `scanner.finding`
  parks a seat's items, and it runs only on ZIRAN chains from `trace_sweep`.
- `cli/wuwei/closing.py:223` (`scanner_hold`) skips every `scanner.finding` whose
  `risk_level` is not `critical`, so the honeytoken finding never holds the close.
- `cli/wuwei/guards/traces.py:120-122` (`check`) records the finding before `_record` binds the
  session to its seat, so a seat check at record time misses a seat whose first tool call is
  the read.

## User Scenarios & Testing

### User Story 1 - A seat that reads the honeytoken parks and holds the close (Priority: P1)

A builder seat reads the planted honeytoken file. Its item parks with a reason naming
`security.honeytoken`, the owner sees the resume card, and `bin/wuwei close` stays held until
the owner answers its Owner step card.

**Independent Test**: the PostToolUse recorder gets a honeytoken read from a seat session; the
item is parked, a critical `scanner.finding` names the rule, and `closing.scanner_hold` returns 1.

**Acceptance Scenarios**:

1. **Given** a seat whose session is already bound, **When** that session reads the honeytoken
   path, **Then** the item is `parked` with reason `security.honeytoken read` and the close is held.
2. **Given** a seat whose session is bound by this same tool call (first call), **When** it reads
   the honeytoken, **Then** the same happens.

### User Story 2 - A non-seat session keeps its current behaviour (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a session that is no item seat, **When** it reads the honeytoken, **Then** it writes
   `security.honeytoken` and a `scanner.finding` page as today, parks nothing and does not hold
   the close.

### Edge Cases

- An adhoc seat keeps its launcher's rule (#676), so it counts as a non-seat, as for ZIRAN chains.
- A second read by the same seat appends another critical finding; parking is idempotent and
  each finding is its own Owner step card, as for chains.

## Requirements

- **FR-001**: A honeytoken read by an item seat's session appends a `scanner.finding` with
  `risk_level: critical`, the `session_id`, chain `['security.honeytoken']` and reason
  `security.honeytoken read`, and parks that seat's items through the same park update as a
  critical chain.
- **FR-002**: The seat check runs after the recorder binds the session to its seat.
- **FR-003**: Sessions that are not item seats keep the current events and park nothing.
- **FR-004**: `closing.scanner_hold` is unchanged; the critical finding holds the close.

## Success Criteria

- **SC-001**: The acceptance scenarios pass as tests in `tests/test_canary.py`.
- **SC-002**: Existing canary, traces, scanner and close tests stay green.

## Assumptions

- "Current note behaviour" for a non-seat session means the `security.honeytoken` and
  plain `scanner.finding` pages it gets today; it does not gain a `traces.noted` row.
- A seat's read keeps the plain `scanner.finding` from `security.record` as well as the
  critical one; doctor shows one row for each. Removing the plain one would move the
  non-seat event behind the span write.
- The canary does not have this gap: it is a `page` and an outward refusal by design (7.1),
  never a scanner finding, and its presence in fetched content means an injection reached
  the seat, not that the seat did something it should not. Unchanged.
- The card text "A critical tool sequence ran today: security.honeytoken." is clear enough;
  `scanner_hold` stays as it is.

## Deferred

- From the #870 review: a bare `Read(credential) -> Bash(curl ...)` with no later write is no
  critical ZIRAN chain and does not park; only canary or honeytoken values in the command
  text stop Bash egress. Out of scope here.
