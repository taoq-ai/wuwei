# Implementation Plan: the reference-adapter replay test is isolated under the parallel run

**Branch**: `776-replay-isolation` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The flake is the Linear adapter's process-wide memo `_state_ids`
(`adapters/tracker/linear.py:8`), filled by `test_linear_transition_resolves_team_state_once`
and never restored, then read by `test_linear_replay`, whose fixed replay order assumes it is
empty. Every test that calls the real `transition` replaces the memo with an empty dict through
`monkeypatch.setattr`, the idiom `tests/test_tracker_adapters.py:87` already uses, so pytest
restores it after the test. Three one-line changes in two test files, plus one comment line.
No production code, fixture, marker or config changes.

## Technical Context

Stdlib-only Python 3.11+, pytest and pytest-xdist for tests. `transition` reads the module
global `_state_ids` at call time, so replacing the module attribute is seen by the next call
and undone at teardown.

## Constitution Check

- I stdlib only: no runtime change.
- II exits: unchanged.
- III one behaviour, one function: the memo stays in `linear.transition`; its own test stays.
- IV test first: the deterministic reproduction pair is the failing test; it is run red before
  any edit and green after.
- V ponytail: reuse the existing `monkeypatch.setattr(adapter, '_state_ids', {})` idiom; no
  autouse fixture, no `xdist_group` marker, no adapter change.
- VII: no guard, refusal or decision rule changes; no 9.2 invariant row owed.

## Changes, by file

### `tests/test_linear_loop.py`

- `test_linear_transition_resolves_team_state_once` (line 41): replace
  `linear._state_ids.clear()` with `monkeypatch.setattr(linear, '_state_ids', {})`. The test
  already takes `monkeypatch`; the call stays where it is, after `_query` is patched and before
  the first `transition`. Its assertions (`calls.count({'team': 'team-1'}) == 1`, the last
  input) hold unchanged because the memo is empty at the start either way.
- `test_linear_transition_resolves_name_starting_with_state` (line 59): the same replacement.

This is the root-cause fix: these two are the only tests that leak the memo today.

### `tests/test_reference_adapters.py`

- `test_linear_replay` (line 69): directly after
  `linear = importlib.import_module('adapters.tracker.linear')`, add one comment line and one
  call:

  ```python
  # #776: linear._state_ids memoises team states per process; a transition run earlier in this worker skipped the workflowStates replay.
  monkeypatch.setattr(linear, '_state_ids', {})
  ```

  The comment is the issue's "record the cause in one line in the test". The call makes the
  test independent of any future writer and stops the test itself leaving `team-1` behind.
  Nothing else in the test moves: the six replayed responses, their order and every assertion
  stay byte for byte.

## Shared helpers reused

- pytest `monkeypatch.setattr` on the module attribute, exactly as
  `tests/test_tracker_adapters.py:86-87` does for the port contract test.

## What must not change

- `adapters/tracker/linear.py`: the memo, `transition` and every other function.
- `tests/conftest.py`, `pyproject.toml` (no new `xdist_group` name), `.github/workflows/tests.yml`.
- `tests/test_tracker_adapters.py` (already isolated).
- Any assertion, recorded response or response order in `test_linear_replay` and in the two
  loop tests. `tests/fixtures/reference_adapters/recordings.json` is untouched.

## Rejected alternatives

- `@pytest.mark.xdist_group`: hides the leak behind worker placement and serialises tests that
  do not need it.
- An autouse fixture in `tests/conftest.py`: larger diff, imports the Linear adapter for every
  test in the suite, and makes the existing explicit isolation in the contract test redundant.
- Clearing or dropping the memo in the adapter: changes production behaviour that has its own
  test, to fix a test-only problem.

## Verification

1. Reproduction (red before, green after), from the worktree root:
   `python -m pytest -q -p no:xdist tests/test_linear_loop.py::test_linear_transition_resolves_team_state_once tests/test_reference_adapters.py::test_linear_replay`
2. Both files: `python -m pytest -q tests/test_linear_loop.py tests/test_reference_adapters.py`.
3. Full suite serial: `python -m pytest -q`; and parallel as CI runs it:
   `python -m pytest -q -n auto --dist loadgroup`.
4. Assertion set unchanged: the diff of `tests/test_reference_adapters.py` adds exactly two
   lines and removes none; the diff of `tests/test_linear_loop.py` changes exactly two lines.
