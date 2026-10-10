# Tasks: the seat limit is not read from host memory when seats are subagents of one process

**Input**: `specs/658-seats-not-memory/spec.md`, `specs/658-seats-not-memory/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Test command: `python -m pytest -q` from the repository root.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 - subagent seats keep a steady limit (P1)

### Tests first

- [X] T001 [US1] `tests/test_calibrate.py`: add `test_runtime_rule` for `calibrate.processes`:
  default config with `{}` is False; `{'builder': {'runtime': 'claude', ...}}` False;
  `'none'` False; a `codex` builder with Claude sentinels True; `adapters.runtime = "codex"`
  with `{}` True; a non-dict policy and a non-dict row count as empty; a Codex
  `gates.second_opinion` alone is False. Run it; it fails (`processes` does not exist).
- [X] T002 [US1] `tests/test_calibrate.py`: add `test_subagent_seats_never_read_memory`
  (spec US1 scenarios 1 and 3, SC-001): default runtime, `host.seats = 6`, `cpu_count` 10;
  for free memory 9216, 5120, 7168, 9216, 3072 MiB set on the `ports['host']` fake,
  `pace.seats('steady', calibrate.host(root, config, policy={}))` is `(6, 'host.seats', None)`
  every time and the fake recorded no `free_memory` call; the text is
  `cap 6 (host.seats): subagent runtime, free memory not read`. With
  `host.seats = 0`: CAP 10, seats 10, text ends `host.seats unset, 10 cores`. With the free
  memory port failing: still CAP 6, no `unmeasured` key. Also call without `policy` and with
  no day state: same result (reads the default empty policy). Run it; it fails (no `policy`
  parameter; without it CAP follows memory: 6, 4, 6, 6, 2, bound `host`).
- [X] T003 [US1] `tests/test_calibrate.py`: extend
  `test_calibrate_measures_the_host_and_never_proposes_cap` (or add a sibling): on the
  default runtime the `## Host` section has `cores:` and `derived: cap ... (host.seats)` and
  no `free memory:` or `seat cost:` line. Run it; it fails.
- [X] T004 [US1] `tests/test_parallel_dispatch.py`: rewrite
  `test_launch_guard_compares_with_the_cap_derived_at_launch` for the default runtime (US1
  scenario 4): with three running and 1 GiB free (exactly the floor), D's builder launch is
  admitted. Add a process-runtime twin (a `codex` builder in `seat_policy`) keeping today's
  refusal (`CAP 3`). Keep `test_memory_floor_equality_and_completed_seats` in
  `tests/test_agent_launch.py` as the floor proof. Run the rewrite; it fails (D is refused
  on memory).
- [X] T005 [US1] `tests/test_parallel_dispatch.py`: add `test_subagent_cap_is_host_seats`
  (US1 scenario 2): `host.seats = 6` in the day's config (append it where the fixture
  config has no `[host]` table, else edit that table), 3 GiB free on `day.memory`; after
  `approved` and `launch_set`, `day.data['cap'] == 6`, `cap_bound == 'host.seats'`, the
  `CAP:` line of `plan.md` is
  `CAP: cap 6 (host.seats): subagent runtime, free memory not read; host.seats 6`
  and `status --line` contains `seats 0/6 by host.seats`. Run it; it fails (CAP 2, bound
  `host`).
- [X] T006 [US1] `tests/test_signal_status.py`: with the `four_seats` data, `status.line` with
  `cap_bound: 'budget'` contains `seats 4/1 by budget (lead, `; with `cap_bound: ''` the
  token has no `by`; `status.full` first line is
  `WUWEI 1 building · seats 4/1 by budget (lead, arch, quality, security) · builders G-1 2`
  (no `bound budget`). Update `:966` to `:968` (`budget` leaves the moved list, `bound`
  stays) and `:1063`. Run them; they fail.

### Implementation

- [X] T007 [US1] `cli/wuwei/calibrate.py`: add `processes(config, policy)` and give `host`
  the `policy=None` parameter, the policy read inside the existing `try`, the subagent
  branch (no free-memory read, no seat-cost scan, fit `owner_seats or cores`, bound
  `host.seats`, the `measured` text) and the shared tail from `plan.md` Design; in
  `report`, print the memory lines only when `'free_mib' in host`. T001 to T003 pass.
- [X] T008 [US1] Pass the held policy at each caller (`plan.md` Callers table):
  `cli/wuwei/dispatch.py:396` and `:736`, `cli/wuwei/guards/agent_launch.py:185`,
  `cli/wuwei/commands/pace.py:15`, `cli/wuwei/plan.py:189` (`data.get('seat_policy')`).
  T004 passes; T005 passes except the line assertion.
