Verdict: PASS
Gate: quality
Item: 1210
PR: taoq-ai/wuwei#1215
Head: 614a781eb7ba3759b4d4e713a559326f3acc4f91
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/gh.py:56 blocks: no. Two different workflows that report a check under the same name collapse to the one with the higher id, so an older failing run of one hides behind a newer green run of the other. The promise says per check name, so this is by design; a note for the PR's review notes.
- [low] tests/test_evidence.py:124 blocks: no. An extra blank line before the new test (three blank lines, the file uses two); the key's `or 0` fallback for a run without an id has no test.

## Probes
- Read at the head with `git archive 614a781` in my scratch folder. `pytest -q tests/test_evidence.py`: 309 passed. The 4 new parametrised cases are collected and run, none skipped. They go through the real `gh.pr` via FakeGh, which reaches `ci_gaps` and the settled check.
- Mutants applied to both `cli/wuwei/gh.py` and `.claude/wuwei/cli/wuwei/gh.py`, test_evidence.py only:
  - Remove the per-name collapse (key by `id(c)`): killed by runs0, runs1 and runs3 of `test_the_newest_run_of_a_check_at_the_head_decides`.
  - Reverse the sort (oldest wins): killed by all four cases.
  - Remove the sort (API order, last wins): killed by runs0, runs2 and runs3.
- Acceptance scenarios 1, 2 and 3 map to runs0 (success newest, cancelled, success, cancelled: no gap), runs2 (newer failure after success: `CI failing: Review Gate` once) and runs3 (newer in-progress after failure: `CI running`).
- Downstream readers checked by reading `cli/wuwei/evidence.py`. `ci_gaps` and `review_contexts` read statuses (`context`) and check runs by name, so the collapse leaves statuses untouched. The `settled` read now looks at the newest run only, so an older in-progress run that was superseded no longer holds the cache or the "required check not run yet" wait. That is the intent. The required-checks name set is unchanged, because the collapse keeps one run per name. The `not rollup` CI-not-started branch is unchanged.
- Runtime budget: `cat cli/wuwei/*.py | wc -l` gives 3388, within 3,400. The vendored copy is identical (`diff -r` shows only `__pycache__`), and the vendored-plugin, budget and lines tests pass (47).
- Unmeasured: whether GitHub's `check-runs` endpoint, with its default `filter=latest`, can omit the true newest run by id. I had no network read of infra-aws#472, so this is not checked. The fix is correct for whatever the endpoint returns.
- Guard parsing is untouched, so the combinatorial probe and the route differential do not apply.
- Simplicity: none to delete. The change is one expression, a sort then a dict comprehension, and replaces a loop. Nothing in stdlib is shorter.

## Residual risk
Same-named checks from different workflows are judged by the newest only. Pagination stays at the first 100 runs, as before.
