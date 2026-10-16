Verdict: PASS
Gate: goal
Item: 1067
PR: taoq-ai/wuwei
Head: 3fb3f405ed6c888942a406e6f82c0f651c857bb0
Confidence: high

## Findings
- [low] cli/wuwei/evidence.py:361 blocks: no. Any FAILED state of a review-tied status (failure, error) reads "change request outstanding" without consulting the review list. Acceptance 2 says "while a change request stands"; the spec records this as a clarification (the promise maps failure to the text directly). It stays an actionable safety gap that holds the merge, so the owner's harm (a red build sending work to a CI fix) is gone either way.
- [low] cli/wuwei/evidence.py:349 blocks: no. Review workflows are learned from the last 100 pull_request_review runs. On ai-stacks claude.yml shares that list (total_count 2500); if a busier review-triggered workflow crowded review-gate.yml out of the last 100, the status would fall back to CI (the safe side, the old wording). Recorded as an assumption in the spec.
- [low] cli/wuwei/evidence.py:349 blocks: no. The per-run read (actions/runs/<id>) is not cached, so each evidence read of a PR with an unsettled same-repo status makes one extra call. This sits within the promise ("read only when the head has a commit status"); the board's own cache bounds it.
- [low] cli/wuwei/board.py:47 blocks: no. Existing limit outside this item: drafts #3293, #3292, #3294 and #3295 are not on the board as adopted rows (the adopted rule skips drafts). `wuwei evidence` on them now reads "waiting on review: Review Gate".

## Probes
- Source trace: issue #1067 (owner report), plan show 1067 (promise, 7 acceptance), plan show 1067-probe (done: target_url run id, then workflow path, then on: pull_request_review; run event alone does not classify). The diff 7f8a0d7..3fb3f40 does exactly that: gh.pr keeps target_url, gh.workflow_paths, evidence.review_contexts, ci_gaps.
- Read the host myself (gh api commits/<head>/status and check-runs): all seven PRs have every check run completed (success/skipped). Review Gate is pending on #3300/#3291/#3293/#3292/#3294/#3295 and failure on #3274, each target_url an ai-stacks actions run.
- Tie check: runs 38794777313 (#3300) and 38827960342 (#3274) have event pull_request_review, path review-gate.yml. Run 38867163408 (#3292) has event pull_request with the same path, which confirms the probe: classifying by path is needed. runs?event=pull_request_review paths = [claude.yml, review-gate.yml].
- Live evidence.gaps from a scratch copy at 3fb3f40 (python3 -I, temp workspace root): all six PRs read "waiting on review: Review Gate", actionable (no [waiting]); #3274 reads "change request outstanding: Review Gate"; blocking() contains both. The same script at main 7f8a0d7 gives "CI running [waiting]" for all six and "CI failing: Review Gate" for #3274, which is exactly the owner's report.
- Live board (board.text(board.compute)) at head: #3300 and #3291 show "waiting on review: Review Gate" with no [waiting]; #3274 shows "change request outstanding: Review Gate"; #3253 (also pending) is classified too. #3289/#3281 still show "CI running [waiting]", which is correct: real check runs are in progress and their Review Gate is success, which triggers no Actions read.
- Actions calls in the live board: one runs?event=pull_request_review read plus one per-run read for each unsettled status; no call for success statuses.
- Suite at head: 280 passed. Config five keys and runtime size tests passed; runtime lines = 3000.
- Mutants (copy, tests/test_evidence.py + test_guards.py), all killed: drop the unsettled filter, accept any repo's run URL, invert the path match, re-raise on Actions failure, swap the two review labels, never classify as review, always read workflows, no cache.
- Merge door: test_a_review_gap_holds_the_merge_with_or_without_auto (pending/failure x with/without --auto) passes at head.
- Docs: design.md section 6 (The evidence contract) and site evidence.md carry the rule; the #review-statuses anchor resolves to its heading. Explain-back in spec.md matches the promise and the seven acceptance scenarios; no claim beyond them.
- Confidence high: confirmed live on the real host before and after the change, and tests kill every guard mutant. It would drop if ai-stacks moved its gate to a check run, or if review-gate.yml fell out of the last 100 review runs.

## Residual risk
A CI workflow that also listens on pull_request_review would read as a change request (spec "How this fails" 1); the merge still holds. A newly added review workflow reads as CI for up to a day.
