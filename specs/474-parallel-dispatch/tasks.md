# Tasks: the day starts in parallel

**Input**: `specs/474-parallel-dispatch/` (spec.md, plan.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. No absolute local paths, engagement names, emojis or
em-dashes in any file. Every new refusal or reason names a next step (`tests/test_reasons.py`).

## Phase 1: US1, CAP proposed from the calibrated host

- [X] T001 Test, `tests/test_agent_launch.py`: an admitted launch's `seat launched` event
  payload carries `free_mib` (the patched free memory in MiB) and `running` (the running
  seat count before it) (spec US1 scenario 6). Run `python -m pytest -q
  tests/test_agent_launch.py -k free_mib` (fails: payload has only name and item).
- [X] T002 Implement the payload fields in `cli/wuwei/guards/agent_launch.py` `_check` (plan
  Design 1, first bullet). Rerun T001; pass.
- [X] T003 Test, `tests/test_agent_launch.py`: a builder launch is judged against the day's
  approved `cap`: config `cap = 1`, day state `cap = 3` (set before approval through the
  generic owner field, or by `plan approve` of a CAP 3 proposal), two builders running: the
  third is admitted, and with three running the next is refused naming `CAP 3` (spec US3
  scenario 4). Run `python -m pytest -q tests/test_agent_launch.py -k day_cap` (fails: the
  guard refuses at config cap 1).
- [X] T004 Implement `data['cap']` at `cli/wuwei/guards/agent_launch.py:182-183` (plan Design
  1, second bullet); move any existing builder-cap test that set only config cap to set the
  day cap. Rerun T001, T003 and `tests/test_agent_launch.py`; pass.
- [X] T005 Test, `tests/test_metrics.py`: `metrics.seat_cost` returns the median drop per
  running seat from `seat launched` rows (baseline 10240 at running 0; 7168 at running 1 and
  4096 at running 2 give 3072), skips rows without `free_mib`, and is `unmeasured` with no
  baseline or no sample; `metrics.collect` has `seat_cost_mib`. Run `python -m pytest -q
  tests/test_metrics.py -k seat_cost` (fails: no function).
- [X] T006 Implement `seat_cost` and the `collect` key in `cli/wuwei/metrics.py` (plan Design
  2). Rerun T005; pass.
- [X] T007 Test, `tests/test_calibrate.py`: with a `fakes.host.Fake` free memory and a patched
  `os.cpu_count` (add both to the calibrate port fixture so no existing test runs the real
  host adapter): `calibrate.host` gives cap 3 for 8 cores, 10240 MiB free, floor 1024,
  `host.seats = 4` and a day with seat cost 3072; cap 2 with `host.seats = 2`; `seat_source`
  `default` and `seat_mib` 1024 with no measured day; `{'unmeasured': ...}` when the port
  fails or `cpu_count` is None. Through `main(['calibrate'])`: calibration.md has the
  `## Host` section; with `cap = 1` present the output says "Config differs; edit by hand:
  cap" and config.toml is unchanged; with `cap` absent the proposal diff adds `cap = 3`; an
  unmeasured host exits 2 with the reason on stderr. `config promote` with a confirming stub
  lists the same cap line (spec US1 scenarios 1 to 5). Run `python -m pytest -q
  tests/test_calibrate.py -k host` (fails: no `calibrate.host`).
- [X] T008 Implement `SEAT_MIB`, `host`, the `host` parameter of `proposal`, `propose` and
  `report` in `cli/wuwei/calibrate.py` (plan Design 3). Rerun T007; the unit cases pass.
- [X] T009 Implement the calibrate command wiring in `cli/wuwei/commands/calibrate.py` (`run`,
  `record`) and the `host` parameter of `proposal` plus the `promote` call in
  `cli/wuwei/commands/config.py` (plan Design 3). Rerun T007 and `tests/test_calibrate.py`;
  pass.

## Phase 2: US2, seats per goal in the plan and the gate question

- [X] T010 Test, `tests/test_plan.py`: with goals G-1 and G-2, CAP 3 and ranked A (G-1), B
  (G-2), C (G-1), D (G-2): plan.md has `Seats per goal: 3 seats: G-1 2, G-2 1 (CAP 3)` and
  proposal.json has `seats`; `plan gate` Approve description contains `3 seats: G-1 2, G-2 1
  (CAP 3)` and the Change something description names seats per goal; a lead `seats` of
  `{"G-1": 1, "G-2": 2}` is shown instead; an unknown goal, a 0 count, a bool or a total
  above cap exits 2 with the plan JSON contract; no candidates gives `0 seats (CAP 3)`;
  `plan approve` writes `goal_seats`; `plan template` prints the configured `cap` (spec US2
  scenarios 1 to 4 and 6). Run `python -m pytest -q tests/test_plan.py -k seats` (fails: no
  seats line).
- [X] T011 Test, `tests/test_state_allowlist.py`: a generic write of `goal_seats` is refused as
  reserved and names `wuwei plan approve` (spec US2 scenario 5). Run `python -m pytest -q
  tests/test_state_allowlist.py -k goal_seats` (fails: producer named as "its dedicated
  command").
- [X] T012 Implement `running_by_goal`, `goal_split` and the `goal_seats` producer in
  `cli/wuwei/state.py`; `goal_seats`, `seats_text`, the `_proposal` check, `propose`,
  `gate_widget` and `approve` changes in `cli/wuwei/plan.py`; the template `cap` in
  `cli/wuwei/commands/plan.py` (plan Design 4). Update pins of the old `CAP N` gate text in
  `tests/test_plan.py` and the one-gate-question tests. Rerun T010, T011, `tests/test_plan.py`
  and `tests/test_state_allowlist.py`; pass.

## Phase 3: US3 and US4, the launch set and gates together

- [X] T013 Test, `tests/test_dispatch.py`: `dispatch next` with neither an item nor `--all`,
  or with both, exits 2 naming both forms; `launch_set` on recorded day state orders gate
  items, then build items, then planned items; starts stop at CAP and the rest are `wait`
  naming CAP; planned items within their goal's `goal_seats` share come first, the rest
  fill CAP in queue order; an item whose gate seats exceed the free `host.seats` is one
  `wait` naming `host.seats` (spec US4 scenario 2); a `next_step` refusal is a `refused`
  entry and the command exits 1 with the full set on stdout; a day without `goal_seats`
  uses queue order; a carried item is skipped (spec US3 scenario 5, edge cases). Run
  `python -m pytest -q tests/test_dispatch.py -k launch_set` (fails: no `--all`).
- [X] T014 Test, new `tests/test_parallel_dispatch.py`, fixture day through the hooks
  (`tests/fakes/day.py`, goals G-1 and G-2 written in the test): config `cap = 3`, a CAP 3
  proposal with four items across two goals, approval of all four; `dispatch next --all`
  lists three `start` entries and D as `wait`; after the three builder briefs it lists three
  `launch` entries; the three Agent PreToolUse payloads pass with three builder seats
  running; a fourth builder PreToolUse is refused naming CAP 3; `next` names D as waiting and
  the earliest-started builder seat (spec US3 scenarios 1 and 2). With `cap = 1`: one
  `start`, a second builder launch refused (US3 scenario 3). Gate: one item at the gate with
  three gate briefs, three sentinel PreToolUse payloads before any SubagentStop leave three
  running sentinel seats; after the first and second receipt `dispatch next` returns `gates`
  and the phase is `gate`; after the third it returns `raise` (US4 scenario 1). Run `python
  -m pytest -q tests/test_parallel_dispatch.py` (fails: no `--all`, and `next` names no
  waiting item).
- [X] T015 Implement `approved(data)` in `cli/wuwei/commands/next.py` (extracted, `step` uses
  it), `launch_set` in `cli/wuwei/dispatch.py` and the `--all` form in
  `cli/wuwei/commands/dispatch.py` (plan Design 5). Rerun T013 and the launch-set parts of
  T014; pass.
- [X] T016 Test, `tests/test_next.py`: on an approved day with planned items and free CAP the
  row is `dispatch` with command `wuwei dispatch next --all` and the startable count (spec
  US5 scenario 2); at CAP the `wait` row names the first waiting item and the running
  builder seat with the earliest `started_at`. Run `python -m pytest -q tests/test_next.py
  -k seats` (fails: old dispatch command, no waiting item).
- [X] T017 Implement the dispatch and wait rows in `cli/wuwei/commands/next.py` `step` (plan
  Design 6); update the sample line in `docs/site/daily.md` and existing pins of
  `wuwei worktree add` as the dispatch command. Rerun T014, T016 and `tests/test_next.py`;
  pass.

## Phase 4: US5, running seats per goal on the status line and the board

- [X] T018 Test, `tests/test_signal_status.py` and `tests/test_board_mcp.py`: an approved day
  with CAP 3 and running builder seats for A (G-1) and B (G-2) shows `seats 2 of CAP 3 (G-1
  1, G-2 1)` on `status --line` and in the board text; before approval no seats part (spec
  US5 scenario 1). Run `python -m pytest -q tests/test_signal_status.py
  tests/test_board_mcp.py -k seats` (fails: no seats part).
- [X] T019 Implement `snapshot` and `line` in `cli/wuwei/commands/status.py` (plan Design 6).
  Rerun T018, `tests/test_signal_status.py`, `tests/test_board_mcp.py` and
  `tests/test_dashboard.py`; pass.

## Phase 5: skill, charter and docs

- [X] T020 Test, `tests/test_parallel_dispatch.py`: `skills/wuwei-plan/SKILL.md` names `wuwei
  dispatch next --all` and says the set's Agent launches go in one message and run
  concurrently; `docs/site/concepts.md` has a `### Seats per goal` heading;
  `docs/site/configuration.md` `cap` row names calibrate and the morning gate. Run `python
  -m pytest -q tests/test_parallel_dispatch.py -k docs` (fails: none of the text exists).
- [X] T021 Implement the skill changes in `skills/wuwei-plan/SKILL.md` (plan Design 7). Rerun
  T020 and `tests/test_skill_evals.py`; pass.
- [X] T022 Implement the lead charter sentence in `charters/lead.md`, regenerate
  `agents/lead.md` with `python3 -P -m wuwei agents build`, bump the charter version if the
  charter tests require it. Run `python -m pytest -q tests/test_agents.py
  tests/test_charters.py`; pass.
- [X] T023 Implement the docs in `docs/site/concepts.md`, `docs/site/daily.md` and
  `docs/site/configuration.md` (plan Design 7). Rerun T020 and `tests/test_docs.py`; pass.

## Phase 6: Polish

- [X] T024 Run `python -m pytest -q`; everything passes. Grep the changed files for
  em-dashes, emojis and absolute local paths and remove any.
