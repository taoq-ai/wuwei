# Implementation Plan: raised and claimed PRs share one post-PR path

**Branch**: `903-post-pr` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

The claimed-only checks in `raise_action`, `_gated_push` and the push guard go; one path serves
both ownership origins. `rechecks` names the post-PR delta gate, and `open_fix` rotates delta
records when it opens from `raised` too, so the delta is always the current round's. `offers`
gains one branch for red checks at the held head in gate and delta, and `_fix_round` lets that
fix open at delta. `_rebase` records the head `--run` starts from and leases `--complete` on it.

## Constitution Check

- II: every refusal still exits with its reason and names its command; nothing that blocked
  now passes. The push guard refuses more (a raised PR's worktree), never less.
- III: deletions over additions: three claimed-only conditions removed; one helper
  (`post_pr_gate`) and one offers branch added.
- IV: test first; `tests/test_post_pr.py` drives the issue's scenario through the real commands
  and hooks (`fakes.day.Day`), red on the base for each claim.
- V: no new state kind, event kind or config key; reuses `rotate`, `_gated_push`, the conflict
  episode and `capped`.
- Hook paths stay pure reads: the offers branch reads the listing and the worktree HEAD from
  git's files only.

## Files to edit

- `cli/wuwei/dispatch.py`: `rechecks` (post-PR gate), `post_pr_gate`, `rotate` (next free key),
  `raise_action` (any linked PR).
- `cli/wuwei/commands/build.py` `open_fix`: rotate from `raised`.
- `cli/wuwei/pr_actions.py`: `_gated_push` (any owned PR), `_fix_round` (delta at the held
  head), `_rebase` (run head lease).
- `cli/wuwei/derive.py` `offers`: red checks at gate and delta.
- `cli/wuwei/guards/edges.py`: `_claimed` becomes `_owned`, any linked PR.
- `docs/site/reference.md`: the shared post-PR paragraph.
- Tests: new `tests/test_post_pr.py`; `tests/test_edges.py` (raised worktree, message);
  existing expectations that encoded the old rule (`test_dispatch.py::test_rechecks_rule`,
  `test_e2e_day.py` claimed round, `test_pr_actions.py` complete tests seed the run head).

## Verification

The full suite under the pipeline interpreter; dispatch, derive, next, pr_actions, merge,
shepherd, worktree_command, e2e_day, edges, build, invariants, docs and charters under 3.11.
