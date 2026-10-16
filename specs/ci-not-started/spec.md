# Feature Specification: a head with no CI checks registered yet reads as CI not started, never as ready to merge

**Feature branch**: `claude/ci-not-started`
**Item**: ci-not-started, tier full, goal G-2, fixes #1085
**Input**: on 2026-10-16 `wuwei evidence A-Teams-Network/ai-stacks#3319` answered `no gaps: ready
to merge` for a head GitHub had not yet given any check run. `evidence.gaps` passes an empty
`statusCheckRollup` to `ci_gaps`, which finds nothing to report.

## The promise in my words

When a PR head has no check run and no commit status, `wuwei evidence` asks whether the repository
has ever run a workflow on `pull_request` (one read of
`repos/<o>/<r>/actions/runs?event=pull_request&per_page=1`, cached a day per repository). If it
has, the head gets the waiting safety gap `CI not started at <sha7>`, so it is never `no gaps:
ready to merge`. If the Actions read fails or answers an odd shape, the repository counts as having
CI and the gap shows. A repository that never ran a `pull_request` workflow gets no CI gap, as on
main.

The merge door holds on the new gap for `gh pr merge` and for `--auto` alike. `CI running` stays
the only gap `--auto` passes, because GitHub's auto-merge with no required checks merges at once.
The door already exempts only the exact text `CI running`, so the door needs no code change; a
test pins it.

A gate verdict owed at a moved head is reported whatever the CI state. Main already does this; a
test pins it next to the new gap.

Out of scope: CI that runs only on push (its checks already appear in the rollup), required-check
settings, board wording beyond the new gap text.

The acceptance scenarios, restated:

1. PR o/r#5 with an empty rollup in a repository whose Actions runs list one `pull_request` run:
   `wuwei evidence o/r#5` prints `CI not started at aaaaaaa` and not `no gaps: ready to merge`.
2. The same PR: `gh pr merge 5 -R o/r --auto --squash` read by the Bash guard is refused naming
   `CI not started`; a head whose only gap is `CI running` still passes with `--auto`.
3. A repository whose Actions runs list no `pull_request` run: no CI gap, as on main.
4. The Actions read raises `GhError`: `CI not started at aaaaaaa` appears.
5. A quality FIX at the previous head, no verdict and no checks at the new head: evidence names the
   quality gate missing at the new head and `CI not started`.

## Clarifications

### Session 2026-10-16

- Q: Is the gap actionable? A: No. It is waiting (`[waiting]`), like `CI running`: the seat waits
  for GitHub to register checks. It is still a safety gap, so it holds the merge.
- Q: Which odd Actions replies count as unreadable? A: `GhError`, and the shapes that raise
  `AttributeError` or `TypeError` in `gh.workflow_paths` (a non-object reply, `workflow_runs:
  null`). This matches `review_contexts`, which treats the same failures as CI.
- Q: Is a failed read cached? A: No. The exception leaves `_cached` before it writes, so the next
  call reads again. Only a successful read is cached for a day.
- Q: Does a PR with checks make the Actions read? A: No. The read happens only when the rollup is
  empty, so existing PRs and the recorded replay case make no new call.
- Q: Does `per_page=1` still tell "ran a pull_request workflow" apart from "never"? A: Yes. The real
  endpoint answered `{"total_count": 989, "workflow_runs": [{"path": ".github/workflows/tests.yml",
  "event": "pull_request", ...}]}` for taoq-ai/wuwei; a repository with none answers an empty
  `workflow_runs`.

## How this fails

1. A repository whose `pull_request` workflow is filtered by paths gets no check for a docs-only PR.
   The head then shows `CI not started` until the owner accepts an exception. The gap is waiting,
   not actionable, so no seat is told to fix it; the cost is a held merge, never a false pass.
2. The cached answer goes stale: a repository adds its first `pull_request` workflow and for up to
   a day an empty rollup reads as no CI. This matches main's behaviour for that window.
3. GitHub registers checks seconds after a push. A seat reading evidence in that window now sees a
   waiting gap where main said ready. That is the fix; a seat that polls would loop, which the
   charters already forbid.

## User scenarios

### US1: an unverified head is never ready to merge (P1)

Acceptance 1, 3 and 4. Tests in `tests/test_evidence.py`:
`test_a_head_with_no_checks_in_a_repo_with_pull_request_ci_reads_ci_not_started`,
`test_a_repo_that_never_ran_a_pull_request_workflow_gets_no_ci_gap`,
`test_an_unreadable_actions_host_counts_as_having_ci`,
`test_the_actions_read_is_cached_a_day_per_repository`.

### US2: auto-merge waits for CI that has not started (P1)

Acceptance 2. Test: `tests/test_guards.py::test_auto_merge_is_refused_while_ci_has_not_started`.

### US3: a moved head names the gate it owes whatever CI says (P2)

Acceptance 5. Test: `tests/test_evidence.py::test_a_moved_head_names_the_gate_owed_and_ci_not_started`.

## Requirements

- FR-001: with an empty rollup and a repository that ran a `pull_request` workflow, evidence adds
  the waiting safety gap `CI not started at <sha7>`.
- FR-002: the Actions read is made only for an empty rollup and is cached a day per repository.
- FR-003: an unreadable Actions host counts as having CI.
- FR-004: a repository that never ran a `pull_request` workflow gets no CI gap.
- FR-005: the merge door refuses `--auto` on the new gap; only `CI running` stays exempt.
- FR-006: the vendored copy under `.claude/` is rewritten.

## Assumptions

- One Actions read per repository per day is cheap enough. Overturned if the gh call rate shows in
  the report.
- The new gap text is not a breaking change: `wuwei evidence` output gains a line for a state it
  wrongly called ready. No flag, key, exit-code meaning or route changes. Overturned if a consumer
  parses `no gaps: ready to merge` as a contract for empty-rollup heads.

Rollback: revert the commit; no data or config changes.
