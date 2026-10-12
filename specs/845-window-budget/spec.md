# Feature Specification: seats and pauses follow each runtime's usage window, not the day; next waits for the reset instead of stopping

**Feature Branch**: `845-window-budget` (feature directory `specs/845-window-budget/`)

**Created**: 2026-10-12

**Status**: Draft

**Input**: Issue #845: "feat(budget): seats and pauses follow each runtime's usage window, not
the day; next waits for the reset instead of stopping". Owner, 2026-10-11: WUWEI should
calculate how many seats run per usage window, not per day, and control the pause between
windows, taking each runtime's limits into account (Claude Code and Codex in parallel).

## Context

Today `budget.tokens_per_day` bounds CAP once a day: `dispatch.host` takes today's
`seat.usage` tokens and the median tokens per seat and lowers CAP to what is left, never
below 1. It knows nothing of the windows the runtimes enforce (a 5-hour and a 7-day window),
nothing of which runtime a seat ran on, and never holds a launch: a spent window cuts seats
off mid-task and `next` keeps offering launches.

`research.md` settles what each runtime exposes. Claude Code gives percent used and reset
time of both windows to the status line command on stdin. Codex writes them to the seat
thread's rollout file (`token_count` event). Neither exposes them through hooks or
`codex exec --json` events. Where no reading exists the window is estimated from
`seat.usage` tokens against a per-window token budget set once in config.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - next waits for the reset instead of starting work that will not fit (Priority: P1)

The owner runs a day on Claude Code. The 5-hour window has no room left for another seat.
`next` stops offering seat launches on Claude, lets running seats finish, and returns a timed
wait naming the reset time. The planner runs the wait in the background; when it exits after
the reset, the planner runs `next` again and the day goes on without the owner.

**Why this priority**: the issue's first acceptance line, and the failure the owner sees
today.

**Independent Test**: a workspace with a Claude window budget, seat tokens that leave less
than one seat of room, and a ready planned item: `wuwei next --json` returns a `wait` row with
`until` at the window's reset and a background command that exits after it; with the clock
past the reset, the same workspace offers the launch.

**Acceptance Scenarios**:

1. **Given** `budget.claude.five_hour = 300000`, 250000 tokens of Claude `seat.usage` inside
   the window and a median seat of 100000 tokens, **When** `next --json` runs with a planned
   item ready, **Then** no launch is offered and the row is a timed wait whose `until` is the
   window's reset time.
2. **Given** no budget and a saved Claude reading of 100 percent with a reset time, **When**
   `next --json` runs, **Then** it returns a timed wait until that reset.
3. **Given** the case of scenario 1, **When** the clock passes the reset time, **Then**
   `next --json` offers the launch again, with no owner step.
4. **Given** a builder seat running when the window is spent, **When** `next` runs, **Then**
   the running seat is not stopped or resumed and no new seat launches on that runtime.
5. **Given** a spent Claude window and a due duty or an owner decision, **When** `next` runs,
   **Then** the set returns the duty or the decision and each held launch carries `until`.

---

### User Story 2 - CAP per runtime; a ready launch goes to the runtime with budget (Priority: P1)

The owner configured Claude Code and Codex and approved a seat policy whose builder runs on
Claude with Codex as its alternate. Claude's window is spent and Codex's has room: the next
planned item starts its builder on Codex. Each runtime has its own CAP: the day's CAP bounded
by the room left in that runtime's windows.

**Why this priority**: the issue's second acceptance line.

**Independent Test**: two runtimes with budgets, Claude spent, Codex with room, builder policy
`{"runtime": "claude", "model": "opus", "alternate": "codex"}`: the launch set starts the
planned item's builder as a background `wuwei build` run on Codex; without `alternate` the
item waits for Claude's reset.

**Acceptance Scenarios**:

1. **Given** Claude's room is 0, Codex's room is 2 and the builder policy names Codex as its
   alternate, **When** the launch set resolves two briefed planned items, **Then** both start
   on Codex as background `wuwei build <item> <brief> <worktree>` runs and both build records
   bind runtime `codex`.
