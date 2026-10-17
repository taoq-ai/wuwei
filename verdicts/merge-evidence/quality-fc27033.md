Verdict: PASS
Gate: quality
Item: merge-evidence
PR: taoq-ai/wuwei#1114
Head: fc27033543ad8c0a57ec39f84fd0082d5d8587f2
Confidence: medium
Breaking: no

## Findings
- [low] blocks: no. The `specs/`/`openspec/` prefix exclusion in `code` (cli/wuwei/evidence.py, the `code = [...]` line) is untested: dropping it leaves all 119 tests in tests/test_evidence.py green. The test inputs `specs/a/spec.md` and `docs/site/x.md` are already matched by DOCS. Input the reversed guard lets through: a diff of only `specs/a/plan.json` with an empty rollup, which would then raise a false CI not started gap and a false no-test gap. Untested, not shown equivalent (no differential probe run). Missing test: a specs-only non-markdown file.
- [low] blocks: no. The spec claims a docs-only diff makes no Actions read (FR-002), but no test asserts the read count. The result is pinned only through the gap text.
- [low] blocks: no. The `endswith` check in test_an_unreadable_actions_host_counts_as_having_ci is vacuous for the two non-exception replies (`or not isinstance(reply, Exception)`). The `startswith` check still pins the unreadable-host text for all three replies.

## Probes
- Suite at head (git archive into scratch, pytest): 1207 passed, 2 skipped.
- Red on main: the head's tests/test_evidence.py was run against the 86135fa tree. 7 cases failed (test_only_an_owner_review_ruling_clears_the_owner_review, test_a_docs_only_diff_gets_no_ci_not_started[files0-False], test_pull_request_target_runs_count_as_ci, 3 cases of test_an_unreadable_actions_host_counts_as_having_ci, test_a_failed_actions_read_is_not_cached). The code-diff parametrized case holds on main, as tasks.md T006 says.
- Mutant kind check (`and True`): killed by test_only_an_owner_review_ruling_clears_the_owner_review.
- Mutant `code` docs-only in the CI read (drop `and code`): killed by test_a_docs_only_diff_gets_no_ci_not_started[files0-False].
- Mutant `code` docs-only on the no-test gap (drop `not generated`, i.e. restore the old shape): killed by the generated-PR tests (`no test in the diff` appears).
- Mutant unreadable-host text (`why = ''`): killed by the startswith assertion of the unreadable-host test (3 cases), and by test_a_failed_actions_read_is_not_cached.
- Mutant pull_request_target fallback removed: killed by test_pull_request_target_runs_count_as_ci, and by the cache test.
- Mutant not-caching of failures (the lambda swallows GhError and returns a truthy value, so it is cached): killed by test_a_failed_actions_read_is_not_cached and the unreadable-host tests.
- Mutant `specs/` prefix removed from `code`: SURVIVED (see the first finding). Re-run in a fresh copy, still 119 passed.
- The two updated old tests: test_a_failed_actions_read_is_not_cached still pins the no-cache behaviour (the 502 shows the gap, the retry reads clean, 3 reads in total). test_each_repository_keeps_its_own_cached_actions_answer still pins per-repo cache keys. Only the read counts and the text changed, for the second read and the new wording.
- Runtime: `find cli -name '*.py' | xargs cat | wc -l` gives 2977 (main 2976), under the 3,000 cap and within the +6 budget.
- Vendored copy: `diff cli/wuwei/evidence.py .claude/wuwei/cli/wuwei/evidence.py` is identical.
- Emojis and em dashes: scanned the added lines of the diff with a Python regex for U+2014 and emoji ranges, 0 hits.
- Spec completeness: spec.md, plan.md, tasks.md, analysis.md and checklists/requirements.md are present. spec.md has the promise, clarifications, How this fails, Breaking with migration, Assumptions and FR-001 to FR-005, and analysis.md maps every FR to tasks. docs/design.md and docs/site/concepts/evidence.md are updated.
- Confidence is medium. The gate ran no differential probe and no real gh run, so the actual Actions responses rest on stubs.

Simplicity: none to delete. The change is a +1 runtime-line rewrite of existing expressions, with no new abstraction. The `why` variable is needed for the error text. The try/except already existed. The trust-boundary fail-closed branch (an unreadable host shows the gap) is kept.

## Residual risk
Real `pull_request_target` and 403 replies are unmeasured beyond the stubs and the spec's one recorded read. A docs-only PR can merge before docs CI registers, which is the plan's recorded assumption.
