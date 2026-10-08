# Tasks: Day pace (careful, steady, fast)

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (items `A` to `I`, goals `G-1` and `G-2`, repository
`acme/widget`, paths under `cli/wuwei/`). Host fixture for saturation: ten cores, load
average 34.0, a last suite of 14 minutes (the 2026-10-08 measurement). Reuse the fixture
day in `tests/fakes/day.py`, the item worktree and fake ports of `tests/test_commit_push.py`,
the plan helpers of `tests/test_plan.py` and the launch-set helpers of
`tests/test_parallel_dispatch.py`; monkeypatch `os.getloadavg` and `calibrate.host` rather
than reading the real host. Run only the touched test files.

Precondition: bring the branch up to `main` first (the worktree base b6daa42 predates #567,
merged as PR #577). Then #567's `dispatch.depth`, `step_zero` and `metrics.cycles` exist; if
not, stop and report.

## Phase 1: the pace value (FR-001, FR-002)

- [X] T001 Test in `tests/test_pace.py`: `pace.current` returns the day's `pace`, else
  `[pace] default`; `pace.label` maps `Approve`, `Approve (Recommended)`, `Approve at fast`
  and `fast` and raises `ValueError` naming the three paces for `Change something` and
  `quick`. Test in `tests/test_state.py`: a generic write of `pace` or `pace_card` is
  refused naming its producer. Test in `tests/test_config_writer.py` (or the config schema
  test that covers defaults): `[pace] default` defaults to `steady`, rejects `quick`;
  `repos.tests` defaults to empty.
- [X] T002 Implement `PACES`, `current`, `label` in `cli/wuwei/pace.py`; the producers in
  `cli/wuwei/state.py`; the schema keys in `cli/wuwei/workspace.py`.

## Phase 2: the tier rule (FR-008, FR-009, US2)

- [X] T003 Test in `tests/test_pace.py`: `pace.adjust` table: steady returns its input;
  careful raises light to standard and a guard to full; fast raises a guard to full,
  returns depth light for a measured standard tier with no guard and not flagged, and
  returns depth standard when flagged or unmeasured; no combination returns a tier below
  its input.
- [X] T004 Implement `adjust` in `cli/wuwei/pace.py`.
- [X] T005 Test in `tests/test_dispatch.py` (with #567's fake diff helpers): at pace fast a
  standard diff touching `cli/wuwei/report.py` gives `tier: standard`, roles arch, quality,
  security, `depth: light`, and `dispatch.depth(row, gate=True) == 'light'`; touching
  `cli/wuwei/guards/x.py` gives `tier: full`, `depth: full` and the reason `pace fast:
  cli/wuwei/guards/x.py matches guards/*`; a row with `trust_surface` stays depth standard;
  at careful a light diff gives standard with reason `pace careful`; at steady every
  existing tier case returns the same record as before plus `depth` equal to `tier`.
- [X] T006 Implement the `pace.adjust` call and `record['depth']` in `dispatch.tier`, the
  `gates.depth` preference in `dispatch.depth`, and the depth switch in `dispatch.classes`
  (`cli/wuwei/dispatch.py`).
- [X] T007 Test in `tests/test_brief.py`: at pace fast a builder brief for a plain standard
  diff has `Depth: light` and `items.A.depth == 'light'`. Test in `tests/test_dispatch.py`:
  `wuwei sweep classes` prints `Depth: light; no class sweep` for that item. Test in
  `tests/test_dispatch.py`: after a FIX on that item at fast, the delta seat's feedback is
  the #567 re-read text, and a full item keeps the delta review text.
- [X] T008 Implement the depth reads in `cli/wuwei/brief.py` (`write`),
  `cli/wuwei/guards/verdict.py` (`_light`) and `cli/wuwei/commands/sweep.py` (`classes`).

## Phase 3: checks and push evidence (FR-010, FR-011, US1 scenario 4)

- [X] T009 Test in `tests/test_fast_checks.py`: `fast_checks.commands` returns the
  `fast_checks` at steady; `fast_checks + [tests]` at careful; at fast with `repos.tests =
  "python3 -m pytest -q"` and a diff changing `tests/test_a.py` (present) and
  `tests/test_gone.py` (deleted) returns `["python3 -m pytest -q tests/test_a.py"]`; at fast
  with no test file changed, an empty `tests` or an unreadable diff returns the
  `fast_checks`. `record` stores `seconds` on each record and runs the pace's commands.
- [X] T010 Implement `commands` and the `record` change in `cli/wuwei/fast_checks.py`.
- [X] T011 Test in `tests/test_build.py`: at pace fast `wuwei build check` completes when
  the touched-test command passed and does not report incomplete checks for the configured
  `fast_checks`.
- [X] T012 Implement the `commands` refresh in `check` in `cli/wuwei/commands/build.py`.
- [X] T013 Test in `tests/test_commit_push.py`: at pace fast a push whose HEAD has a passing
  touched-test record and no `fast_checks` record exits 0; at steady the same push gets
  today's fast-check message (and under strict today's refusal); at careful a missing suite
  record gets the fast-check message naming the suite command.
- [X] T014 Implement the `commands` loop in `fast_evidence` in
  `cli/wuwei/guards/commit_push.py`.
- [X] T015 Test in `tests/test_brief.py`: the builder brief has the `Checks:` line for each
  pace, including the not-configured wording when `repos.tests` is empty.
- [X] T016 Implement the `Checks:` line in `cli/wuwei/brief.py` `write`.

## Phase 4: host and seats (FR-012, FR-013, US3)

- [X] T017 Test in `tests/test_calibrate.py`: `calibrate.host` returns `load` from
  `os.getloadavg` (monkeypatched to 34.0) and None when it raises `OSError`, plus
  `per_seat_tokens` and `used_tokens` (None without a budget), and the text names the load.
- [X] T018 Implement the fields in `cli/wuwei/calibrate.py` `host`.
- [X] T019 Test in `tests/test_pace.py`: `pace.seats` gives CAP minus one (at least 1) and
  bound `pace careful` at careful; at fast with load 34.0 and 10 cores the same cap, bound
  `load` and the hold reason; at fast with load 3.0, at steady, or with load None, the
  limits unchanged and no hold.
- [X] T020 Implement `seats` in `cli/wuwei/pace.py`.
- [X] T021 Test in `tests/test_parallel_dispatch.py`: at pace fast with the saturated host
  every launching entry of `launch_set` is `wait` with the hold reason and day state has
  `cap_bound == 'load'`; at careful with CAP 4 at most 3 builders are planned; at steady the
  existing launch-set cases are unchanged. Test in `tests/test_agent_launch.py` (or the file
  that covers the launch guard): the guard's result for a builder launch is the same at
  every pace.
- [X] T022 Implement the `pace.seats` call and the hold in `dispatch.launch_set`
  (`cli/wuwei/dispatch.py`).
- [X] T023 Test in `tests/test_signal_status.py`: `status.line` shows `pace fast` and `held
  by load` for a fast day bound by load, `pace careful` for careful, and no pace token for
  steady or a day without `pace`.
- [X] T024 Implement `pace` in `snapshot` and the tokens in `_groups`
  (`cli/wuwei/commands/status.py`).

## Phase 5: the advice and the gate (FR-003 to FR-007, US1, US2, US3 scenarios 2, 4, 5)

- [X] T025 Test in `tests/test_pace.py`: `pace.advise` on 7 light and 2 standard candidates
  (lead tiers), goal G-2 dated two days ahead, an idle 10-core host: pace fast, line 1
  `9 items, 7 light, 2 standard, G-2 due <date>: fast, <n> seats, expected close <HH:MM>`,
  line 2 ending `binding: queue`; two candidates with `paths` under `cli/wuwei/guards/`:
  careful, `2 items touching guard code: careful`; the fast queue on the saturated host:
  steady, binding host, `fast unlocks when the load average falls below 10`; a budget that
  covers 6 of 9: `budget reaches 6 of 9 items at fast: advised against`, binding budget, pace
  unchanged; `[pace] default = "steady"` with a fast advice: the third line `Your default is
  steady; the advice is fast (binding: queue)`; no cycle history uses the fallbacks;
  `pace.host_line` shows `last suite 14 min` from a prior day's `repos.tests` record with
  `seconds: 840`, `last suite unmeasured` without one, and `load unmeasured` when the load
  is None.
- [X] T026 Implement `predict`, `guard_items`, `advise` and `host_line` in
  `cli/wuwei/pace.py`.
- [X] T027 Test in `tests/test_plan.py`: `_proposal` accepts candidate `paths` as a list of
  strings and refuses another type; `plan.propose` writes `pace`, `pace_reasoning` and
  `pace_advice` to `proposal.json` and the pace lines under `## Gate proposal` in `plan.md`;
  `plan.gate_widget` options are `Approve`, `Approve at steady`, `Approve at careful`,
  `Change something` for a fast advice, the Approve description carries the reasoning lines,
  and the record ends with `--pace "<label>"`.
- [X] T028 Implement `_proposal`, `propose` and `gate_widget` in `cli/wuwei/plan.py`; update
  the existing label assertion at `tests/test_plan.py:366`.
- [X] T029 Test in `tests/test_plan.py`: `plan approve --pace "Approve"` records the
  recommended pace and the `plan.approved` payload carries `pace`, `recommended`, `wish`;
  `--pace "Approve at careful"` records careful; `--pace "Change something"` exits 2 and
  records nothing; no `--pace` on a proposal without `pace` records the config default;
  `wuwei plan set pace=careful` writes state and a `pace.set` event with `previous`; `wuwei
  plan set pace=quick` exits 2 naming the paces; `wuwei plan set A spec=required` still
  works.
- [X] T030 Implement `approve(pace_label=...)` and `set_pace` in `cli/wuwei/plan.py`, and
  `--pace` and the `set` parsing in `cli/wuwei/commands/plan.py`.
- [X] T030a Test in `tests/test_protect_state.py`: `bin/wuwei plan set pace=fast` from the
  registered planner session under guarded passes; from a seat it returns the existing
  `plan set` owner reason; under strict from the planner it returns the host-terminal
  reason; `plan set pace=fast; rm x` and `plan set pace=$X` do not pass.
- [X] T030b Implement `_planner_pace_set` and its check in
  `cli/wuwei/guards/protect_state.py`.
- [X] T031 Test in `tests/test_next.py` and `tests/test_docs.py`: the gate THEN text tells
  the planner to run the record command on any Approve option; the off-path check accepts
  `wuwei plan approve ... --pace "Approve at fast"` against the named record command.
- [X] T032 Implement the `THEN['gate']` text in `cli/wuwei/commands/next.py`.

## Phase 6: `wuwei pace` (FR-014, US4 scenario 3)

- [X] T033 Test in `tests/test_pace.py`: `wuwei pace` on an approved fast day prints `Pace:
  fast`, an `Advice:` line, an `Inputs:` line with host, wish and budget, and a `Balance:`
  line, and exits 0; on a workspace whose state cannot be read it exits 2 with the reason.
  Test in `tests/test_cli_known_command.py`: `pace` is listed read-only.
- [X] T034 Implement `cli/wuwei/commands/pace.py`, its registration and `READ_ONLY` in
  `cli/wuwei/commands/__init__.py`.

## Phase 7: measurement and the default card (FR-016 to FR-018, US5)

- [X] T035 Test in `tests/test_metrics.py`: over fixture days (five at steady, five at fast,
  items merged on each) `metrics.cycles` rows carry the day's pace and `metrics.by_pace`
  returns days, merged, `cycle_by_tier`, escaped (one fast item named by a later builder
  brief) and cards (`decision_routes`) per pace; with no day carrying `pace` it is
  unmeasured; `collect` exposes `by_pace`.
- [X] T036 Implement `pace` in `cycles`, `by_pace` and the `collect` key in
  `cli/wuwei/metrics.py`.
- [X] T037 Test in `tests/test_report_retro.py`: the report has `## Pace` with `Pace: fast
  (recommended fast, binding queue)` and one line per pace, plus the `costs escaped
  defects` line for fast in the fixture; the retro has the same lines and `Pace proposal:
  D-n` when a pace card is open.
- [X] T038 Implement `pace_lines` and the section in `cli/wuwei/report.py` and the retro
  lines in `cli/wuwei/retro.py`.
- [X] T039 Test in `tests/test_pace.py`: `pace.propose_default` with ten fixture days at two
  paces writes one card whose option titles are `pace.default = "steady"` and
  `pace.default = "fast"`, recommends the pace with fewer escaped per merged item, names the
  costly pace in its context, records `pace_card`; a second call within ten days writes
  nothing; nine days or one pace writes nothing; `wuwei decision show D-n --widget` for the
  card uses the `config set ... --from-card` record.
- [X] T040 Implement `propose_default` in `cli/wuwei/pace.py` and its call beside
  `cruise.propose` in `plan.propose`.

## Phase 8: invariants, design and docs (FR-019, FR-020)

- [X] T041 Test in `tests/test_invariants.py`: add `pace_rule` and the three rows (I15 no
  pace lowers a floor, I16 no pace changes who decides, I17 fast merges only at green
  required checks; I16 compares `cruise.level` over `cruise.CLASSES` and `decision.route`
  across paces and runs `plan set pace=fast` through `protect_state` from the planner and
  from a seat) to `INVARIANTS` and `READS` (I15 and I17 `()`, I16 `(0,)`), each rule cached; run it before the design rows exist and see
  `test_table_matches_the_checks` fail; add a `BROKEN` case that monkeypatches
  `pace.adjust` to return a lower tier and see the walk catch it.
- [X] T042 Add rows I15 to I17 to design 9.2, the "Pace" paragraph and table to design 5.2
  and the per-pace line to 5.6 in `docs/specs/2026-09-24-wuwei-design.md`.
- [X] T043 Test in `tests/test_docs.py`: `docs/site/concepts.md` names the three paces,
  `daily.md` shows the gate card's pace lines and `plan set pace=`, `configuration.md`
  lists `[pace] default` and `repos.tests`, `reference.md` lists `wuwei pace`, `plan approve
  --pace` and `plan set pace=`.
- [X] T044 Write those docs in `docs/site/concepts.md`, `daily.md`, `configuration.md`,
  `reference.md`.

## Phase 9: finish

- [X] T045 Run the touched test files (`tests/test_pace.py`, `test_dispatch.py`,
  `test_brief.py`, `test_fast_checks.py`, `test_build.py`, `test_commit_push.py`,
  `test_calibrate.py`, `test_parallel_dispatch.py`, `test_signal_status.py`, `test_plan.py`,
  `test_next.py`, `test_docs.py`, `test_cli_known_command.py`, `test_metrics.py`,
  `test_report_retro.py`, `test_state.py`, `test_protect_state.py`, `test_invariants.py`) and check every written
  file for em-dashes and emojis.

## Build notes

Tests for most tasks live in `tests/test_pace.py`, which reuses the fixtures of
`test_dispatch`, `test_process_depth`, `test_brief`, `test_commit_push`, `test_build_next`,
`test_calibrate` and `test_parallel_dispatch`; the plan tests are in `tests/test_plan.py` and
the invariant rows in `tests/test_invariants.py`. T021's launch-guard check is I17: the walk
fails when `guards/agent_launch.py`, `guards/pr.py` or `merge.py` reads the pace.