2. **Given** the same rooms and a builder policy with no alternate, **When** the launch set
   resolves them, **Then** both wait with Claude's reset time.
3. **Given** Claude's room 0, Codex's room 1, CAP 3 and three planned items, **When** the
   launch set resolves them, **Then** one starts on Codex and two wait with a reset time.
4. **Given** both runtimes have room, **When** a planned item starts, **Then** it starts on
   the policy runtime.
5. **Given** a build bound to Codex, **When** its fix round opens, **Then** the fix continues
   on Codex (the build record's runtime), never on the policy runtime.
6. **Given** two runtimes with budgets, **When** the launch set resolves, **Then** each
   runtime starts at most the day's CAP and its room in seats, and the capacity text names
   each runtime's room.

---

### User Story 3 - readings from the runtimes keep the estimate honest (Priority: P2)

The owner also uses Claude outside WUWEI. The status line reports 80 percent of the 5-hour
window used while WUWEI's seats spent little. WUWEI counts the reading, not only its own
seats, and waits until the reset time the runtime reports.

**Why this priority**: without readings the estimate misses the owner's own use and guesses
the reset; the P1 stories hold without them.

**Independent Test**: pipe a status line payload with `rate_limits` into
`wuwei status --line`; `.wuwei/windows.json` holds the reading. A Codex seat result whose
rollout file has a `token_count` event saves the Codex reading.

**Acceptance Scenarios**:

1. **Given** status line stdin with `rate_limits.five_hour` and `rate_limits.seven_day`,
   **When** `wuwei status --line` runs, **Then** `.wuwei/windows.json` holds both readings
   under `claude` and the printed line is the same as without stdin.
2. **Given** status line stdin with no `rate_limits`, malformed JSON or no stdin, **When**
   `wuwei status --line` runs, **Then** it prints the same line, exits 0 and does not touch
   the file.
3. **Given** a Codex seat result naming its `threadId`, and that thread's rollout file with a
   `token_count` event, **When** the result is recorded, **Then** the Codex readings are saved
   by window length (300 minutes is `five_hour`, 10080 is `seven_day`).
4. **Given** a reading of 80 percent on a 300000-token budget and 10000 counted seat tokens,
   **When** room is computed, **Then** used is 240000.
5. **Given** a reading whose reset has passed, **When** room is computed, **Then** the
   reading is ignored and the window is estimated.

---

### User Story 4 - existing workspaces upgrade without a manual edit (Priority: P3)

**Acceptance Scenarios**:

1. **Given** a config with `[budget] tokens_per_day = 200000`, **When** `init --upgrade` runs,
   **Then** the key is removed and reported, and the config then loads with no unknown-key
   warning.
2. **Given** a config with no budget and no reading at 100 percent, **When** the day runs,
   **Then** no window holds any launch.

### Edge Cases

- A damaged day log: windows are unmeasured and hold nothing (a damaged log never blocks a
  launch, as today); the capacity text carries the warning. A reading at 100 percent still
  holds launches.
- A damaged or unreadable `.wuwei/windows.json`: readings are ignored, with a warning in the
  capacity text.
- Per-seat tokens unmeasured: a budgeted window holds nothing until a seat is measured, as
  `tokens_per_day` did; the text says so.
- A budget below one measured seat: the window never has room; the wait names the budget and
  the reset so the owner can raise it.
- Runtime `none`: no window applies.
- A launch that is not a seat (`pr act`, `merge`, `seat stop`, a finding, a park) never waits
  on a window.
- The lead and steward run in the planner session and are outside the launch set; they are
  not held or routed.
- A Codex window of any length other than 300 or 10080 minutes is ignored.
- `seat.usage` rows written before this feature carry no runtime: they count toward
  `adapters.runtime`.
- A timed wait while seats still run: their completion notifications still bring the planner
  back before the reset.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Config MUST hold one token budget per runtime and window:
  `budget.claude.five_hour`, `budget.claude.seven_day`, `budget.codex.five_hour`,
  `budget.codex.seven_day` (integers, default 0, 0 is no budget). `budget.tokens_per_day` is
  retired.
- **FR-002**: Every new `seat.usage` row MUST name its `runtime`: the build record's runtime
  for a builder, the second opinion's runtime for a second-opinion gate.
- **FR-003**: One function MUST compute each runtime's room from: the input plus output
  tokens of that runtime's `seat.usage` rows inside each window; the saved reading when its
  reset is in the future; the window's budget; and the median tokens per seat of that runtime
  (else of all measured seats). Used is the larger of the counted tokens and the reading's
  percent of the budget. A window's room is `(budget - used) // per_seat`, never below 0; a
  reading at 100 percent or more gives room 0 with or without a budget; no budget and no full
  reading gives no bound.
- **FR-004**: A runtime's room MUST be the smallest room over its windows, and its `until` the
  latest reset among its windows that give 0 (the wait outlasts every spent window); with room
  left, the reset of the window that gives the smallest room, so a launch held because this
  turn's launches took the room still names a reset. A reading names the reset; an estimate
  takes the earliest counted row's time (else now) plus the window length.
- **FR-005**: The launch set MUST bound each runtime's seats by the day's CAP and that
  runtime's room (`dispatch.windows`) and name each runtime's room in its capacity text. The
  `budget` bound of `tokens_per_day` goes; `dispatch.host` and the day CAP keep their host and
  owner bound and stay at least 1. The Agent launch guard (a hook) does not compute windows.
  (Review F10: no per-runtime `cap` field; nothing read it.)
- **FR-006**: The launch set MUST NOT offer a seat launch on a runtime whose room is spent:
  each becomes a `wait` with `until` (ISO) and a reason naming the runtime, the window and the
  reset. Each offered seat launch takes one seat of its runtime's room. Launches that are not
  seats are never held. The room left is the room less the seats already running on that
  runtime and its live build loops (review D1); a builder seat counts against its build
  record's runtime (review E2). A new build is checked against its routed runtime's room before
  `build next` writes its record, so a held build is not bound, moved to implement or claimed,
  and takes no CAP slot (review F4).
- **FR-007**: When every launch of the resolved set is a wait, at least one held by a window
  (CAP and gate waits beside it carry no `until`, review F1), and the set has no duty and no
  decision, `next` MUST return one timed wait row: state `wait`, `until` (the
  earliest reset), a command that exits shortly after it, and a then line that runs it in the
  background and runs `next` when it exits.
- **FR-008**: A seat policy row MAY name `alternate`, a runtime with window budgets (`claude`
  or `codex`, never `none`) other than its `runtime` and other than the second opinion's
  runtime (a build routed there would be reviewed on its own thread, review F3). A
  new build MUST start on the policy runtime when it has room, else on the alternate when that
  has room, else wait. Only builder starts are routed; a build keeps the runtime its record
  binds, fix rounds included.
- **FR-009**: A builder launch bound to a runtime other than Claude MUST be offered as a
  background run of `wuwei build <item> <brief> <worktree>`; that command, the Agent launch
  guard and the second opinion's independence check MUST use the build record's runtime over
  the policy runtime. One loop per item (review F2, D2): the loop claims the build record
  (`loop`, its pid and start time) under the state lock, a second loop for the item exits 0
  without a job while that pid lives, and the item counts as running (`state.in_flight`, not
  offered again) while the loop lives. A loop that ended within two minutes of its start is
  offered as a `wait` with `until` two minutes after that start (review D2, E1), so `next`
  sleeps past it instead of offering it every turn or waiting on nothing.
- **FR-010**: `wuwei status --line` MUST save the Claude readings in its stdin's
  `rate_limits` to `.wuwei/windows.json` when they differ from the saved ones, and MUST print
  the same line and exit 0 whatever stdin holds.
- **FR-011**: The Codex runtime adapter MUST return the readings of the seat's thread (the
  last `token_count` event of its rollout file, matched by `window_minutes`) with the result,
  and the CLI MUST save them; a missing or unreadable rollout gives no reading and no error.
