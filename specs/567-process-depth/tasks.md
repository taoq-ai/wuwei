# Tasks: Process depth follows the tier

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (items `A`, `B`, repository `acme/widget`, paths under
`cli/wuwei/`). Reuse the fixture day in `tests/fakes/day.py`, the brief helpers of
`tests/test_brief.py`, the verdict texts of `tests/test_verdict.py` and the record helpers of
`tests/test_decision_classes.py`; no new fixture framework.

## Phase 1: one depth (FR-001)

- [X] T001 Test in `tests/test_dispatch.py`: `dispatch.depth` returns `gates.tier` when
  recorded, else `depth`, else `standard`; with `gate=True` it ignores `depth` (a row with
  `depth: light` and no gate tier is `standard`); `dispatch.tier` returns the same record as before
  for a light diff, a trust-path diff, an unreadable diff and a floor (pin the existing cases
  through the extracted `_changes`).
- [X] T002 Implement `depth` and extract `_changes` from `tier` in `cli/wuwei/dispatch.py`.

## Phase 2: the class sweep command (US1, US2, FR-005)

- [X] T003 Test in `tests/test_dispatch.py`: `dispatch.classes` lists no class at light, only
  `AUTH` and `ERR` (and any other matching class) for a standard diff touching
  `cli/wuwei/guards/x.py`, every class at full; an unreadable diff raises `ValueError`.
- [X] T004 Implement `CLASS_PATHS` and `classes` in `cli/wuwei/dispatch.py` (globs through
  `merge.matched`).
- [X] T005 Test in `tests/test_dispatch.py`: `wuwei sweep classes <worktree>` prints `Depth:
  light; no class sweep` and exits 0 at light; prints `Depth: standard` then one `CLASS:
  paths` line per touched class at standard; exits 2 naming the reason for a path that is no
  item's worktree. Test in `tests/test_cli_known_command.py` passes with `sweep classes`
  listed as read-only.
- [X] T006 Implement the `classes` subcommand in `cli/wuwei/commands/sweep.py` and add
  `'sweep classes'` to `READ_ONLY` in `cli/wuwei/commands/__init__.py`.

## Phase 3: the Depth line in briefs and prompts (US1, US2, FR-002 to FR-004)

- [X] T007 Test in `tests/test_brief.py`: a builder brief on a light item has `Depth: light`
  with the skip list and the `wuwei sweep classes <worktree>` command, and state holds
  `items.A.depth == "light"`; on a standard item `Depth: standard` without the skip list.
  Test in `tests/test_state.py`: a generic write of `items.A.depth` is refused naming
  `wuwei brief`.
- [X] T008 Implement `depth_line` and the builder branch in `cli/wuwei/brief.py` `write`; add
  `'depth': 'wuwei brief'` to `_producer_error` in `cli/wuwei/state.py`.
- [X] T009 Test in `tests/test_brief.py`: a gate brief for a standard item whose diff touches
  `cli/wuwei/guards/x.py` has `Depth: standard; step zero: run (cli/wuwei/guards/x.py matches
  guards/*)`; one touching only `cli/wuwei/report.py` has `step zero: skip (no guard code or
  trust path in the diff); write Mutation: skipped (depth standard)`; a path in the repo's
  `trust_paths` runs step zero; light has the light skip line; full has `step zero: run`.
- [X] T010 Implement `step_zero` in `cli/wuwei/dispatch.py` and the gate branch of the
  `Depth:` line in `cli/wuwei/brief.py` `write`.
- [X] T011 Test in `tests/test_brief.py`: `launch_prompt` ends its mandate block with the
  brief's `Depth:` line; a brief with no `Depth:` line gives the prompt of today.
- [X] T012 Implement the `Depth:` read in `launch_prompt` in `cli/wuwei/brief.py`.

## Phase 4: the light verdict and retro (US1, FR-006 to FR-008)

- [X] T013 Test in `tests/test_verdict.py`: `lint(..., light=True)` accepts `Verdict: PASS`,
  `Head: abc1234`, `Findings: none` for quality and arch; still refuses a FIX without a
  finding, a finding without `file:line`, two `Verdict:` lines, a missing `Head:`, a PASS
  with `blocks: yes`, and a partial retro note; `light=False` keeps every current refusal.
- [X] T014 Implement the `light` keyword in `verdict.lint` in `cli/wuwei/verdict.py`.
- [X] T015 Test in `tests/test_verdict.py`: `lint_file` on `decisions/gate-<seat>.md` accepts
  the three-row verdict when the seat's item has `gates.tier == "light"` and refuses it when
  the tier is standard, when only the builder's `depth` is light (no gate tier recorded),
  when the seat is unknown, and when there is no workspace.
- [X] T016 Implement `verdict.light(path, data)` and pass it from `lint_file` in
  `cli/wuwei/verdict.py`.
- [X] T017 Test in `tests/test_pr_guards.py`: the PR raise gate check accepts recorded light
  verdicts in the three-row shape and still refuses them for a standard item; test in
  `tests/test_obligations.py`: the verdict obligation is met by a light verdict at the PR
  head.
