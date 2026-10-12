# Implementation Plan: a resumed item whose build finished goes on to its gates

**Branch**: `872-resume-after-build` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`plan resume` advances a paused build phase whose build already passed, through the same move
the build loop writes after passing checks.

## Technical Context

Stdlib Python 3.11+, two runtime files, two test files. No new state field, no migration.

## Constitution Check

- III: one behaviour, one function: the move after a passing build becomes `build.built`,
  called by `complete_checks` and `plan.resume`.
- IV: the failing tests come first (`tests/test_plan.py` table, `tests/test_next.py`
  acceptance), run red, then the code.
- V: shortest diff; no migration for already stuck items (spec Assumptions).

## Files to edit

- `cli/wuwei/commands/build.py`: `AFTER = {'implement': 'gate', 'fix': 'delta'}` and
  `built(data, item, phase, end)` (the `fix_heads` end head for `delta`, then `state._move`),
  taken out of `complete_checks`, which calls it.
- `cli/wuwei/plan.py` `resume`: read the build record; if it is `done` and `AFTER` has the
  paused phase, call `build.built` after restoring the phase, in the same state write.
- `tests/test_plan.py`: `test_plan_resume_continues_from_the_build_record`, a table over
  planned, implement (ready, check, done), gate, fix (check, done).
- `tests/test_next.py`: `test_resumed_item_whose_build_finished_goes_to_its_gates`.

## Verification

`python -m pytest -q` on every test file that imports `wuwei.plan` or
`wuwei.commands.build`, under 3.12 and 3.11.
