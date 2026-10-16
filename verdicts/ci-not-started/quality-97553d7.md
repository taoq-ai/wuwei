Verdict: FIX
Gate: quality
Item: ci-not-started
PR: taoq-ai/wuwei#1106
Head: 97553d7efc3cd9bbe070667ff90e3a71f8af6392
Confidence: medium

## Findings
- [medium] cli/wuwei/evidence.py:399 blocks: yes. Failure: the cache key `'ci-' + repo.replace('/', '__')` is not pinned by any test (mutant keyed `'ci'` for all repositories survives, 702 passed). With a shared key, a repository with no pull_request workflow read first caches an empty answer, and within the day a repository that does run pull_request CI and has an empty rollup reads as no gap, `no gaps: ready to merge` on an unverified head: the exact #1085 false pass. Add a test reading two repositories (one with runs, one without) and asserting each keeps its own answer.
- [low] cli/wuwei/evidence.py:399 blocks: no. The spec clause "a failed read is not cached" has no test (a mutant that stores True on failure survives). The current structure cannot cache a failure, so this is a missing pin only: a test that a GhError read followed by a healthy read returns the healthy answer would close it.

## Probes
- Suite at head: pytest -q gives 945 passed, 2 skipped.
- Tests red on main: head tests run against main's evidence.py and guards.py fail 6 in test_evidence.py (not-started, 3 unreadable-host cases, cache, moved head) and the guards auto-merge test; the no-pull_request-CI and moved-head gate checks are pinned as the spec says.
- Mutants killed: empty-rollup forced True (many tests fail) and forced False (6 fail); actionable flag dropped (test_a_head_with_no_checks...reads_ci_not_started); error-counts-as-CI reversed (3 unreadable-host cases); day cache removed (test_the_actions_read_is_cached_a_day_per_repository); except narrowed to GhError only, without AttributeError, without TypeError (each killed by its own unreadable-host case); merge door widened to any 'CI ' gap (test_auto_merge_is_refused_while_ci_has_not_started).
- Mutants surviving, re-run at this head: shared cache key (above, blocks); failure-cached variant (above, note).
- Runtime: cat cli/wuwei/*.py | wc -l gives 2992, within 3,000.
- Vendored copy: diff -r of cli/wuwei and .claude/wuwei/cli/wuwei at head is empty.
- No emojis or em dashes in the spec, runtime diff or tests (grep over the byte patterns found none).
- Spec: spec.md, plan.md, tasks.md, analysis.md and checklists/requirements.md are present for full tier; spec carries How this fails, Assumptions and Rollback, and acceptance 1-5 map to named tests.
- Readability: the try/except with an inline `ci` flag is compact and commented; the guards.py change is only a comment (door logic unchanged), acceptable. One-line `ci = not rollup and _cached(...)` is dense but readable.
- Simplicity: none to delete; the guards.py comment edit is the only non-essential change and it records why the exemption stays exact.

## Residual risk
The per-repository cache isolation is unpinned; after a test is added the change is sound. A path-filtered pull_request workflow leaves docs-only heads on a waiting gap, as the spec says.
