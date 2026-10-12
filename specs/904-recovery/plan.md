# Implementation Plan: environment failures are holds, an approved resume moves the build on

**Branch**: `904-recovery` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

The environment branch of `complete_checks` becomes a counted hold; `plan resume` resets a
parked build record; one helper, `dispatch.capped`, carries the resume grant to every cap
check; `derive.offers` uses `merge.owner_hold`.

## Constitution Check

- III: shared spots only (`complete_checks`, `plan.resume`, `dispatch.capped`).
- IV: test first; each claim has a red test.
- V: reuses `_signature`, `_save`, `_continue`, `_park`, `_resumed` and `owner_hold`; deletes the
  `granted` parameter and its three call-site copies of the cap test.

## Files to edit

- `cli/wuwei/commands/build.py`: `recheck` (the check action, now shared with `record_result`);
  the environment hold in `complete_checks`; `run_loop` stops on a hold; `open_fix` reads the
  grant through `dispatch._resumed`.
- `cli/wuwei/plan.py` `resume`: reset a `parked` build in the same write.
- `cli/wuwei/dispatch.py`: `capped`; `next_step` uses it at both cap checks.
- `cli/wuwei/pr_actions.py`: `_gated_push` and `_fix_round` use `capped`.
- `cli/wuwei/derive.py`: `capped` for the moved head and red checks; `merge.owner_hold`.
- `docs/site/concepts.md` Park: the hold and the resumed build.
- Tests: `test_build.py`, `test_build_next.py`, `test_dispatch.py`, `test_derive.py`,
  `test_pr_actions.py`, `test_loop.py` (real `owner_merge` record), `test_worktree_command.py`
  (the `open_fix` fake drops `granted`).

## Verification

Every test file importing a changed module under 3.12; build, build_next, dispatch, plan,
derive, next, merge, pr_actions, loop and worktree_command under 3.11.
