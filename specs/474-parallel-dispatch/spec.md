# Feature Specification: the day starts in parallel

**Feature Branch**: `474-parallel-dispatch`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #474, "feat(dispatch): the day starts in parallel: CAP from the
calibrated host, seats per goal in the plan and the gate question, every dispatchable item
launched up to CAP in one turn, and an item's gate sentinels run together". Owner,
2026-10-04, first real items on 0.15.0: "the process is too sequential: the number of seats
for each goal after approval, to start with the day."

## Root cause (read on main, 963a839)

The notes name no dry-run workspace for this issue; the causes below are read from the
code on main, and each is pinned by a failing test in tasks.md before it is changed.

1. Nothing proposes a CAP from the host. `cli/wuwei/calibrate.py` profiles repositories
   only (`survey`, lines 577-599); `cli/wuwei/commands/calibrate.py:48-57` never reads the
   host port, the core count or any seat measurement. The host floors exist
   (`host.free_memory_mb`, `host.seats`, `cli/wuwei/workspace.py:105`) and the launch guard
   measures free memory on every launch (`cli/wuwei/guards/agent_launch.py:131`), but the
   measurement is discarded: the `seat launched` event carries only `name` and `item`
   (`agent_launch.py:199-200`), so no seat cost can be derived.
2. The lead starts from 1. `plan template` prints a hard-coded `'cap': 1`
   (`cli/wuwei/commands/plan.py:54`) instead of the configured `cap`, and `cap` defaults
   to 1 (`workspace.py:75`, `templates/workspace/config.toml:3`).
3. The approved CAP is not the CAP the launch guard checks. `plan approve` records the
   gate's `cap` in day state (`cli/wuwei/plan.py:272`), and `next`, `status` and `plan add`
   read that day value (`commands/next.py:100`, `commands/status.py:247`, `plan.py:315`),
   but the launch guard refuses builders against `config['cap']`
   (`agent_launch.py:182-183`). An owner who raises CAP at the gate still gets refused at
   the config value.
4. The plan and the gate question show no seats per goal: plan.md prints `CAP: N`
   (`plan.py:157`) and the gate's Approve description says `CAP N` (`plan.py:183`).
5. Dispatch is one item at a time. `wuwei dispatch next` takes exactly one item
   (`commands/dispatch.py:13-14`); `wuwei next` returns one `dispatch` row for the first
   planned item and points at `wuwei worktree add <item>` (`commands/next.py:100-104`);
   the plan skill's builder loop says to wait for each Agent call to return
   (`skills/wuwei-plan/SKILL.md:36-46`) and never tells the planner to launch several items
   in one message. At CAP, `next` says only "Seats running: ..." (`next.py:105-108`) and
   names neither the waiting item nor the seat that frees first.
6. Gates: `dispatch.next_step` already returns one ready action per logged gate brief and
   waits for every required verdict before a fix or raise (`cli/wuwei/dispatch.py:218-242`),
   and the skill says "Launch those seats in parallel" (`SKILL.md:52`). Missing: the
   explicit instruction that the launches go in one message (the harness runs Agent calls
   in one message concurrently), and a fixture test pinning "the item moves only after all
   three verdicts" with all three seats running at once.

## User Scenarios & Testing

### User Story 1 - CAP proposed from the calibrated host (Priority: P1)

`bin/wuwei calibrate` (and `bin/wuwei config promote`) measures the host (cores, free
memory, the memory cost of one seat measured from the first seats that ran, or a default
before any ran) and proposes `cap`: the number of seats that fit above the memory floor
with one core each, never above `host.seats`, never below 1. The profile is written to
`calibration.md`; `cap` goes into the config proposal under calibrate's existing rule
(added when absent, listed as "Config differs; edit by hand: cap" when present and
different).

**Why this priority**: without a measured CAP the lead proposes 1 and nothing else here
changes the day.

**Independent Test**: `python -m pytest -q tests/test_calibrate.py -k host`.

**Acceptance Scenarios**:

1. **Given** a host with 8 cores, 10240 MiB free, `host.free_memory_mb = 1024`,
   `host.seats = 4` and a measured seat cost of 3072 MiB, **When** calibrate runs, **Then**
   calibration.md shows the host profile and the proposed cap is 3.
