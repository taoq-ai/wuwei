# Tasks: one table per edge and the loop property test; no timing assertions; under 3000 tests

**Input**: [spec.md](spec.md), [plan.md](plan.md). Built after parts 23 and 24 on the same
branch.

Run tests with `python -m pytest -q <files>` from the repository root, only the files named.
This part changes tests and CI. For each consolidated table, show it red once: in a scratch
copy, reverse the edge's condition and run the table (it must fail and name the rows), then
restore. Record the count with `python -m pytest --collect-only -q | tail -1` after each phase.

## Phase 1: Edge tables (US1, P1)

- [X] T001 [US1] Write the eight table tests in `tests/test_edges.py` from the rows plan.md
  lists, with the `guards.enforce` and workspace columns; show each red by breaking its edge in
  a scratch copy; run `tests/test_edges.py`: green.
- [X] T002 [US1] Delete the moved functions from `tests/test_edges.py`, `tests/test_merge.py`,
  `tests/test_profiles.py`, `tests/test_seat_command_forms.py`, `tests/test_parser_warns.py`,
  `tests/test_scope_first.py`, `tests/test_guard_mutation.py`, `tests/test_outward.py`,
  `tests/test_canary.py`, `tests/test_enforce.py`, `tests/test_card_confirms.py`; move the init
  and settings tests to `tests/test_config_transition.py`; delete the files left empty. Run
  those files: green. Check SC-003 with `grep -rn "check_bash\|check_deploy\|check_send" tests`.

## Phase 2: No timing assertion (US3, P1)

- [X] T003 [US3] Create `scripts/hook_latency.py` from the measurement in `tests/test_hooks.py`;
  move the decision tests to `tests/test_latency_report.py`; run
  `python scripts/hook_latency.py` locally (writes rows, exits 0) and
  `tests/test_latency_report.py`: green.
- [X] T004 [US3] Delete the timing tests and elapsed checks plan.md lists in
  `tests/test_hooks.py`, `tests/test_integrity.py`, `tests/test_traces.py`,
  `tests/test_e2e_day.py`, `tests/test_path_day.py`, `tests/test_signal_status.py`; rewrite the
  held-lock test to assert the outcome; delete the `timing` group, its rerun step, the marker and
  the `TIMING` pin; point the latency job at the script; add the count step to
  `.github/workflows/tests.yml`. Run those files plus `tests/test_dev_cycle.py`: green. Run the
  SC-002 grep: no duration assertion.

## Phase 3: Loop contract (US2, P1)

- [X] T005 [US2] Fix the `tests/test_loop.py` docstring; run
  `python -m pytest -q --durations=0 tests/test_loop.py`; if the property test's setup and calls
  exceed one second, write each world in one `_write_state` call and measure again. Record the
  figure for the PR body.

## Phase 4: Under 3000 (US4, P1)

- [X] T006 [US4] Collapse parametrized tables in plan.md's order, one file at a time, running
  that file after each; stop at a collected count of at most 2900.
- [X] T007 [US4] Run `python -m pytest --collect-only -q | tail -1`: at most 2900. Run the files
  T006 touched plus `tests/test_edges.py tests/test_loop.py tests/test_e2e_day.py
  tests/test_path_day.py`: green.

## Dependencies

Parts 23 and 24 first. Phase 1 before Phase 4 (the edge consolidation changes the counts).
Phases 2 and 3 are independent.

## Build notes

- B9 lead call (b) overrides FR-007 and T006/T007: the count is test functions (`def test_`),
  no parametrized table is collapsed, and the CI step counts test functions and fails at 3000.
  The suite holds 2643 test functions after this part.
- T002 absorbed only exact duplicates whose every row moved: the edge rows of
  `test_merge.py::test_guard_never_bypasses_dedicated_writer`. The hook-level tables in
  `test_profiles.py`, `test_seat_command_forms.py`, `test_parser_warns.py`, `test_scope_first.py`,
  `test_canary.py`, `test_enforce.py` and `test_outward.py` test other context (profiles,
  postures, the outside-workspace gate, canaries, the outward lint) and stay.
- T005: `--durations` shows the property fixture's setup at 1.38 s on a developer machine; the
  time is the 400 materialised worlds' files (300 plus 100 for the state.json deletion check),
  not the state write, so the one-write fallback would not bring it under a second. Measured,
  never asserted.
