Verdict: PASS
Gate: quality
Item: ci-not-started
PR: taoq-ai/wuwei#1106
Head: 121d06ecf52695857c3b98092df18be8c1e3d7c3
Confidence: high

## Findings
none

## Probes
- Delta 97553d7..121d06e read with git diff: tests, docs (design.md, evidence.md) and spec/tasks only; no runtime change.
- Suite at head: pytest -q gives 947 passed, 2 skipped.
- Mutant shared 'ci' cache key, re-run at this head: killed by test_each_repository_keeps_its_own_cached_actions_answer.
- Mutant failed read cached (GhError caught inside the cached read), re-run at this head: killed by test_a_failed_actions_read_is_not_cached.
- Plain gh pr merge refusal added to the guards test pins the door for the non-auto path.
- Runtime: cat cli/wuwei/*.py | wc -l gives 2992; vendored copy diff -r is empty.
- Earlier mutants (empty-rollup, actionable, error-counts-as-CI, day cache, narrowed excepts, widened door) were killed at 97553d7 and the runtime is unchanged, so they stand.
- Simplicity: none; the new test helper actions_by_repo is used by both new tests.

## Residual risk
A path-filtered pull_request workflow holds a docs-only head on a waiting gap, as the spec and design.md now state.