2. **Given** the same host with `host.seats = 2`, **Then** the proposed cap is 2.
3. **Given** no seat has run yet, **Then** the profile says the seat cost is the default
   (unmeasured) and the cap is computed from the default.
4. **Given** the host port is unmeasured, **Then** no cap is proposed, calibration.md and
   stderr say why, and calibrate exits 2.
5. **Given** config.toml already has `cap = 1`, **Then** calibrate does not rewrite it and
   prints "Config differs; edit by hand: cap".
6. **Given** a launch passes the launch guard, **Then** its `seat launched` event carries the
   free memory in MiB and the running seat count measured at that launch.

### User Story 2 - Seats per goal in the plan and the gate question (Priority: P1)

`plan propose` writes `cap` and a `seats` map (how many of CAP each goal gets) into
proposal.json and plan.md. The map is derived from the ranked queue (the first CAP items,
counted per goal) unless the lead JSON carries a valid `seats` map, which is how a "Change
something" edit reaches the plan. The gate question states "N seats: G-1 2, G-2 1 (CAP 3)"
and "Change something" lists seats per goal among the separate questions. `plan approve`
records the map in day state as `goal_seats`, written only by `plan approve`.

**Why this priority**: the owner asked to see and approve the seats per goal at the start
of the day.

**Independent Test**: `python -m pytest -q tests/test_plan.py -k seats`.

**Acceptance Scenarios**:

1. **Given** CAP 3 and a ranked queue A (G-1), B (G-2), C (G-1), D (G-2), **When** `plan
   propose` runs, **Then** plan.md contains `Seats per goal: 3 seats: G-1 2, G-2 1 (CAP 3)`.
2. **Given** that proposal, **When** `plan gate` runs, **Then** the Approve description
   contains `3 seats: G-1 2, G-2 1 (CAP 3)` and the Change something description names seats
   per goal.
3. **Given** a lead JSON with `seats: {"G-1": 1, "G-2": 2}`, **Then** plan.md and the gate
   question show that split instead of the derived one.
4. **Given** a `seats` map naming an unknown goal, a count below 1 or a total above `cap`,
   **Then** `plan propose` exits 2 naming the plan JSON contract.
5. **Given** approval, **Then** day state has `goal_seats` equal to the proposal's map, and a
   generic `state set goal_seats ...` is refused as reserved, naming `wuwei plan approve`.
6. **Given** `plan template`, **Then** its `cap` is the configured `cap`.

### User Story 3 - Every dispatchable item launched up to CAP in one turn (Priority: P1)

`wuwei dispatch next --all` prints the launch set. For each approved, open item without a
running seat, gate items first, then build items, then planned items, each group in queue
order, it gives the action the single-item command returns (`dispatch next <item>` for an
item at gate or delta, `build next <item>` for an item building or briefed), or `start`
with the commands that brief it for a planned item without a builder brief. Builders stay
within CAP; the set's launches stay within the free `host.seats`. Planned items start
within their goal's share of `goal_seats` first, then in queue order to fill CAP. An item
whose launches do not fit, or a planned item beyond CAP, is listed as `wait` with the
reason. `dispatch next <item>` keeps its one-item form. The plan skill tells the planner to
run the set, brief every `start`, run the set again, and emit every `launch` and `continue`
as Agent calls in one message, which the harness runs concurrently. The launch guard checks
CAP per launch, against the day's approved CAP.

**Why this priority**: this is the parallel start the owner asked for.

**Independent Test**: `python -m pytest -q tests/test_parallel_dispatch.py`.

**Acceptance Scenarios**:

1. **Given** a calibrated host with room for three seats (config `cap = 3`, proposal CAP 3)
   and three approved items across two goals, **When** the planner's first dispatch turn
   runs through the hooks (fixture day), **Then** `dispatch next --all` lists three `start`
   entries, after the three builder briefs it lists three `launch` entries, and the three
   Agent PreToolUse payloads all pass with three builder seats running at once.
2. **Given** CAP reached (three builders running) and a fourth approved planned item,
   **Then** `dispatch next --all` lists the fourth as `wait` naming CAP, a fourth builder
   PreToolUse is refused naming CAP 3, and `wuwei next` says the fourth item waits and names
   the running builder seat that started first as the one expected to free first.