- **FR-012**: `init --upgrade` MUST remove `budget.tokens_per_day` and report it.
- **FR-013**: No window rule stops, signals or resumes a running seat.

### Key Entities

- **Window**: a runtime's rolling usage limit, `five_hour` (300 minutes) or `seven_day`
  (10080 minutes), with a token budget, used tokens, an optional reading and a reset time.
- **Reading**: what a runtime reported per window: percent used and reset time, cached in
  `.wuwei/windows.json` under the runtime's name.
- **Room**: whole seats a runtime's windows can still carry; bounded by the day's CAP it is
  that runtime's CAP.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the window tests, `next` offers zero seat launches on a runtime whose room
  is 0, and each such case returns `until` equal to the reset time.
- **SC-002**: The two-runtime test routes every routed launch to a runtime with room, and
  never to a runtime the role's policy row does not name.
- **SC-003**: The suite passes; the `tokens_per_day` tests are rewritten to windows and no
  other test changes its expectation.
- **SC-004**: No new module under `cli/wuwei/` and no new event kind; runtime code grows by
  under 240 lines (raised from 200 after review: the claim, stdin and running-seat fixes).
- **SC-005**: `wuwei status --line` prints the same bytes with and without a `rate_limits`
  stdin payload.

## Clarifications

### Session 2026-10-12

