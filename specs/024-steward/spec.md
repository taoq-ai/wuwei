# Feature Specification: Steward seat and process metrics

**Feature Branch**: `024-steward`
**Created**: 2026-09-29
**Status**: Draft
**Input**: GitHub issue #24 and amendments #75, #84, #110.

## User Scenarios & Testing

### User Story 1: Measure the day (Priority: P1)

The planner and steward can inspect process metrics derived from recorded day state, events and traces. Missing sources are unmeasured and unreadable sources fail with exit 2.

**Acceptance Scenarios**:
1. Given three recorded fix transitions for an item, metrics reports three rounds for that item.
2. Given recorded handbacks, phase transitions, verdict rejections, decisions, usage, and trace calls, metrics reports their named counts and durations without external calls.
3. Given a missing source, its dependent metrics say unmeasured; given an unreadable source, the command exits 2 with a reason.

### User Story 2: Steward steering (Priority: P1)

A fresh steward seat reviews the day at each sweep, close and configured trace call interval. It records evidence-based steering and pre-triages decisions without dispatching work or changing item state.

**Acceptance Scenarios**:
1. Given an item on its third fix round, a steering note is written and the planner's next dispatch is refused until the dedicated acknowledgement command records that note.
2. Given pending owner decisions, the steward's queue cites the decision ids and recommendations.
3. Given a day with no steward run, the next plan contains a finding.

## Requirements

- FR-001: `wuwei metrics` reads recorded events, traces, and state only. It measures fix rounds per item, handbacks per PR, phase time, verdict-lint rejections, decisions per day and by reversibility, unplanned work share, size calibration, seat decisions reversed by owner, build iterations, stuck parks, and reported cost per item, role and day.
- FR-002: The steward uses the existing runtime port as a fresh seat at sweep and close. Trace call threshold defaults to 50 and is configurable.
- FR-003: Steward notes and planner acknowledgements are dedicated producers, reserved against generic state and event writes. Dispatch refuses while a note is pending.
- FR-004: The steward proposes charter and note changes through the existing proposal path; only promote lands them. It never dispatches or changes item state.
- FR-005: Outward steward text follows the owner voice profile for its audience.

## Assumptions

- A fix round is a recorded transition into `fix`; legacy days without a transition history are unmeasured.
- A recorded reply acknowledgement to PR feedback is the v1 handback proxy. A day without the events stream is unmeasured.
- The existing runtime adapter may return a host dispatch instruction. That instruction is a launched fresh seat, while its completed output is recorded through the dedicated steward command.
- The planner acknowledges a note by its id after reading it. The command records acknowledgement but cannot prove comprehension.

## Deferred

Outcome metrics against the owner baseline belong to issue #80. The owner-reversal metric remains unmeasured until a verified owner reversal producer exists; a seat-writable decision file cannot prove an owner action. Exact PR review-cycle handbacks need a dedicated event producer. Remote control plane enforcement and retrospective voice calibration remain with their dedicated issues.
