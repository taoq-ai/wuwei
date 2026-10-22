# Implementation plan: gates-at-push

**Spec**: `specs/gates-at-push/spec.md`
**Item**: 1221, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,600 lines. Main 470ab63 holds
  3,551; the item's budget is +3.
- `board.compute` builds the team row; its owed-gates duty skipped any row with a gap starting
  `CI ` or `required check`.
- `guards.ready_door` reads the PR with `gh.pr` (which carries `statusCheckRollup`) and hands a
  draft to `create_door`, which reads only gate gaps.
- `evidence.ci_gaps(rollup)` turns checks into `CI failing: <names>` or `CI running`;
  `evidence.excepted(root, ref, head, found)` drops a gap the owner accepted at that head.
- `hook._verdict_problem` attests a verdict from its file alone; `evidence.gate_gaps` counts it by
  head and ancestry. Neither reads CI.

## Design

1. `board.compute`: the owed-gates duty skips only rows with a `CI failing` gap; its text drops
   "on green heads".
2. `guards.ready_door`: on a draft, the `CI failing` gap from `evidence.ci_gaps`, less what the
   owner accepted at that PR and head, is refused first, naming the checks; otherwise the create
   door reads the gates as before. (+3 lines.)
3. Charters: planner Running the work 2, builder hand-back, `_way`, `_pr`, shepherd Follow 3, the
   watch skill; agents rebuilt; the vendored copy refreshed.
4. Docs: design section 7 and the gate row, site evidence and doors pages.

## Proof

- Tests first: the board duty, the ready door on a red, running and green head with the owner
  exception, the merge door on a red head, a verdict attested while CI ran, the charter text.
- `route_diff.py`: the route corpus under four hosts (green, running, red, excepted) at main and
  the head, with the corpus sha256.
- Six mutants of the changed expressions, applied to both runtime copies one at a time.
