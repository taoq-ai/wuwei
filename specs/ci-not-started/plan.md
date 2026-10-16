# Implementation plan: ci-not-started

**Spec**: `specs/ci-not-started/spec.md`
**Item**: ci-not-started, tier full, fixes #1085

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 3,000 lines. Main 247d72e holds
  2,986 after free-lines-3 (#1104).
- `evidence.gaps` reads `pr['statusCheckRollup']` and calls `ci_gaps`. `gh.workflow_paths(repo,
  query)` already reads `repos/<repo>/actions/runs<query>` and answers the sorted workflow paths.
  `evidence._cached` caches a value for a day in `.wuwei/cache/`.
- `guards.merge_door` drops only the gap whose text is exactly `CI running` when `--auto` is set.

## Design

1. In `evidence.gaps`, after `ci_gaps`, when the rollup is empty read
   `_cached(root, 'ci-<owner>__<repo>', gh.workflow_paths(repo, '?event=pull_request&per_page=1'))`.
   A non-empty answer, or `GhError`, `AttributeError` or `TypeError`, adds
   `gap('CI not started at <sha7>', actionable=False)`.
2. No guard change: the new gap is a safety gap and not `CI running`, so the merge door holds it
   with and without `--auto`. The comment on that line names #1085.
3. Re-vendor `.claude/` with `setup.vendor`.

Line cost: +6 runtime lines (2,986 to 2,992), inside the +7 budget.

## Constitution check

Stdlib only, no new dependency, no config key, no new door, test first, under the line budget.

## Test plan

Stub the code host with `conftest.FakeGh` (its `runs` table plays the Actions runs list). Five
acceptance tests plus a cache test, run red on e34586d, then green.
