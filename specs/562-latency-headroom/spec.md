# Feature Specification: Latency headroom and a regression report

**Feature Branch**: `562-latency-headroom`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #562: the latency job is green with headroom again: `status --line`
and PreToolUse under 35 ms CPU and SessionStart under 75 ms wall on the runner, the
invariant walk under a second with margin, and the job reports each probe against the last
green run so the next regression is caught before it fails.

Standing rule (#346, owner, 2026-10-08): reduce the latency, never loosen a budget, a test
or the job.

## Root cause

Runner variance (15 to 25 percent between two runs on near-identical code, startup floor
10.0 to 10.8 ms) lands on probes that have no margin left. The margin was eaten by work
added to the hot paths since #346 that the paths do not need:

- `status --line` computes the whole snapshot and renders a few fields of it.
  `cli/wuwei/commands/status.py:250` (`snapshot`) also counts live sessions (lines
  252-256, imports `wuwei.sessions`), the next reply and meeting (lines 277-289), the
  cruise label (lines 293-295, #283, imports `wuwei.cruise`), the plugin and template
  versions (lines 298-299) and calls the calendar adapter (lines 302-326, imports
  `wuwei.registry`, starts the adapter). `_groups` (line 352) renders none of them. The
  config is loaded twice per call (scan, line 239, and snapshot, line 291).
- `cli/wuwei/integrity.py:9-10` imports `wuwei.registry` at module level, so every path
  that only asks `integrity.version`, `restart` or `other_versions` (the status line since
  #521, the PreToolUse template check) pays for `registry` and its imports.
- `cli/wuwei/outward.py:352-363` (`_topics`) normalizes, escapes and looks up a pattern for
  every configured keyword on every call: about half of `outward.classify`'s time. It runs
  on every outward PreToolUse check and 3000 times in the invariant walk.
- SessionStart reads the same files more than once: `cli/wuwei/guards/lifecycle.py:68` and
  `:96` read the day state twice after `next.step` (`cli/wuwei/commands/next.py:168`) read
  it; today's `events.jsonl` is read by `next._seen` (`next.py:102-108`) and again by each
  of the two `watch.health` calls (`lifecycle.py:82` and `:86`, `watch.py:63-70`).
- `tests/test_invariants.py:487` asserts `elapsed < 3.0` (loosened from the one-second
  claim); its timed region also imports `test_grants` (line 198), `test_decision` and
  `wuwei.__main__` (lines 317-318) on first use, so pytest's assertion rewriting of those
  modules counts as walk time when the file runs alone, and every one of the 11 invariants
  runs on every one of the 18000 cases although most read one or two dimensions.
- `.github/workflows/tests.yml:49-62` prints figures but keeps none, so a probe drifting
  toward its budget is visible only when it fails.

## User Scenarios and Testing

### User Story 1: The probes are green with headroom (Priority: P1)

The latency job on main shows every probe under its budget with room for runner variance:
`status --line` and PreToolUse under 35 ms CPU, SessionStart under 75 ms wall, push under
65 ms wall, and every workspace probe at least 20 ms under its wall budget.

**Independent Test**: the latency probes in `tests/test_hooks.py` run locally against the
startup floor before and after the change at the same load; the above-floor CPU of each
changed path drops, and the module tests pin what the paths no longer import.

**Acceptance Scenarios**:

1. **Given** the latency job on main after the change, **When** it runs, **Then** every
   probe is green with the stated headroom, and the output shows each probe next to the
   last green figure.
2. **Given** a workspace with a configured calendar adapter and a cruise file, **When**
   `status --line` runs, **Then** it prints the same line as before and imports neither
   `wuwei.cruise`, `wuwei.registry` nor `wuwei.sessions`, and starts no adapter.
3. **Given** `bin/wuwei status` and `bin/wuwei status --json`, **When** they run, **Then**
   their output is unchanged (cruise, plugin, template, meetings, sessions still shown).
4. **Given** an outward check with configured sensitive keywords, **When** it classifies a
   text, **Then** the topics found are the same as before for every keyword, boundary and
   underscore form.
5. **Given** SessionStart in a workspace, **When** it runs, **Then** its output is
   unchanged and the session guard reads the day state once and today's events once.

### User Story 2: The invariant walk is under a second with headroom (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_invariants.py`.

**Acceptance Scenarios**:

1. **Given** the full suite on the runner, **When** `tests/test_invariants.py` runs,
   **Then** it walks at least as many cases as today (18000, asserted exactly as the
   product of the dimensions) and stays under one second of CPU with headroom.
2. **Given** a broken rule (the existing `BROKEN` cases), **When** the walk runs, **Then**
   it still fails and prints the full case tuple.
3. **Given** an invariant that reads a dimension it does not declare, **When** the walk
   runs, **Then** it fails loudly naming the invariant instead of passing silently.

### User Story 3: The job names the regression before it fails (Priority: P1)

**Independent Test**: `tests/test_latency_report.py` runs `scripts/latency_report.py` on
fixture JSON lines.

**Acceptance Scenarios**:

1. **Given** a current and a last green artifact, **When** the report runs, **Then** it
   prints one row per probe with the measured figure, the last green figure, the change in
   ms and percent, the budget and the margin.
2. **Given** a later commit that adds 15 ms to `status --line` while every other probe
   moves by runner variance (up to 20 percent), **When** the report runs, **Then** it names
   `status --line` as the probe that moved most.
3. **Given** a probe whose budget minus its figure is under 10 ms CPU (CPU budget) or under
   20 ms wall (wall budget), **When** the report runs, **Then** it names the probe as short
   of margin and exits 1; the job stays informational.
4. **Given** no last green artifact (first run, expired artifact), **When** the report runs,
   **Then** it prints the current figures with `-` for the last green column, names no
   probe as moved most, and still checks the margin.
5. **Given** an unreadable or malformed current artifact, **When** the report runs,
   **Then** it exits 2 with the reason.

### Edge Cases

- A probe that fails its budget is still written to the artifact (the row is written
  before the assert), so a red run carries its figures.
- A probe present now but absent from the last green artifact (new probe) shows `-` and
  takes no part in "moved most".
- A malformed last green artifact is treated as absent, with a one-line note.
- Locally, without `WUWEI_LATENCY_OUT`, nothing is written and the probes behave as today.

## Requirements

### Functional Requirements

- **FR-001**: `status --line` computes only what the line renders: no sessions count, no
  seats per goal, no reply or meeting dates, no cruise label, no plugin or template version, no calendar
  adapter call; `status` and `status --json` keep every field.
- **FR-002**: `integrity` imports `registry` only inside the functions that use it.
- **FR-003**: `outward._topics` builds the keyword patterns once per keyword list and gives
  the same topics as today.
- **FR-004**: the SessionStart session guard reads the day state once and today's events
  once (the clock stamps passed to both `watch.health` calls), with unchanged output.
- **FR-005**: any further cut on PreToolUse, SessionStart and push comes from profiling
  (`python3 -X importtime`, cProfile over 60 runs) and removes work from the path; no
  budget, probe, run count, fixture size or job setting is loosened.
- **FR-006**: `assert_latency_budget` appends one JSON line per probe to the file named by
  `WUWEI_LATENCY_OUT` when set: `probe`, `cpu_ms`, `wall_ms`, `budget_ms`, `measure`
  (`cpu` or `wall`), `floor_cpu_ms`, `floor_wall_ms`, `load`, `runs`.
- **FR-007**: `scripts/latency_report.py <current> [<last green>]` prints the comparison
  table, names the probe that moved most (largest relative rise of its budgeted measure),
  checks the margin (10 ms CPU, 20 ms wall) and exits 0 (every margin held), 1 (a margin
  short or a budget broken) or 2 (current artifact unreadable).
- **FR-008**: the latency job writes the artifact, uploads it, fetches the artifact of the
  last successful Tests run on main, and runs the report; the job stays
  `continue-on-error`.
- **FR-009**: `tests/test_invariants.py` asserts the exact case count (the product of the
  dimensions, at least 18000), restores `elapsed < 1.0`, keeps imports outside the timed
  region, and evaluates each invariant once per distinct value of the dimensions it reads,
  reporting failures with every full case tuple; an undeclared read raises.
- **FR-010**: `docs/site/reference.md#hook-latency-budget` says where the per-probe figures
  and the comparison live.

### Key Entities

- **Latency row**: one JSON object per probe per run (FR-006).
- **Latency artifact**: the JSON lines file of one job run, uploaded as `latency`.

## Success Criteria

- **SC-001**: on the runner, `status --line` and PreToolUse p95 CPU under 35 ms,
  SessionStart p95 wall under 75 ms, push p95 wall under 65 ms, every workspace probe at
  least 20 ms under its wall budget.
- **SC-002**: locally, at the same load, against a baseline taken on this worktree before
  the change, the above-floor CPU p95 (probe minus the `python3 -I` floor printed beside
  it) of `status --line` drops by at least 25 percent and that of PreToolUse, SessionStart
  and push by at least 10 percent each (the runner gap to SC-001 from the last green run is
  about 15, 2, 11 and 0 percent of the probe).
- **SC-003**: the invariant walk takes under 0.5 s CPU locally on the pipeline interpreter
  with the file run alone, and the test asserts under 1.0 s.
- **SC-004**: the report names `status --line` in the 15 ms scenario (US3.2).

## Assumptions

- Builder: `status --line` still imports `wuwei.registry` on a config parse without a cache, because `workspace.load_config` validates the adapters through it. Only `wuwei.integrity` stops importing it; `wuwei.cruise` and `wuwei.sessions` stay off the line.
- Builder: T001, T012, T013 and T023 (profiling rounds for SessionStart, PreToolUse and push beyond the planned cuts) were not run under the owner's time limit; the latency job on the pull request gives the runner figures.

- The runner cannot be run from here. Local acceptance is SC-002 and SC-003; SC-001 is
  confirmed by the latency job on the pull request and on main. If the job shows a probe
  above its SC-001 figure, the builder reports it rather than touching a budget.
- "Last green run" is the last successful run of the Tests workflow on main (the latency
  job is `continue-on-error`, so a red latency job inside a successful run still provides
  figures). Pull requests compare against main too.
- The per-probe margin pin is the report's margin check, run in the job on the run's own
  artifact and covered by `tests/test_latency_report.py`; a pytest test reading the
  artifact would depend on test order inside `-k latency`.
- "Moved most" uses the relative change of the budgeted measure, so a 15 ms rise on a
  30 ms probe outranks a 20 percent rise on the heartbeat tick.
- No guard, refusal or posture behaviour changes (#530): this item only removes work and
  adds an informational report. No new rule, so the 9.2 invariant table does not change.
  No planner action changes (#551).
- The outward keyword patterns are cached per process (`functools.lru_cache` keyed on the
  keyword tuple): a hook process lives one call, a long command reads one config.
- A cache of the `events.jsonl` scan is out of scope: the cuts come from work removed from
  the path, and a cache would make the probe measure a hit path.