- [X] T018 Pass `light` in `_recorded_gates` in `cli/wuwei/guards/pr.py` and in
  `_gate_recorded` (now taking `data`) in `cli/wuwei/obligations.py`.
- [X] T019 Test in `tests/test_retro.py`: SubagentStop `check_retro` for a seat of a light
  item with no retro lines records `retro.captured` with `none` on every field and exits 0;
  the same seat of a standard item records `retro.gap` and exits 1 as today; a light seat
  with a partial note records `retro.gap`.
- [X] T020 Implement the light branch in `check_retro` in `cli/wuwei/guards/verdict.py`.
- [X] T020a Review F3: a builder seat with no recorded gate tier judges light from the live
  diff (`dispatch.tier`), not the brief-time prediction; test in `tests/test_process_depth.py`.

## Phase 5: the light re-read (US1, FR-009)

- [X] T021 Test in `tests/test_dispatch.py`: after a light quality FIX and its fix round,
  `dispatch next` returns a `continue` for the same seat whose `feedback` starts `Re-read:`,
  names the `Verdict:` and `Head:` lines and does not contain `Delta review`; a standard item
  keeps the `Delta review` feedback; `receive --round delta` records the re-read.
- [X] T022 Implement `_delta_feedback(first, light)` and pass it from `_seats` in
  `cli/wuwei/dispatch.py`.

## Phase 6: Routine records in one line (US3, FR-010)

- [X] T023 Test in `tests/test_decision_classes.py`: a Routine record taken under mandate
  prints exactly one line from `wuwei decision show D-n` (id, `Routine`, question, option,
  the `--full` command); `--full` prints the record text; a Consequential record under
  mandate and an owner-routed record print as today; `--widget` is unchanged.
- [X] T024 Implement the one-line branch in `show` in `cli/wuwei/commands/decision.py`.

## Phase 7: cycle time per tier (US4, FR-011)

- [X] T025 Test in `tests/test_metrics.py`: with recorded events (`plan.approved` at 09:00,
  sentinel `brief written` and `seat launched` at 09:20, `gate.received` at 09:40, a
  `merged` phase change at 10:00, `gates.tier` light), `collect` has `cycle_minutes == {"A":
  60.0}`, `gate_minutes == {"A": 20.0}` and `cycle_by_tier == {"light": {"median_minutes":
  60.0, "items": 1, "target": 60}}`; a `plan.added` start works; an item approved on one day
  and merged the next spans both; no merged item gives `unmeasured` for all three.
- [X] T026 Implement `CYCLE_TARGETS`, `cycles` and the three keys in `collect` in
  `cli/wuwei/metrics.py`.
- [X] T027 Test in `tests/test_report_retro.py`: the report has `## Cycle time` with the tier
  line and the item line at brief and standard verbosity; the retro names the tier whose
  median moved most between the previous and the current ISO week, and says unmeasured when
  no tier merged in both.
- [X] T028 Implement the section in `cli/wuwei/report.py`, `cycle_moved` in
  `cli/wuwei/metrics.py` and its line in `cli/wuwei/retro.py`.

## Phase 8: the fixture days (US1, SC-001, SC-002)

- [X] T029 Test in `tests/test_path_day.py`: a light variant of the day (repo floor `light`
  in the fixture config, lead tier `light` in the proposal) closes through `wuwei next`; the
  builder brief has `Depth: light`; the fake sentinel writes the three-row verdict when its
  brief says `Depth: light` (change `tests/fakes/day.py` `Runtime.finish` to read the brief's
  `Depth:` line); the quality FIX is continued with `Re-read:` feedback; `cycle_by_tier`
  light median is under 60. The existing standard day asserts the standard median under 180.
- [X] T030 Fix whatever the light day exposes in the modules above (no new behaviour).

## Phase 9: charters, docs, suite (FR-012, FR-013, SC-003)

- [X] T031 Test in `tests/test_charters.py`: `_common.md` names the design 5.3 depth table
  and the brief's `Depth:` line for step zero; `builder.md` names `wuwei sweep classes`;
  `sentinel-quality.md` says when step zero applies; the line count of `_common.md` plus
  `builder.md` is not above the count on main (pin the number in the test).
- [X] T032 Edit `charters/_common.md`, `charters/builder.md`, `charters/sentinel-quality.md`,
  `charters/sentinel-arch.md`, `charters/sentinel-security.md` (bump versions), then run
  `bin/wuwei agents build`; confirm `tests/test_agents.py` passes and no grant changed.
- [X] T033 Amend `docs/specs/2026-09-24-wuwei-design.md` 5.3 (depth table) and the process
  metrics; update `docs/site/concepts.md`, `docs/site/daily.md`, `docs/site/reference.md`.
- [X] T034 Run the full suite in the background to a file and wait; fix failures; check every
  written file for em-dashes and emojis.
