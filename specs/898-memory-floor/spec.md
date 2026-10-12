# Feature Specification: a free-memory percentage floor holds seat launches; CAP counts live seats

**Feature Branch**: `898-memory-floor`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #898: "Seat capacity ignores host free memory for subagent seats; add a
free-memory floor."

## What happened

On the owner's 0.29.0 day the standing rule was to hold launches while free memory is under 40
percent. The planner enforced it by hand with `memory_pressure` before every launch. `next`
printed `cap 8 (owner): config cap; the host fits 8 (subagent runtime, free memory not read)`.
At 41-42 percent free with about 10 seats it would have admitted more; at 64 percent free it
refused at its 8-seat ceiling, and its count included adhoc and finished seats.

## Root cause

- `dispatch.host` (`cli/wuwei/dispatch.py:47-108` on main) reads free memory only when a seat
  runtime launches its own process (`:62-64`); for Claude subagent seats it never reads it
  (`:94-96`, "free memory not read"). The only free-memory check for subagents is the MiB floor
  in the Agent launch hook (`cli/wuwei/guards/agent_launch.py:209-212`), which compares bytes
  against `host.free_memory_mb` and, as a capacity refusal, only logs (#837,
  `cli/wuwei/guards/__init__.py:42`). Nothing reads free memory as a share of the host, and
  `launch_set` (`dispatch.py:805-901`) never holds a launch on memory.
- The seat count is `status == 'running'` over every seat record, computed separately at
  `dispatch.py:817` (launch set), `dispatch.py:1358` (second opinion) and
  `agent_launch.py:267` (the launch hook). It counts adhoc seats (no brief, `agent_launch.py:122`)
  and seats that already handed back but were never stopped (`brief.stuck`, `brief.py:324`).

## User Scenarios & Testing

### User Story 1 - the owner's floor holds new seats (Priority: P1)

**Independent Test**: set `host.min_free_memory_pct = 40`, inject a reading of 38; `next` lists
every seat launch as a wait with `held: free memory 38% < 40%` and a re-check time.

**Acceptance Scenarios**:

1. **Given** the floor 40 and a reading of 38, **When** the launch set is derived, **Then** every
   gate, build and planned start entry waits with that reason and an `until` a minute ahead.
2. **Given** the same, **When** nothing else is due, **Then** `next` returns a background sleep
   and offers the launches again after it.
3. **Given** a reading of 40 or more, **Then** nothing is held.
4. **Given** the floor set and the reading unmeasured, **Then** launches wait with
   `held: free memory percentage unmeasured: <why>; bin/wuwei doctor tests the host adapter`
   and the same timed re-check.
5. **Given** the floor 0 (the default), **Then** the percentage is not read and nothing changes.
6. A merge, a `pr act` run and a `seat stop` are never held; a running seat is never stopped.

### User Story 2 - CAP counts live seats (Priority: P1)

**Given** running seats where one is adhoc and one handed back without a stop, **When** the
launch set, the launch hook or the second opinion counts seats, **Then** only registered seats
that have not handed back count.

### User Story 3 - doctor and upgrade (Priority: P2)

Doctor's memory row names both floors and the current percentage; `init --upgrade` adds
`host.min_free_memory_pct = 0` to an existing config.

### Edge Cases

- A host adapter that cannot read the percentage (`adapters.host = "none"`, an unsupported
  platform): with the floor set, launches wait and say why; doctor shows it unmeasured.
- The MiB floor stays where it is (the launch hook, the process-seat fit); both floors apply.

## Requirements

- **FR-001**: `host.min_free_memory_pct`, integer 0-100, default 0 (off).
- **FR-002**: the host adapter gains `free_percent()`: macOS `memory_pressure` "System-wide memory
  free percentage", Linux `MemAvailable * 100 // MemTotal` from `/proc/meminfo`.
- **FR-003**: `dispatch.host` reads it when the floor is set, for every runtime, and returns
  `held` with the reason when below or unmeasured; its text names the reading and the floor.
- **FR-004**: `launch_set` turns every entry that would launch a seat into a timed wait while
  `held`; entries without a seat launch are untouched.
- **FR-005**: `brief.live(data)` is the one seat count: running, registered on a brief, not
  handed back. The launch set, the launch hook and the second opinion use it.
- **FR-006**: doctor reports the floor and the reading; the template carries the key.

## Assumptions

- The hook does not refuse on the percentage floor: capacity refusals there only log and leave
  the seat unregistered (#837, #889), so `next` is where the floor holds. The hook still reads
  it through `dispatch.host`.
- An unmeasured reading with the floor set holds (fail closed, like the MiB floor) with a timed
  re-check; the owner sets the floor to 0 to stop it.
- The re-check interval is one minute past the reading (next sleeps about two minutes).
- "Finished" seats are the ones `brief.stuck` already reports: a running seat whose transcript
  ends in the hand-back. Stale reservations past `host.reservation_timeout_seconds` still count;
  a long build is still live.
- The launch set keeps its "busy item" check on every running seat, adhoc included, so no build
  starts on an item an unregistered seat is working on.
