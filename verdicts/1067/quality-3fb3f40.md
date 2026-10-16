Verdict: PASS
Gate: quality
Item: 1067
PR: taoq-ai/wuwei
Head: 3fb3f405ed6c888942a406e6f82c0f651c857bb0
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/evidence.py:350 blocks: no. Mutant: drop the `paths and` guard in review_contexts survives. With an empty cached review set every unsettled run-linked status still pays one per-run read, and the result is the same empty set. Cost only. The missing test is "no review workflows, so no per-run read", as the builder reported.
- [low] cli/wuwei/evidence.py:351 blocks: no. Mutant: narrowing the except to GhError survives. No test sends a run body without `path` (KeyError, which gaps() turns into "evidence unreadable") or a non-dict body (AttributeError, which would escape gaps()). Both need the host to break its own contract, so there is no concrete bad input.
- [low] cli/wuwei/evidence.py:350 blocks: no. Builder scenario 3 holds as stated. A failed Actions read is not cached, so a token without Actions read pays one failed review-workflow read per evidence read (fail-closed to CI, tested). Each unsettled run-linked status also pays one uncached per-run read. A run id maps to a fixed path, so caching it by id would remove that read.
- [low] cli/wuwei/evidence.py:350 blocks: no. Builder scenarios 1 and 2 are design limits, not defects. They are a CI workflow that also listens on pull_request_review (including claude.yml on ai-stacks), and a review workflow absent from the last 100 runs or newer than the day-old cache. Both match the promise and design.md. A review workflow that has never run on a review is not recognised until its first review run, and an empty set can then stay cached for up to a day.
- [low] pre-existing: the `imported` branch of verdicts() has no test that reaches it. The same mutant (delete the branch) survives on origin/main (264 passed). The builder's merge of the two appends is therefore unprotected both before and after, though by reading it is equivalent.

## Probes
- Suite at the head, in a scratch copy: 280 passed. Main passes 264, so the 16 new cases all run. The runtime is 3000 lines (main 2997), exactly at the cap with no margin.
- Mutants on the new code, all KILLED:
  - flip the failed/pending label: test_a_pending_status_from_a_review_triggered_workflow_waits_on_review
  - drop the SUCCESS filter: test_a_failing_status_from_an_ordinary_workflow_is_still_ci
  - drop the cache: test_the_review_workflows_are_read_once_a_day
  - invert path membership: the waits-on-review test
  - drop GhError from the except: test_an_unreadable_actions_host_leaves_the_status_ci
  - drop the `runs and` guard: test_a_head_without_commit_statuses_makes_no_actions_read
  - match any repo in the target_url: test_a_status_without_a_run_of_this_repo_stays_ci_unread
  - ignore review in ci_gaps: the waits-on-review test
  - drop the url field in gh.pr: the waits-on-review test
  - single-run response shape: the waits-on-review test
- The merge door has tests for PENDING and FAILURE, each with and without --auto (test_guards.py). They pass and are reachable through guards.pre_tool.
- "No behaviour change" claim checked line by line:
  - verdicts() truth table over (hash changed, imported, verdict): identical to main for all combinations.
  - review_duty, item_for, spec_engine, the gaps() reviewers test and the not-linked gap (same position in the list), unanswered_threads' dict comprehension, and the `_upper` inlining: equivalent.
  - `datetime` is imported at module top, so the removal inside budget is safe.
  - Mutants of the refactor killed by existing tests:
    - verdicts: changed file with a PASS verdict (replaced-PASS case)
    - review_duty: the `sent` row check
    - item_for: dropping the PR-link match
    - unanswered_threads: the author kept per thread
  - Mutants that survive: the verdicts `imported` ones, which also survive on main (see the last finding).
- Acceptance 1 to 6 each map to a test above (the no-statuses case is asserted on fake.calls). Acceptance 7: the suite passes and the size test passes at 3000 lines.
- AGENTS.md: the commit author is Leone, and the diff has no em dashes.
- Not run: the real ai-stacks host (403 here), so the `path` shape of the single-run read is unmeasured. Both reads use the same field, so a mismatch would be consistent.
- Simplicity: the `review_contexts` try/except tuple could shrink to GhError plus KeyError. The refactor's 26 freed lines are not harmful, but the comprehension in `runs` is dense. The fake `runs` dict is the right reuse. No trust-boundary or fail-closed code is deletable.

## Residual risk
The tie from status to workflow rests on the probe's reading of ai-stacks, which this session could not re-check. A CI workflow that also listens on pull_request_review is reported as review, but the merge is still refused.
