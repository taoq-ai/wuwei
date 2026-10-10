# Tasks: the reference-adapter replay test is isolated under the parallel run

Test first: the failing test for this issue is the deterministic reproduction pair below. It
is run and seen to fail with `linear.transition: could not run: KeyError` before any edit,
and run again after each edit. No new test file: the behaviour under change is the isolation
of existing tests, and the pair exercises it directly. Run from the worktree root with the
interpreter the task names.

Reproduction pair (REPRO):
`python -m pytest -q -p no:xdist tests/test_linear_loop.py::test_linear_transition_resolves_team_state_once tests/test_reference_adapters.py::test_linear_replay`

## Phase 1: the leak is gone (FR-004, US2)

- [X] T001 Run REPRO on the unchanged tree. Expect `1 failed, 1 passed`, the failure at
  `tests/test_reference_adapters.py` `assert linear.transition('ABC-1', 'In Review').exit == 0`
  with reason `linear.transition: could not run: KeyError`. Stop if it fails for any other
  reason.
- [X] T002 In `tests/test_linear_loop.py`, replace `linear._state_ids.clear()` with
  `monkeypatch.setattr(linear, '_state_ids', {})` in
  `test_linear_transition_resolves_team_state_once` and in
  `test_linear_transition_resolves_name_starting_with_state`. No other line changes.
- [X] T003 Run REPRO: expect `2 passed` (the writer no longer leaks). Run
  `python -m pytest -q tests/test_linear_loop.py`: expect all passed.

## Phase 2: the replay test isolates itself (FR-001, FR-002, FR-003, US1)

- [X] T004 Confirm the dependency T005 removes: in `tests/test_reference_adapters.py`
  `test_linear_replay`, the fourth replayed response is the `workflowStates` page and the
  test has no isolation of `linear._state_ids` (read, no edit). With T002 applied no current
  test fills the memo before it, so there is no further red run; T001 is this behaviour's
  failing test, and T005 keeps REPRO green against any future writer.
- [X] T005 In `tests/test_reference_adapters.py` `test_linear_replay`, directly after
  `linear = importlib.import_module('adapters.tracker.linear')`, add the one-line cause
  comment from plan.md (naming #776 and the per-process `_state_ids` memo) and
  `monkeypatch.setattr(linear, '_state_ids', {})`. No other line changes.
- [X] T006 Run REPRO: expect `2 passed`. Run
  `python -m pytest -q tests/test_linear_loop.py tests/test_reference_adapters.py
  tests/test_tracker_adapters.py`: expect all passed.

## Phase 3: whole suite and hygiene (SC-003, SC-004)

- [ ] T007 (deferred to CI per owner, 2026-10-10) Run `python -m pytest -q` and `python -m pytest -q -n auto --dist loadgroup`;
  both pass.
- [X] T008 Check the diff: `tests/test_reference_adapters.py` gains exactly two lines and
  loses none; `tests/test_linear_loop.py` changes exactly two lines; nothing outside these
  two files and `specs/776-replay-isolation/` changed; no em-dashes, emojis or absolute local
  paths in any touched file.
