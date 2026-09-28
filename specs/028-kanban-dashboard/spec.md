# Feature Specification: Passive kanban dashboard

**Feature Branch**: `028-kanban-dashboard`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: Issue #28 and owner amendment of 2026-09-28.

## User Scenarios & Testing

### User Story 1: Read today's flow (Priority: P1)

A planner opens a day board and sees every item in its current phase, with blocked items grouped separately.

**Independent Test**: Given a fixture workspace, every phase column renders, an unknown phase lands in other, and an escalated item with decision D-3 sits in the blocked lane showing D-3 and its time in phase.

**Acceptance Scenarios**:

1. Given a fixture workspace, when the board renders, then every phase column is present and an unknown phase lands in other.
2. Given an item escalated with decision D-3, when the board renders, then its card sits in the blocked lane showing D-3 and its time in phase.
3. Given items in a build phase, when the board renders, then the column shows its WIP count and whether running build items exceed CAP.
4. Given an item with no activity for more than 15 minutes, when the board renders, then its card is greyed.

### User Story 2: Serve the board (Priority: P1)

A planner runs `wuwei dashboard` and opens the printed loopback URL. The page and board metadata stay in memory; state and events are read live.

**Independent Test**: The command binds to `127.0.0.1` on a free port, prints its URL, and leaves the day directory unchanged. HTTP requests expose only the page, board metadata, state and events to the exact loopback Host header.

**Acceptance Scenarios**:

1. Given a workspace, when running `wuwei dashboard`, then it serves on a free loopback port until interrupted and writes no day files.
2. Given a request for a brief or a directory listing, then the server returns 404.
3. Given a Host header other than `127.0.0.1:<port>`, then the server returns 403.

## Requirements

- FR-001: Show planned, spec, implement, gate, fix, delta, raised and merged columns in that order, plus an other column for unknown phases.
- FR-002: Show parked and escalated items in a blocked lane, outside the phase columns.
- FR-003: Show each card's item, repo, goal id, WSJF or RICE score, time in phase, PR link and blocking decision id when present.
- FR-004: Derive time in phase from the latest transition event for that item; show an unknown duration when no transition exists.
- FR-005: Show WIP per phase and compare running build items with the day's CAP.
- FR-006: Grey cards whose latest item activity is older than 15 minutes; refresh the board by polling day state and events.
- FR-007: The page never changes workspace state. Phase changes remain a CLI operation.
- FR-008: The command serves the page and phase metadata from memory on a free loopback port, prints its URL, and reads state and events live only for allowed paths and the exact loopback Host header.
- FR-009: Operational errors fail closed with a reason and exit 2.

## Key Entities

- Day board: one day of item snapshots, events, CAP and phase ordering.
- Item card: the current item fields and event-derived timing.
- Blocked lane: items whose current phase is parked or escalated.

## Success Criteria

- SC-001: All eight phase columns are present even when empty; unknown phases remain visible in other.
- SC-002: A blocked card shows its decision id and elapsed time from its latest transition.
- SC-003: The command creates no day files; a local viewer refreshes live state and events within one poll interval.
- SC-004: The full repository test suite passes.

## Assumptions

- Card metadata comes from optional item keys `repo`, `goal_id`, `wsjf`, `rice`, `pr_url` and `decision_id`; missing values display as unavailable.
- A transition event has `kind: state.transition`, `payload.item`, and `ts`, matching the existing writer.
- Staleness uses the latest event with `payload.item` for the item, falling back to `updated_at`, then treats a missing timestamp as stale.
- CAP applies to running items in spec, implement and fix; delta is a sentinel check. The phase WIP count includes all cards in that phase.
- Serving is the only mode. The server binds to `127.0.0.1` on a free port and stops when interrupted.

## Deferred

- Event schema or mandatory card metadata changes belong to the state writer or item intake issues. This board reads optional fields without changing the writer schema.
