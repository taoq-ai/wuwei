# Feature Specification: a seat's end is recorded apart from acceptance of its report

**Feature Branch**: `905-stop-report`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #905: "a seat's completion is recorded separately from acceptance of its
report, read once through brief.stop_text" (independent review, item 5).

## What happened

On the owner's day, finished builds went unrecorded and their seats stayed `running`, holding
seats until the owner stopped them by hand. `wuwei next` then offered only
`wuwei seat stop <name> --unmeasured`, which discards the result.

## Claims checked on main (0.29.1)

1. **Guards read only `last_assistant_message`** (`guards/spec.py` `check_stop`,
   `guards/verdict.py` `check_retro`). Does not hold as a defect: `commands/hook.py`
   `fill_stop_text` (#488) runs `brief.stop_text` once for a WUWEI seat's SubagentStop and writes
   the report into the payload before any guard runs; `seat stop --verdict` builds the payload
   with the message set. `test_hook_fills_message_for_every_guard` and
   `test_background_handback_day` already prove a background handback reaches every stop guard.
   Nothing to change.
2. **A recording error leaves the seat running** (`guards/agent_launch.py` `stop`, the
   `build result could not be recorded` return). Holds. Any error from `build.stopped` (malformed
   usage, a race, an unreadable transcript, a message that differs from the transcript) returns
   exit 2 with the seat and the build still `running`. Malformed usage alone discards a finished
   build.
3. **next's recovery discards the result** (`commands/next.py` stuck-seat launch). Holds. A stuck
   seat is always offered `--unmeasured`, even when its report is readable.

Found while verifying:

4. A late stop from a replaced builder agent whose report is unreadable stops the replacement
   seat as unmeasured: the report read runs before the agent identity check.
5. A second stop of an already stopped non-builder seat (a stop the retro guard sent back for
   repair) writes a second `seat stopped` event.

## User Scenarios & Testing

### User Story 1 - a finished seat is never left running (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a builder stop whose usage is malformed, **When** the hook runs, **Then** the
   result is recorded with usage unmeasured, the seat is stopped and the build waits for checks.
2. **Given** a builder stop whose result cannot be recorded, **When** the hook runs, **Then** the
   seat is stopped unmeasured with the reason, its report is kept in the day directory and the
   message names `wuwei seat stop <name> --verdict`.
3. **Given** a late stop from the replaced agent, or a stop from an agent that is not the bound
   one, **When** the hook runs, **Then** the replacement seat stays `running`.
4. **Given** a seat already stopped, **When** a second stop arrives, **Then** nothing more is
   recorded.

### User Story 2 - recovery records the report first (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a stuck seat whose report is kept or whose transcript ends in a hand-back, **When**
   `wuwei next` runs, **Then** it offers `wuwei seat stop <name> --verdict`; only a seat with no
   readable report is offered `--unmeasured`.
2. **Given** that offer, **When** the owner runs it, **Then** the report is recorded through the
   stop guards (`stop_with_report`) and the build result is recorded once.

## Requirements

- **FR-001**: `build.stopped` treats missing or malformed usage as unmeasured and records the
  result.
- **FR-002**: `agent_launch.stop` checks agent identity before reading the report; an identity
  mismatch (`build.Mismatch`) leaves the seat as it was.
- **FR-003**: any other error recording a running seat's stop stops the seat unmeasured with the
  reason and keeps the report (`brief.keep_report`, path on the seat as `report`, its sha256 as
  `report_sha256`). The kept text is the transcript's last turn, the bound agent's own words,
  never a payload message; an unreadable turn keeps nothing.
- **FR-007**: kept reports and their directory are protected state; `seat stop --verdict` refuses
  a kept report whose sha256 differs from the one on the seat.
- **FR-004**: a stop for a seat already `stopped` records nothing.
- **FR-005**: `wuwei seat stop <name> --verdict` with no file records the seat's kept report, else
  the report its transcript ends with, through `stop_with_report`.
- **FR-006**: `wuwei next` offers `--verdict` for a stuck seat with a readable report before
  `--unmeasured`.

## Success Criteria

- **SC-001**: the new tests in `tests/test_handback.py` pass; existing handback, build and hook
  tests stay green under 3.12 and 3.11.

## Assumptions

- Agent identity means the builder `agent_id` binding (#614): the replaced agent, a missing id or
  an id that differs from the resumed agent. A message that differs from the transcript is a
  report that needs repair, so the bound seat is recorded as ended.
- The kept report lives at `.wuwei/days/<day>/reports/<seat>.md`; the seat records its path, and
  a new launch of the seat clears it, so an older report is never offered.
- A stop for an `unmeasured` seat still records it as stopped (the #473 recovery path).
- The Codex result path (`record_result` from `run_loop`) keeps refusing malformed usage; the
  issue names the stop hook only.