3. **Given** `cap = 1` set by the owner, **Then** the plan proposes CAP 1, `--all` lists one
   `start`, and a second builder launch is refused: sequential as today.
4. **Given** config `cap = 1` and a day approved at CAP 3, **Then** the launch guard admits
   three builders and refuses the fourth: the gate's CAP is the one enforced.
5. **Given** `dispatch next` with neither an item nor `--all`, or with both, **Then** it
   exits 2 naming the two forms.

### User Story 4 - An item's gate sentinels run together (Priority: P2)

For an item at the gate, the three sentinel launches (arch, quality, security) are listed
together and launched in one message; `dispatch next` keeps the item at `gate` until all
three verdicts are received, then moves it (raise or fix). The delta round the same, with
`continue` actions. `--all` lists an item's gate seats only when all of them fit the free
`host.seats`, so they are never split across turns.

**Why this priority**: the gate code already waits for all verdicts; this story is the
skill instruction, the `--all` fit rule and the fixture test that pins it.

**Independent Test**: `python -m pytest -q tests/test_parallel_dispatch.py -k gate`.

**Acceptance Scenarios**:

1. **Given** an item at the gate with three logged gate briefs, **When** the three Agent
   PreToolUse payloads run before any SubagentStop, **Then** three sentinel seats are
   running; after one and after two receipts `dispatch next` still returns `gates` and the
   item is still at `gate`; after the third receipt it returns `raise`.
2. **Given** `host.seats` leaves two free seats, **Then** `--all` lists that item as `wait`
   naming `host.seats` instead of two of its three launches.

### User Story 5 - Running seats per goal and N of CAP on the board, the status line and next (Priority: P2)

`status --line` (and so the board, whose first line is the status line) shows
`seats N of CAP M` with the running builder seats per goal once the gate is approved. The
`next` dispatch row says how many planned items can start and points at `wuwei dispatch
next --all`.

**Independent Test**: `python -m pytest -q tests/test_signal_status.py tests/test_next.py tests/test_board_mcp.py -k seats`.

**Acceptance Scenarios**:

1. **Given** an approved day with CAP 3 and running builder seats for A (G-1) and B (G-2),
   **Then** `status --line` contains `seats 2 of CAP 3 (G-1 1, G-2 1)` and the board text
   contains the same part.
2. **Given** an approved day with planned items and free CAP, **Then** the `next` row is
   `dispatch` with command `wuwei dispatch next --all` and names how many can start.

### Edge Cases

- No candidates: the derived map is empty and the gate says `0 seats (CAP N)`.
- Fewer candidates than CAP: the map sums to fewer than CAP; nothing pads it.
- An unplanned candidate counts under the key `unplanned`.
- A day approved before this feature (no `goal_seats`): `--all` uses queue order only;
  status shows running seats per goal without a planned split.
- A carried or parked item (a seat decision outcome, as `next` reads it) is not dispatched.
- A second-opinion `run` entry counts against free `host.seats` with its gate set.
- An item whose single-item call refuses (steward note, missing ticket, spec gap) becomes a
  `refused` entry with the reason; the rest of the set is still printed and the command
  exits 1.
- Launches recorded before this feature have no `free_mib`; the seat cost ignores them.
- `os.cpu_count()` returns None: the host profile is unmeasured (US1 scenario 4).

## Requirements

### Functional Requirements

- **FR-001**: The launch guard MUST record `free_mib` and `running` on the `seat launched`
  payload of every admitted Claude launch.
- **FR-002**: A metrics function MUST derive the memory cost of one seat in MiB from those
  payloads (unmeasured without a zero-running baseline or a sample) and `metrics.collect`
  MUST expose it as `seat_cost_mib`.
- **FR-003**: Calibrate MUST compute a host profile (cores, free MiB, seat MiB and whether it
  is measured or the default, proposed cap) through the host port, write it to
  calibration.md, and propose `cap = max(1, min(memory fit, cores, host.seats))` through the
  existing config proposal rule; `config promote` MUST include the same proposal. An
  unmeasured host proposes nothing and calibrate exits 2 with the reason.
- **FR-004**: `plan template` MUST print the configured `cap`.
- **FR-005**: The plan proposal MUST accept an optional `seats` map (a confirmed goal or
  `unplanned` to an integer of at least 1, total at most `cap`), derive it from the first
  `cap` ranked candidates when absent, write it to proposal.json and plan.md, and state it
  in the gate question as "N seats: G-1 2, G-2 1 (CAP M)".
