# Feature Specification: CAP and host.seats come from the measured host and a token budget

**Feature Branch**: `528-cap-from-host`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #528: feat(cap): WUWEI parallelises on its own: CAP and host.seats come from the measured host (memory floor, cores) and a token budget, never from a default of 1 the owner has to raise, and the planner launches up to CAP without being asked.

Owner, 2026-10-05: "I keep having to ask for more in parallel. [...] WUWEI should be smarter
than this and just do it, respecting the host memory capacity and the token budgets." The day
started at cap 1 and host.seats 4; raising them took two config commands with a y prompt each.
Part of the autonomy push (#530): no new refusal under observe or guarded.

## Root cause

- `cli/wuwei/workspace.py:82` ships `"cap": (int, 1, 1)` and `:112` ships
  `host.seats (int, 4, 1)`; `templates/workspace/config.toml:3` writes `cap = 1` and `:62`
  writes `seats = 4` into every new workspace. Nothing measured sets either value.
- `cli/wuwei/commands/plan.py:59` (`plan template`) prints `config['cap']` into the lead JSON,
  the lead copies it, and `cli/wuwei/plan.py:48` and `:319` carry that number into the
  proposal and the day state. The day's CAP is therefore the shipped 1 unless the owner
  edited config first.
- `cli/wuwei/calibrate.py:446-465` (`host`, #474) already derives a cap from free memory, the
  per-seat memory cost (`metrics.seat_cost`) and cores, but only as a config proposal
  (`calibrate.py:494-495`) the owner must promote in a host terminal, and it is bounded by the
  fixed `host.seats`. Once promoted, the number is pinned and never re-derived.
- `cli/wuwei/dispatch.py:253` (`launch_set`) and `cli/wuwei/guards/agent_launch.py:176-179`
  read the day's frozen `cap` and the fixed `config['host']['seats']`; `dispatch.py:507`
  (`opinion`) reads the fixed `host.seats` too. Free memory that frees up during the day never
  raises CAP.
- No token budget exists in config, and the per-seat token usage already recorded on
  `seat.usage` events (`commands/build.py:229-270`, telemetry #466) is never read for
  capacity.

## User Scenarios and Testing

### User Story 1: a fresh workspace runs in parallel without being asked (Priority: P1)

A new workspace on a host with room for four seats proposes CAP 4 with the measurement, and
the planner's first launch set starts four items.

**Independent Test**: the #474 fixture day (`tests/fakes/day.py`) with no `cap` in config,
the host fake at 8 GiB free, `os.cpu_count` pinned to 4, four approved items.

**Acceptance Scenarios**:

1. **Given** a fresh workspace on a host with room for four seats, **When** the plan is
   proposed, **Then** `plan.md` shows `CAP: 4 (host)` with the measurement (free memory in GB,
   GB per seat, cores), and **When** the planner runs `wuwei dispatch next --all` after the
   gate, **Then** four items get `start` and none waits.
2. **Given** that day after approval, **When** `wuwei status --line` runs, **Then** it shows
   `seats 0/4 (host)`.
3. **Given** a host whose free memory fits two seats at the first sweep and four at a later
   sweep, **When** `dispatch next --all` runs each time, **Then** CAP is 2 then 4, the day
   state's `cap` follows, and one `cap.derived` event is written per change (none when
   unchanged).

### User Story 2: a token budget bounds CAP (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `[budget] tokens_per_day` set and a recorded token cost per seat such that the
   day's remaining budget fits two seats, **When** the plan is proposed and the launch set
   runs, **Then** CAP is 2 with `(budget)` in the plan and the status line, and two items
   start.
2. **Given** a budget but no seat has reported token usage yet, **When** CAP is derived,
   **Then** the budget does not bind and the measurement text says the per-seat token cost is
   unmeasured.
3. **Given** a budget whose remaining tokens fit no seat, **When** CAP is derived, **Then**
   CAP is 1 with `(budget)`, never 0 and never a refusal.

### User Story 3: one config key overrides (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the owner sets `cap = 1`, **When** the plan runs, **Then** CAP is 1 with
   `(owner)`, one item starts and a second builder launch is at CAP (the existing seats-area
   guard result, unchanged).
2. **Given** the owner sets `host.seats = 2` and no `cap`, **When** CAP is derived, **Then**
   CAP and the seat ceiling are at most 2.
3. **Given** the owner's `cap` is lower than what the host fits, **When** the plan is
   proposed, **Then** the CAP line names the owner value and what the host fits.

### User Story 4: calibrate measures, never asks (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a workspace without `cap` in config, **When** `wuwei calibrate` runs, **Then**
   the report shows the host profile and the derived CAP, and the config proposal contains no
   `cap` line.
2. **Given** the morning gate card, **When** it is printed, **Then** the `Approve` description
   carries the derived CAP with its measurement, and `Change something` names CAP as the
   override.

### Edge Cases

- Host memory unmeasured (adapter error): CAP falls back to the owner value or 1 and the seat
  ceiling to the owner value or 4, labelled `(unmeasured)` with the reason; the launch guard
  still fails closed on unmeasured memory as today.
- `os.cpu_count()` returns None: treated as unmeasured, as `calibrate.host` does today.
- A day state written before this change has no `cap_bound`: the status line shows the cap
  without a label.
- Seats already running: they count toward the fit (running seats plus the seats that fit in
  the free memory above the floor), so CAP does not shrink just because running seats use
  memory.

## Requirements

### Functional Requirements

- **FR-001**: `cap` and `host.seats` default to 0, meaning derived; any positive value is the
  owner's override. The workspace template writes `cap = 0` and `seats = 0` with a comment
  saying so.
- **FR-002**: One function derives capacity: the seats that fit are the running seats plus
  `(free MiB - host.free_memory_mb) // seat MiB` (seat MiB measured by `metrics.seat_cost`,
  else the 1024 MiB first guess), at most one per core; `host.seats` derived is that fit (at
  least 1); CAP is the owner `cap` or the fit within `host.seats`; then the token budget bounds
  CAP. It returns CAP, the seat ceiling, the bound (`host`, `budget`, `owner` or
  `unmeasured`) and a one-line measurement text.
- **FR-003**: `[budget] tokens_per_day` (int, default 0 = no budget). The per-seat token cost
  is the median input plus output tokens of `seat.usage` rows on the latest day that has any;
  used tokens are today's sum. Budget seats are `max(1, remaining // per-seat)`; when lower
  than CAP, CAP becomes that and the bound `budget`.
- **FR-004**: `plan propose` sets the proposal's `cap` from the derivation (the lead's `cap`
  is not used), records the bound and text in the proposal, and writes the line
  `CAP: <n> (<bound>): <measurement>` in `plan.md`. `plan template` prints the derived cap.
- **FR-005**: `plan approve` records `cap` and `cap_bound` in the day state from the proposal.
- **FR-006**: `dispatch next --all` re-derives capacity at every call, uses the derived CAP
  for planned items and the derived ceiling for launches, and when CAP or bound differs from
  the day state writes both with one `cap.derived` event. The launch set output carries
  `bound` and the measurement text.
- **FR-007**: The agent launch guard and `dispatch opinion` compare against the derived CAP
  and seat ceiling at launch time. Their refusal texts and the posture handling of the
  `seats` area are unchanged.
- **FR-008**: `status --line` shows `seats <running>/<cap> (<bound>)`, keeping the goal split
  inside the parentheses after the bound.
- **FR-009**: `calibrate` no longer proposes `cap` into config; its report keeps the host
  profile and shows the derived CAP and bound.
- **FR-010**: The gate widget's `Approve` description carries the CAP measurement text;
  `Change something` names CAP as the override, recorded as config `cap`.
- **FR-011**: `cap.derived` is a reserved event kind (producer `wuwei dispatch next --all`)
  and a quiet signal; `cap_bound` is a reserved day-state key.
- **FR-012**: The plan skill, lead charter, configuration and concepts pages and design 5.3
  say CAP and `host.seats` are derived, name the override keys and `[budget]
  tokens_per_day`, and drop "the default cap of one".

### Key Entities

- **Capacity**: `{cap, seats, bound, text}` plus the host profile keys `calibrate.host`
  already returns (`cores`, `free_mib`, `seat_mib`, `seat_source`).
- **Day state**: `cap` (existing), `cap_bound` (new string, default empty).
- **Config**: `cap` and `host.seats` (0 = derived), `budget.tokens_per_day` (0 = none).

## Success Criteria

- **SC-001**: A fresh workspace with room for four seats starts four items in its first
  launch set with no owner config step.
- **SC-002**: With a budget fitting two seats, two items start and the plan and status line
  say `(budget)`.
- **SC-003**: With `cap = 1` set by the owner, one builder runs.
- **SC-004**: No new refusal under observe or guarded; the full suite passes.

## Assumptions

- Derivation is live where capacity is enforced (launch set, launch guard, opinion) and at
  plan propose, so SessionStart adds no separate derivation or write; the SessionStart
  context and the status line read the snapshot the last sweep recorded. Init writes the
  derived default (`0`) instead of a number. Overturn if a reading between sweeps proves
  misleading.
- A positive `cap` or `host.seats` already in an existing workspace's config is an owner value
  and stays (init --upgrade never changes an owner value, #357); the plan line shows what the
  host fits next to it, so the owner can set `cap = 0` to derive. A migration of the old
  template lines is not built.
- The token budget bounds CAP (builders) only, not the gate seats in `host.seats`.
- One `seat.usage` row is one seat launch for the per-seat token cost (a builder iteration is
  a launch or continue). Overturn if multi-iteration seats skew it.
- A budget that fits no seat leaves CAP at 1: the day state requires CAP of 1 or more, and the
  budget governor (design 15.8, M5) owns stopping launches at 100 percent.
- The owner's `cap` is bounded by the budget but not by the host (the memory floor check in
  the launch guard still applies).
- The gate's `Change something` for CAP records config `cap` (one key), through the config
  record path #529 builds; until #529 lands, `config set` asks as today.
- `tests/test_invariants.py` does not exist on this base, so no invariant row is added here;
  #530 part E adds the #528 row.
- "Wait for budget" in the orchestrator notes is a pipeline scheduling note, not a product
  behaviour.

## Deferred

- Migrating `cap = 1` and `seats = 4` written by the old template in existing workspaces.
- The budget governor's 80 and 100 percent behaviour (design 15.8, M5).
