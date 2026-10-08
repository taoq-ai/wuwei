# Feature Specification: Day pace (careful, steady, fast)

**Feature Branch**: `579-pace`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #579: a day pace (careful, steady, fast) chosen at the morning gate
from the lead's advice on the queue's complexity, deadlines and the host, sets the tier
floor, fix rounds, local versus CI checks and the seats used, never a floor or who decides,
and the retro reports cycle time and escaped defects per pace.

Owner, 2026-10-08: "Can we add some kind of pace control in WUWEI too, so it adjusts like
you did now in the days we need to move faster? Also with advice based on the complexity of
the planned items?" Owner comment, same day: "Pace takes the host capacity, owner wish and
token budget, and tries to balance it with proper advice."

Builds on #567 (process depth per tier: `dispatch.depth`, `dispatch.step_zero`,
`dispatch.GUARD_CODE`, `dispatch.CLASS_PATHS`, `dispatch._changes`, `metrics.cycles`,
`metrics.cycle_by_tier`), #280 (tiers), #528/#546 (CAP from the host and the token budget),
#530 (floors and the 9.2 invariant table) and #551 (the CLI owns the path). The pace sets
inputs to what #567 and #528 already read: no second tier, no second depth table.

## Root cause

Line numbers are on `main` at 4e23a55, which carries #567 (merged as PR #577). The
worktree base (b6daa42) predates it; see Assumptions.

WUWEI has every knob the owner turned by hand on 2026-10-08 (tier, depth per tier, CAP from
the host, local checks), but each reads a fixed input, nothing reads a day-level choice, and
nothing advises one:

