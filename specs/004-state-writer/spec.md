# Feature Specification: State writer

**Feature Branch**: `004-state-writer`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: Issue #4, single writer for state.json and append-only events.jsonl.

## User Scenarios & Testing

### User Story 1: Persist a day's work safely (Priority: P1)

The planner reads and changes day and item state without losing concurrent updates.

**Independent Test**: Concurrent processes set separate keys and all changes survive.

**Acceptance Scenarios**:
1. Given N concurrent writers, when each sets a distinct key, then state parses, every key survives, and exactly N valid event lines exist.
2. Given no state for today, when reading, then defaults are returned without writing files.
3. Given a valid update, when reading its path, then the JSON value round-trips and one timestamped event records the write.
4. Given malformed input, invalid schema or unreadable state, then the command prints a reason and does not report success.

### User Story 2: Enforce the phase lifecycle (Priority: P1)

The planner advances items only along legal edges and can pause and resume them.

**Independent Test**: Drive an item through all phases and pause/resume each active phase.

**Acceptance Scenarios**:
1. Given implement, when transitioning to done, then exit 1 names gate, parked and escalated as legal next phases, with no write.
2. Given an active phase, when parked or escalated, then only the phase it left is a legal return.
3. Given merged, then no next phase is allowed.
4. Given separate phase and status fields, then changing status never implicitly changes phase.

### User Story 3: Record events (Priority: P2)

Callers append one event with the actual shared clock timestamp.

**Independent Test**: Append payloads containing newlines and caller timestamps; each remains one valid line with a writer timestamp.

### Edge Cases

Missing paths/items, empty path segments, scalar parents, malformed existing JSON,
non-finite numbers, bad enums/types, I/O failures, interrupted replacement, and
short event writes must fail closed. Reads must never reset corrupt state.

## Requirements

- FR-001: Expose state get [path], set <path> <json-value>, transition <item> <phase>, and event <kind> [json-payload].
- FR-002: State replacement is atomic and concurrent read-modify-write operations preserve independent updates.
- FR-003: Every successful state write appends one event; explicit events append without changing state.
- FR-004: Use existing workspace discovery, day directory and clock.
- FR-005: Item schema contains lane, status, phase, flags (trust_surface, boundary_relevant, agent_surface), gates and note. Day schema contains cap, seat_policy, envelope, claimed_prs, raised_prs and gate_verdicts.
- FR-006: Enforce planned -> spec or implement; spec -> implement; implement -> gate; gate -> raised or fix; fix -> delta; delta -> raised or fix; raised -> fix or merged. Active phases allow parked/escalated and resume only to their saved phase. Merged is terminal; done is only a status.
- FR-007: Legal status values are queued, running, blocked and done. Invalid transitions/schema exit 1; malformed arguments, missing paths and operational failures exit 2 with a reason.

### Key Entities

Day state is a JSON object with an items object keyed by item identifier.
Items contain lifecycle metadata. Events contain kind, payload and ts.

## Assumptions

- Paths are dot-separated object keys; no array indexing or escaping. Unknown keys are preserved for future issue-owned fields and independent concurrent updates.
- Missing day state defaults to cap 1, empty policy/envelope/verdict maps, empty PR lists and items. Missing item fields default to lane build, status queued, phase planned, false flags, empty gates and note.
- The first snapshot may initialize items to any legal phase (including terminal phases); later new items must start at planned, and no write may remove an existing item. Existing phase changes, including through set or imported writer functions, enforce the same transition rules.
- Paused items persist resume_phase. It is writer-managed on phase changes; no nested pause transitions. Status remains independently controlled.
- Explicit event kinds starting with state. are reserved for the writer; all event timestamps and appends hold the state lock.
- An event payload is an object nested under payload (omitted or null means empty); caller ts cannot override the event timestamp.
- Atomicity is per state file, not a crash-proof transaction spanning state and event files. Append failures after replacement exit 2 and report the failure; cross-file recovery is deferred.
- A crash between state replacement and event append can leave a state change without an event; retrying the transition can report that state may already be at the target phase.

## Success Criteria

- SC-001: All N independent concurrent updates and exactly N corresponding events survive a successful run.
- SC-002: Every prohibited lifecycle edge is refused without modifying state or appending an event.
- SC-003: All command outcomes follow exits 0, 1 and 2 and successful reads emit valid JSON.

## Deferred

Crash recovery across state and event files, Windows locking, lane-specific workflow gates,
and schema semantics for adapter-owned policy, envelope, PR and verdict contents.