- [X] T009 [US1] `cli/wuwei/commands/status.py`: the seats token gets `by <cap_bound>` in
  `_groups` (line 379); delete the `bound X` token in `full` (lines 416 and 417). T005 and
  T006 pass.

## Phase 2: User Story 2 - process seats use a smoothed memory estimate (P1)

### Tests first

- [X] T010 [US2] `tests/test_calibrate.py`: add `test_memory_rule_takes_the_median_of_five`
  (US2 scenarios 1 and 3, SC-002): `PROCESS = {'builder': {'runtime': 'codex', 'model': 'm'}}`,
  `cpu_count` 10, no reading today: 5120 MiB free (a reading of 4) yields CAP 4, bound
  `memory`, text `cap 4 (memory): 5 GB free, 1 GB per seat, 10 cores` (no median clause) and
  `reading == 4`. Then append four `cap.derived` events with `reading` 8, 4, 6, 8 via
  `state.append_event`: the same free memory yields CAP 6 and text starting
  `cap 6 (memory): median of 8, 4, 6, 8, 4; `. Recording a fifth reading 9 slides the
  window: text starts `cap 6 (memory): median of 4, 6, 8, 9, 4; `. A damaged today
  `events.jsonl` gives the current reading alone and a `warning:` clause. Run it; it fails
  (no median, bound `host`).
- [X] T011 [US2] `tests/test_parallel_dispatch.py`: add `test_memory_sweeps_record_and_smooth`
  (US2 scenarios 2 and 4, SC-003): `approved` with a `codex` builder in `seat_policy` (or
  `[adapters]\nruntime = "codex"`), 3 GiB free then 8 GiB: both sweeps append `cap.derived`
  with `reading` 2 then 4 (fixture: 4 cores, 1 GiB floor and seat), the second CAP is 2
  (`median_low([2, 4])`), the `CAP:` line of `plan.md` contains `(memory): ` and
  `status --line` contains `by memory`. Run it; it fails.

### Implementation

- [X] T012 [US2] `cli/wuwei/calibrate.py`: the memory branch from `plan.md` Design (reading,
  today's `cap.derived` readings, `median_low`, the median clause, `reading` in the
  result, bound `memory`). T010 passes.
- [X] T013 [US2] `cli/wuwei/dispatch.py` `launch_set` lines 400 to 402: write `cap.derived`
  when CAP or the bound moved or `'reading' in limits`, with `reading` in the payload.
  T011 passes.

## Phase 3: Pinned behaviour elsewhere (old assertions follow the two rules)

- [X] T014 [US2] `tests/test_calibrate.py`: move `test_host_derives_cap_and_seats`,
  `test_host_falls_back_when_a_past_day_log_is_damaged`, `test_token_budget_bounds_cap` and
  `test_calibrate_measures_the_host_and_never_proposes_cap` onto `PROCESS` (or a codex
  config); bound `host` becomes `memory` (`plan.md`, Existing tests).
- [X] T015 [US1] `tests/test_parallel_dispatch.py`: update
  `test_fresh_workspace_derives_cap_from_the_host_and_starts_four`,
  `test_owner_cap_names_what_the_host_fits`, `test_cap_follows_free_memory_at_each_sweep`
  (process runtime, median) and `test_token_budget_fitting_two_seats_starts_two`
  (`seats 0/2 by budget`; `bound budget` no longer in `wuwei status`) per `plan.md`.
- [X] T016 [P] [US1] `tests/test_agent_launch.py`: run the capacity cases; move to a process
  policy only those whose expectation came from the memory fit; floor cases unchanged.
- [X] T017 [P] [US1] `tests/test_pace.py`, `tests/test_e2e_day.py`, `tests/test_board_mcp.py`:
  fix only assertions the `by <bound>` token or the bound rename moved.
- [X] T018 [US1] `tests/test_invariants.py` `i20`: memory cases on `PROCESS` (including the
  `seat_mib` lookup), subagent cases with `policy={}` (`cap or cores`, the same for every
  free value, never raised by the budget). Run the invariant suite.

## Phase 4: Docs (FR-008)

- [X] T019 [P] `docs/specs/2026-09-24-wuwei-design.md`: the #658 amendment after the #528
  CAP paragraph, the bound list (line 571), line 597, the status line seats example
  (line 1024) and the I20 row (line 1975), per `plan.md` Docs.
- [X] T020 [P] `docs/site/concepts.md` lines 246 and 352 and `docs/site/configuration.md`
  lines 27 and 128: the two rules and the new examples. Run `tests/test_docs.py`.

## Phase 5: Verify

- [X] T021 Run the full suite (`python -m pytest -q`); all green. Check every file written
  for em-dashes and emojis.