Answered by the spec author with the recommended option (AGENTS.md: no questions; assumptions
recorded).

- Q: What unit is a window budget? → A: Tokens, input plus output, the unit `seat.usage` and
  the retired `tokens_per_day` use. A reading's percent becomes tokens against that budget.
- Q: Where does a Claude reading come from, given that hooks carry none? → A: The status line
  stdin, read by `wuwei status --line`, which `init` already installs as the status line.
- Q: Does a reading without a budget bound anything? → A: Only at 100 percent or more. Below
  that there is no token figure to compare a seat with; the owner sets a budget for the fit
  guarantee.
- Q: Which launches are routed to another runtime? → A: Only builder starts, and only to the
  policy row's `alternate`. Gates, fix rounds and the shepherd keep their runtime and wait for
  its reset: a fix round resumes its builder's thread, and moving review seats between
  runtimes changes the gate the owner approved.
- Q: Does the stored day CAP drop to 0 when every runtime is spent? → A: No. The day CAP keeps
  its meaning (host or owner bound, at least 1), so plan propose and the state invariant stay
  as they are; the window bound is per runtime and applied in the launch set, where each held
  launch carries `until`.
- Q: How does the loop resume after a reset with no owner? → A: The timed wait's command is
  `sleep <seconds>`, run in the background; the Bash tool re-invokes the planner when it
  exits, and the planner runs `next`.
- Q: What happens to `budget.tokens_per_day`? → A: Retired; `init --upgrade` removes and
  reports it. A day is not a window, so its value is not mapped onto one.
- Q: Which seat cost applies per runtime? → A: The median tokens of that runtime's measured
  seats, else the median over all measured seats.
- Q: Where is routing decided when the launch set and `build next` could disagree? → A: The
  launch set decides with its running room counts and passes the runtime to
  `build.next_action`, which binds it in the new build record; a direct `build next` routes on
  fresh room.

## Assumptions

- Claude seat tokens come from the SubagentStop payload as today; Claude gate sentinels stay
  unmeasured (duration only), so the estimate undercounts gate use. Readings correct for it
  where the plan exposes them.
- Codex seat tokens stay unmeasured (the companion stores none); Codex room rests on its
  rollout reading and the per-seat median of measured seats.
- The rollout file format is not a documented contract; reading it is a best-effort adapter
  read that never fails a seat.
- The planner session's status line refreshes often enough that a Claude reading is minutes
  old at most while the session is open; a closed session leaves the last reading, which
  expires at its reset.
- `sleep` run in the background is allowed by the guards (no edge names it).
- The design spec 5.3 bullet on CAP and `tokens_per_day` gets an "Amended (owner, 2026-10-11,
  #845)" line; the issue's scope is the owner's decision.
- 15.8's budget governor belonged to the retired M5 listener and is not revived; this feature
  replaces only the token bound on launches.

## Deferred

- Codex seat tokens from the rollout's `total_token_usage` (cumulative over resumed rounds,
  so it needs a per-round delta).
- A window's token capacity estimated from a reading when no budget is set.
- Routing gates or the shepherd to an alternate runtime.
