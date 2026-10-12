# Implementation Plan: one re-entry command; no builder without a build record

**Branch**: `901-reconcile` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`build reconcile` composes adoption, the claim, a builder brief and the fast checks into one
idempotent call that leaves an ordinary build record. The gates accept a `done` build in place
of a stopped seat. The Agent guard refuses a builder launch with no build record.

## Constitution Check

- III: shared spots only: `adopt_worktree`, the existing-branch checkout, `next_step`'s
  stand-down test, the guard's `reserve`.
- IV: test first; each claim has a red test.
- V: no new state kind beyond the build record's `reconciled` snapshot and the
  `build.reconciled` event; reuses `brief.write`, `_save`, `recheck`, `check`, `claim_pr`,
  `tracker_call`, `worktree.add`. The existing-branch checkout moves out of `claim_pr` into one
  helper; `pr act`'s two-command adoption recipe becomes the reconcile command.
- VI: stdlib only.

## Files to edit

- `cli/wuwei/commands/build.py`: `reconcile` operation and options; `reconcile()`;
  `check`'s no-record message names reconcile.
- `cli/wuwei/workspace.py` `adopt_worktree`: `dirty` keyword; the refusal names reconcile.
- `cli/wuwei/commands/worktree.py`: `checkout()` (existing branch: adopt, else add).
- `cli/wuwei/shepherd.py` `claim_pr`: uses `worktree.checkout`; `built` passes to
  `state.record_pr`, which then moves a planned item to `implement` instead of `raised`.
- `cli/wuwei/commands/build.py` `next_action`: a new build past the day's derived CAP waits.
- `cli/wuwei/pr_actions.py` `_adoption`: the reconcile command.
- `cli/wuwei/dispatch.py` `next_step`: a `done` build stands for the stopped builder.
- `cli/wuwei/guards/agent_launch.py`: the no-build-record refusal.
- `charters/planner.md`, regenerated `agents/`; `docs/site/reference.md`, `daily.md`,
  `concepts.md`, `recovery.md`.
- Tests: new `tests/test_reconcile.py`; `test_build_next.py` (guard, #892 tests now launch
  with `guards.enforce` off); `test_agent_launch.py`, `test_launch_contract.py` and
  `test_parallel_dispatch.py` give their builder launches a build record (and show the CAP wait);
  `test_pr_actions.py` and `test_shepherd.py` where messages or the adoption command change.

## Verification

Every test file importing a changed module, plus `test_invariants`, `test_docs`, `test_charters`,
under 3.12; the reconcile, build, guard, dispatch, shepherd, pr_actions and worktree files under
3.11.