- `cli/wuwei/dispatch.py:42-98` (`tier`): the tier comes from the diff, flags, track, the
  repository floor and the lead tier only, and `dispatch.py:114-119` (`depth`, #567)
  returns that recorded tier. No input can raise every item to standard on a risky day or
  lighten a plain standard item on a day that has to move fast.
- `cli/wuwei/dispatch.py:307-375` (`launch_set`): seats are `calibrate.host` CAP and
  `host.seats` only. `cli/wuwei/calibrate.py:450-508` (`host`) measures free memory, cores
  and the token budget but not the load average. On 2026-10-08 ten cores ran at load 34
  while the launch set kept starting seats.
- `cli/wuwei/guards/commit_push.py:155` (`fast_evidence` loops `repo['fast_checks']`),
  `cli/wuwei/fast_checks.py:59` (`record`, same loop) and `cli/wuwei/commands/build.py:151`
  (`next_action`): the local checks are always the repository's `fast_checks`. A day cannot
  choose "the full suite before the PR" or "only the tests the diff touches, CI is the gate".
- `cli/wuwei/plan.py:156-247` (`propose`) computes the queue, CAP and the budget line but no
  pace and no advice; `plan.py:250-278` (`gate_widget`) offers only Approve and Change
  something; `plan.py:281-373` (`approve`) records no pace; `plan set` (`plan.py:462-480`,
  `commands/plan.py:80-93`) has no day-level assignment.
- `cli/wuwei/commands/status.py:356-376` (`_groups`), `cli/wuwei/report.py:91` (`build`),
  `cli/wuwei/retro.py` and `cli/wuwei/metrics.py:644` (`collect`) cannot show a pace or
  measure anything per pace, so the owner cannot tell whether going faster costs escaped
  defects.

## User Scenarios and Testing

### User Story 1: The gate advises a pace and the day runs at it (Priority: P1)

The owner opens the morning gate. The card recommends a pace in two lines that name the
queue's shape, the nearest goal date, the host and the token budget, and which input binds.
The owner approves. Day state holds the pace, and every command that dispatches, checks,
pushes or merges reads it from there. No seat decides anything about pace.

**Independent Test**: `plan propose` on a fixture lead JSON with 7 light and 2 standard
candidates and a goal due in two days, `plan gate`, `plan approve --pace "Approve"`, then
`dispatch.tier` and `fast_checks.commands` on an item worktree with fake ports.

**Acceptance Scenarios**:

1. **Given** a queue of seven light and two standard items and a goal due in two days,
   **When** the planner runs `wuwei plan propose` and `wuwei plan gate`, **Then** the gate
   card's first option is `Approve` at pace fast, and its description carries two lines:
   `9 items, 7 light, 2 standard, G-2 due <date>: fast, <n> seats, expected close <HH:MM>`
   and the host and budget line ending in `binding: queue`.
2. **Given** that card, **When** the owner answers `Approve` and the planner runs the record
   command `wuwei plan approve --items ... --goals-confirmed --pace "Approve"`, **Then** day
   state holds `pace = "fast"` and the `plan.approved` payload carries `pace`,
   `recommended` and `wish`.
3. **Given** pace fast, **When** `dispatch next` tiers a standard item whose diff touches no
   guard code, trust path or lead flag, **Then** its gate record keeps `tier: standard` and
   the steady gate roles (arch, quality, security) and gains `depth: light`, so #567's light
   process applies: no class sweep, no step zero, the same sentinel re-reads after a fix,
   the light verdict shape.
4. **Given** pace fast and `repos.tests = "python3 -m pytest -q"`, **When** the builder's
   checks run (`wuwei build check`, `wuwei fast-checks`) on a diff that changes
   `tests/test_a.py`, **Then** the one recorded check is `python3 -m pytest -q
   tests/test_a.py`, and the push guard accepts that record at HEAD as the evidence.
5. **Given** pace fast, **When** `wuwei merge` (the shepherd's only merge path) reaches a PR
   whose required checks are pending, **Then** it does not merge: it merges only at green
   required checks at the gated head (merge policy unchanged, invariant I17).

### User Story 2: Guard work is never lightened (Priority: P1)

A queue with items that touch `cli/wuwei/guards/` gets a careful recommendation, and those
items run full depth when the owner picks careful or fast for the rest.

**Acceptance Scenarios**:

1. **Given** two candidates whose `paths` include `cli/wuwei/guards/x.py`, **When** the
   planner proposes, **Then** the recommendation is careful with the reasoning `2 items
   touching guard code: careful`, and the unlock clause says steady unlocks once they merge.
2. **Given** pace careful or fast, **When** `dispatch next` tiers an item whose diff touches
   guard code or a repository trust path, **Then** its tier and depth are full, with the
   reason `pace <p>: <path> matches <pattern>`.
3. **Given** pace careful, **When** `dispatch next` tiers a light item, **Then** its tier is
   standard (reason `pace careful`) with three gates.
4. **Given** pace steady, **When** the same items are tiered, **Then** every tier record is
   identical to today's (#280 and #567 unchanged).

### User Story 3: The host and the budget bound the advice (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a host with ten cores and load average 34 (the 2026-10-08 measurement) and pace
   fast, **When** the planner runs `wuwei dispatch next --all`, **Then** every entry that
   would launch a seat is `wait` with the reason `host load 34.0 at or over 10 cores (pace
   fast); the next seat launches when the load falls below 10`, day state records
   `cap_bound = "load"`, and `wuwei status --line` shows `pace fast` and `held by load`.
2. **Given** the same host, **When** the planner proposes a queue whose queue input asks for
   fast, **Then** the advice is steady, the binding input is `host`, and the reasoning says
   `fast unlocks when the load average falls below 10`.
3. **Given** pace careful and a host CAP of 4, **When** `dispatch next --all` runs, **Then**
   at most 3 builders are planned (CAP minus one, bound `pace careful`) and the agent-launch
   guard is unchanged: no new refusal.
4. **Given** `budget.tokens_per_day` and measured per-seat tokens that cover 6 of 9 queued
   items at the recommended pace, **When** the planner proposes, **Then** the budget part of
   the second line reads `budget reaches 6 of 9 items at <pace>: advised against`, and the
   binding input is `budget`.
5. **Given** `[pace] default = "steady"` and an advice of fast, **When** the gate card is
   printed, **Then** the Approve description has one more line `Your default is steady; the
   advice is fast (binding: queue)`. The owner's pick is recorded as given, never replaced.

### User Story 4: The pace changes during the day and is visible (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an approved day, **When** the planner runs `wuwei plan set pace=careful`,
   **Then** day state holds `pace = "careful"`, a `pace.set` event records `pace` and
   `previous`, and items tiered afterwards use careful (tier records already written stay).
2. **Given** `wuwei plan set pace=quick`, **Then** it exits 2 naming the three paces.
3. **Given** any day, **When** the planner runs `wuwei pace`, **Then** it prints the current
   pace, the advice and why, the three inputs (host, wish, budget) and the balance (binding
   input and the unlock clause), and exits 0.
4. **Given** pace steady, **Then** `wuwei status --line` shows no pace token; given careful
   or fast it shows `pace careful` or `pace fast`.

### User Story 5: The retro measures each pace and the steward proposes a default (Priority: P2)

**Acceptance Scenarios**:

1. **Given** merged items across days at two paces, **When** the report and the retro are
   built, **Then** a `## Pace` section shows the day's pace (chosen, recommended, binding)
   and, per pace: days, items merged, median cycle minutes per tier (#567), escaped defects
   (5.6) and cards asked.
2. **Given** ten or more days with a recorded pace across at least two paces and no pace
   card in the last ten days, **When** `wuwei plan propose` runs, **Then** the steward
   writes one owner card `Set the default pace to <p>?` whose option titles read
   `pace.default = <p>` (recorded with `wuwei config set pace.default <p> --from-card D-n`),
   with the numbers per pace in its context, and the retro names the card.
3. **Given** a pace with more escaped defects per merged item than another, **Then** the
   card and the retro report it on its own line, and the card does not recommend it.

### Edge Cases

- A diff that cannot be read: the tier rises to standard as today, and fast never lightens
  it (`depth` stays the tier).
- `repos.tests` empty, no changed test file, or the diff unreadable at fast: the checks are
  the repository's `fast_checks`, as at steady. Evidence is never empty.
- `repos.tests` empty at careful: the checks are the `fast_checks`, and the builder brief's
  `Checks:` line says the full suite is not configured locally and CI runs it.
- `os.getloadavg` unavailable: the load is unmeasured, there is no load hold, and the host
  line says `load unmeasured`.
- A `proposal.json` without `pace` (written before this feature): `plan approve` without
  `--pace` records the config default.
- `plan approve --pace "Change something"`: exits 2 saying Change something asks the
  separate questions; nothing is recorded.
- A day state without `pace`: every reader treats it as `[pace] default`.

## Requirements

### Functional Requirements

- **FR-001**: Day state gains `pace` (`careful`, `steady` or `fast`), producer-owned:
  written only by `wuwei plan approve` and `wuwei plan set pace=`; a generic state write is
  refused naming them. A missing value reads as `[pace] default`.
- **FR-002**: Config gains `[pace] default` (`steady`, one of the three paces) and
  `repos.tests` (string, default empty), the repository's test runner command.
- **FR-003**: `wuwei plan propose` computes the advice and writes `pace`, `pace_reasoning`
  (the card lines) and `pace_advice` into `proposal.json`, and shows them in `plan.md` under
  `## Gate proposal`. Lead candidates may carry `paths` (a list of strings), validated by
  `_proposal`.
- **FR-004**: The advice balances three inputs and names the one that binds: queue (the
  predicted tier per item, items touching guard code, expected cycle minutes per tier from
  the #567 medians against the envelope end, the nearest goal date), host (cores, load
  average, last suite duration, CAP) and budget (tokens per day, used, per-seat tokens,
  items reached at the advised pace). The owner's wish (`[pace] default`) is shown, never
  overridden. When two inputs disagree the advice takes the slower pace and says what would
  unlock the faster one.
- **FR-005**: `wuwei plan gate` prints one card: `Approve` (the recommended pace, its
  reasoning lines in the description), `Approve at <p>` for each other pace, and `Change
  something`. Its record command is `wuwei plan approve --items ... --goals-confirmed
  --pace "<label>"`.
- **FR-006**: `plan approve --pace <label>` maps `Approve` to the recommended pace and
  `Approve at <p>` or `<p>` to that pace, writes it to state and to the `plan.approved`
  payload with `recommended` and `wish`; without `--pace` it records the recommendation,
  else the config default.
- **FR-007**: `wuwei plan set pace=<p>` writes the pace and a `pace.set` event (`pace`,
  `previous`); any other value exits 2 naming the paces. The state guard lets the literal
  `plan set pace=<p>` run from the registered planner session below strict; from a seat it
  gets the existing `plan set` owner-action reason, so a seat never changes the pace (the
  pace picks which checks count as push evidence).
- **FR-008**: `dispatch.tier` applies the pace once, through one pure function
  `pace.adjust`: careful raises light to standard and guard-code or trust-path diffs to
  full; fast raises guard-code or trust-path diffs to full and sets `depth: light` on a
  standard tier with a measured diff, no guard code or trust path, no lead flag and no FULL
  track; steady changes nothing. No pace lowers a tier, the repository floor or the gate
  roles. The record gains `depth`; #567's `dispatch.depth` and every #567 reader that
  derives depth from `tier()` prefer it.
- **FR-009**: Fix rounds follow the depth (#567): at fast a standard item at light depth
  gets the same-sentinel re-read; full keeps the delta round. No separate fix-round rule.
- **FR-010**: `fast_checks.commands(root, config, repo, tree)` returns the checks for the
  day's pace: steady the `fast_checks`; careful the `fast_checks` plus `repos.tests` when
  set; fast `repos.tests` followed by the changed test files present in the tree, else the
  `fast_checks`. `fast_checks.record`, `build check` and the push guard's `fast_evidence`
  use it, so the evidence rule follows the pace. Each check record gains `seconds`.
- **FR-011**: The builder brief carries one `Checks:` line naming what the pace runs, so
  the seat never chooses.
- **FR-012**: `calibrate.host` also returns `load` (the one-minute load average, or None
  when unmeasured), `per_seat_tokens` and `used_tokens`, and its text names the load.
- **FR-013**: `dispatch.launch_set` applies `pace.seats`: careful plans CAP minus one (at
  least 1, bound `pace careful`); fast holds every launch as a `wait` with the load reason
  when the load average is at or over the core count (bound `load`). Neither adds a
  refusal: the agent-launch guard does not read the pace.
- **FR-014**: `wuwei pace` (read-only) prints the pace, the advice and why, the three inputs
  and the balance; exit 0, exit 2 with the reason when the day cannot be read.
- **FR-015**: `wuwei status --line` shows `pace <p>` when the pace is not steady, and `held
  by load` when `cap_bound` is `load`.
- **FR-016**: `metrics.cycles` rows gain `pace` (the pace of the day the item merged);
  `metrics.by_pace` returns per pace: days, merged, `cycle_by_tier`, escaped (5.6) and cards
  (`decision_routes` on that pace's days); `metrics.collect` exposes it as `by_pace`.
- **FR-017**: The report and the retro gain a `## Pace` section from `by_pace` and the day's
  pace; the retro names an open pace card.
- **FR-018**: `pace.propose_default`, called by `plan propose` beside `cruise.propose`,
  writes the default-pace card under the conditions of US5, at most once per ten days.
- **FR-019**: Design 9.2 and `tests/test_invariants.py` gain three rows: no pace lowers a
  floor (I15), no pace changes who decides (I16), fast merges only at green required checks
  (I17), numbered after the last row on the base.
- **FR-020**: Docs: design 5.2 (Pace) and 5.6 (per pace), `docs/site/concepts.md` (pace),
  `daily.md` (the gate card lines), `configuration.md` (`[pace] default`, `repos.tests`),
  `reference.md` (`wuwei pace`, `plan set pace=`, `plan approve --pace`).

### Floors (unchanged at every pace)

Records, publish grants, strict refusals, trust-boundary findings, merge only at the gated
head with green required checks, decision routing and every 9.2 invariant hold at every
pace. Pace changes how much seats do and in what order, never what the owner must answer or
what the guards refuse.

### Key Entities

- **Pace**: one of `careful`, `steady`, `fast`; one per day in day state.
- **Advice**: `{pace, lines, seats, close, binding, unlock, reach}` from `pace.advise`,
  stored in `proposal.json` as `pace`, `pace_reasoning` and `pace_advice`.

## Success Criteria

- **SC-001**: The issue's acceptance fixtures pass: the fast recommendation with two lines,
  careful for guard items with full depth, the unchanged invariant walk at fast, the load
  hold on `dispatch next --all` shown on the status line, and the per-pace retro with the
  steward's card.
- **SC-002**: With pace steady every existing dispatch, check, push and merge test passes
  unchanged.
- **SC-003**: After ten fixture days at two paces the retro shows cycle minutes, escaped
  defects and cards per pace, and exactly one default-pace card exists.

## Assumptions

- #567 is on `main` (PR #577, a2ad2d1) but not on this worktree's base (b6daa42). The
  builder first brings the branch up to `main` (the branch holds only these spec files), so
  `dispatch.depth`, `step_zero`, `GUARD_CODE`, `CLASS_PATHS`, `metrics.cycles` and
  `cycle_by_tier` exist; it never re-implements depth or cycle metrics. If they are still
  absent, the build stops and says so.
- Design 9.2 on `main` already uses I12 to I14 (#559, #560). The three pace rows take the
  next free ids at build time (I15 to I17 on `main` at 4e23a55); this spec names them I15 to
  I17.
- Steady keeps today's behaviour exactly, including #567's guard treatment (standard with
  step zero). The acceptance phrase "full depth whatever the owner picks" is met for careful
  and fast; the issue's table says steady is "the computed tier", and changing it would
  change every default day.
- Fast lightens depth, not the tier: the gate roles stay what the tier sets (three
  sentinels at standard), so the repository floor, which is a tier floor, never moves. Fast
  does not lighten an item with a lead flag (trust surface, boundary, agent surface), a FULL
  track or an unreadable diff.
- The pace is applied when `dispatch next` tiers an item, once per item. `plan set pace=`
  affects items tiered afterwards; tier records already written are not rewritten.
- "Touched tests" are the test files the item's diff changes, matched by #567's `TEST` class
  globs and present in the tree, appended to `repos.tests`. This fits runners that take file
  arguments (pytest, jest, vitest, rspec); for others the owner leaves `repos.tests` empty
  and fast falls back to the fast checks.
- "A pending CI run" is not checked at push time: CI cannot run before the push. CI as the
  gate is the merge policy, which already merges only at green required checks; I17 keeps it.
- The load hold applies only at fast, as the issue's table says, and only to launches the
  launch set plans (waits). Holding steady too would make the existing launch tests depend
  on the host's load.
- "A seat that would push the load above the core count" is read as "the load is at or over
  the core count now"; the load a seat adds is not predicted.
- The predicted tier of a candidate is the lead's `tier` when given, `full` for a FULL
  track, else `standard`; guard items come from the candidate's `paths` matched against
  #567's guard code and the configured repositories' `trust_paths`. The lead's size is not
  turned into a tier.
- Expected minutes per tier are #567's medians; without a measurement the fallbacks are
  light 60 and standard 180 (#567's targets) and full 360.
- The token cost of an item is per-seat tokens times the seats its depth runs (builder plus
  one quality gate at light, builder plus three gates at standard and full); fix rounds and
  second opinions are not counted.
- The budget never changes the advised pace (only careful costs more seats, and guard items
  run full at careful and fast anyway); it names itself as binding and advises against the
  pace when it reaches fewer items than the queue.
- Escaped defects per pace reuse the 5.6 measure (`metrics._escaped`, a later builder brief
  naming the item) without a separate seven-day window.
- A day whose pace changed mid-day counts at its final pace in the per-pace metrics.
- `plan set pace=` is not owner-only (the issue says so): the planner session runs it
  without a host terminal, and it is recorded in state, the event log and the report. It is
  not seat-writable, because the pace selects the push evidence. Under strict, like every
  `plan set`, the owner runs it in a host terminal. No pace relaxes a refusal: under strict a
  missing record of the pace's checks is still refused by the push guard.
- The pace card is a config card (`pace.default = <p>` option titles) recorded through
  `config set --from-card`, like every config card since #529.

## Deferred

- Predicting each candidate's tier from its size and files before the build, beyond the
  lead tier and the guard paths.
- A per-seat load prediction for the host hold.