- **FR-006**: `plan approve` MUST record the map as `goal_seats`, a producer-owned state key.
- **FR-007**: The launch guard MUST refuse a builder launch at the day's approved `cap`
  (day state), not `config['cap']`.
- **FR-008**: `wuwei dispatch next --all` MUST print the launch set of US3 and US4 by calling
  the existing single-item functions; `dispatch next <item>` MUST be unchanged.
- **FR-009**: `wuwei next` MUST name the waiting item and the running builder seat that
  started first when CAP is reached, and its dispatch row MUST point at `--all`.
- **FR-010**: `status --line` MUST show running builder seats per goal and N of CAP once the
  gate is approved.
- **FR-011**: The plan skill MUST tell the planner to emit every launch of a set (builders
  and an item's gate seats) as Agent calls in one message and say the harness runs them
  concurrently; the lead charter MUST say where `cap` and `seats` come from.
- **FR-012**: Docs: concepts.md (CAP and seats per goal in plain words), daily.md (one
  paragraph), configuration.md (`cap`, `host.seats`).

### Key Entities

- Host profile: `{cores, free_mib, seat_mib, seat_source: "measured"|"default", cap}` or
  `{unmeasured: <reason>}`; written to calibration.md only.
- `seats` (proposal) and `goal_seats` (day state): `{goal id or "unplanned": int >= 1}`.
- `seat launched` payload: `{name, item, free_mib, running}` (the last two new).
- Launch set: `{action: "set", cap, building, free_seats, entries: [{item, goal, action, ...}]}`.

## Success Criteria

- **SC-001**: The four Acceptance scenarios of issue #474 pass as tests (US3 scenario 1,
  US3 scenario 2, US4 scenario 1, US3 scenario 3), the parallel case through the hooks on
  the fixture day.
- **SC-002**: The full suite passes with `python -m pytest -q`.
- **SC-003**: No new config key, adapter, module or dependency.

## Assumptions

- `[host] max_seats` in the issue is the existing `host.seats`, the total seat ceiling the
  launch guard already enforces. One ceiling, already documented; no new key.
- The proposed `cap` reaches config.toml under calibrate's existing rule: added when absent,
  "edit by hand" when present and different. The workspace template always has `cap = 1`,
  so the owner applies the measured value once with `bin/wuwei config set cap <n>` in a host
  terminal. This keeps an owner-set `cap = 1` (issue Acceptance 4) from being overwritten
  by a later promote. Overturn if the owner wants promote to replace the default.
- The day's approved CAP is the one the launch guard enforces. It is producer-owned after
  approval (`state.OWNER_FIELDS` allows generic writes only before `gate_approved`, and
  `plan approve` overwrites it from the proposal), and `next`, `status` and `plan add`
  already read it. `host.seats` and the memory floor stay the owner's hard ceilings, read
  from config at every launch.
- Seat cost means memory: the drop in free memory per running seat, the median over the
  latest day's launches measured against the free memory at zero running seats. Before any
  seat ran, the default is 1024 MiB per seat (the default memory floor). A heuristic: other
  processes move free memory too, and the median damps it.
- The planner works in turns: Agent calls in one message run concurrently and the turn
  returns when all of them stop. At the start of a turn the previous turn's seats have
  stopped, and `--all` fits each turn's launches into the free `host.seats`, gate items
  first, so new builders never starve an item's gate set.
- `goal_seats` steers which planned items start first (each goal's share, then queue order
  to fill CAP). CAP stays the only limit the launch guard enforces for builders.
- "The heartbeat's seat count follows" needs no change: day state `seats` is the one source
  the guard, status and the board read; the heartbeat has no seat probe.
- The board shows seats through the status line it already prints first; the dashboard
  template already shows `CAP running/limit` on the build column.
- The relayed user message for this run is a pasted hook refusal from another repository's
  session (a `gh run list` pipeline refused by the WUWEI deploy guard); it carries no
  instruction for this issue. This spec follows the computed task for #474.

## Deferred

- A `plan propose` refusal when `cap` exceeds `host.seats` (today the launch guard's host
  ceiling catches it at launch).
- Seat cost from a per-seat memory probe instead of free-memory deltas.
