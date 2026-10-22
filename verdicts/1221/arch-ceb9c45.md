Verdict: FIX
Gate: arch
Item: 1221
PR: taoq-ai/wuwei#1247
Head: ceb9c4596f7b0a4774114a484f8d6c5c8b8986df
Confidence: medium
Breaking: no (minor, feat: the door now enforces the base shepherd rule 2, "Once CI is green and the gates the diff needs passed at the draft head, mark it ready"; an owner exception opens it; the PR's release notes name the stricter door and the changed board line)

## Findings
- [medium] cli/wuwei/guards.py:330 blocks: yes. Failure: the ready door reads CI through `evidence.ci_gaps(rollup)` with no review contexts, while `evidence.gaps` (evidence.py:496) passes `review_contexts(root, repo, rollup)`. A draft whose head carries a FAILURE commit status from a workflow the repo also runs on `pull_request_review` (a review gate that fails until approved) is read by `wuwei evidence` as `change request outstanding: Review Gate`, but the ready door refuses `gh pr ready` and `gh pr edit --add-reviewer` as `CI failing: Review Gate`. The review request that would clear that status is itself refused, so the PR stays stuck as a draft unless the owner carries an exception. This contradicts design.md:131-134 ("review evidence, not CI") and makes a second CI reader that disagrees with the first (design rule, contract). Fix: pass `evidence.review_contexts(root, repo, pr.get('statusCheckRollup'))` as `review`, with zero net lines, plus a test with the `review_gate` fixture shape on a draft.
- [low] cli/wuwei/guards.py:331 blocks: no. A red draft's refusal names only the failing checks and not the gate gaps, so a second refusal can follow once CI is green. This is recorded under Assumptions with what would overturn it.
- [low] blocks: no. The board's `owed` (board.py:123) now matches only `CI failing`, so a head that shows only `required check not run` after CI settled (the check will never run) owes a gate seat. This is harmless, because gates can read that head; the PR records it under Assumptions.

## Probes
- Diff read: `git diff origin/main...ceb9c459` (35 files). Runtime touches only board.py:123-125 and guards.py:329-332. Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows none at the head or the merged tree.
- Merge with main (#1239, #1244 in hook.py and guards.py): `git merge-tree --write-tree origin/main ceb9c459` is clean (tree b10bdd05). On that merged tree, in a scratch archive: test_charters, test_watch, test_hook, test_status_perf and test_setup gave 910 passed. `test_guards.py -k "draft or ready or merge or pr_standard or exception"` gave 449 passed. The full suite was not run (brief).
- Runtime budget, measured with `cat cli/wuwei/*.py | wc -l`: base 470ab63 3,551, head 3,554 (+3, the item's budget of 3), main 3,581, merged 3,584. That is under the 3,600 in test_setup.py:122 even before #1246 raises it.
- Charters as the one source: `bin/wuwei agents build` in a copy of the merged tree printed "agents match the charters". The sentence-word tests in test_charters (35 max, 20 average) passed.
- One source for CI: `git grep ci_gaps` shows two callers, evidence.py:496 (with review contexts) and guards.py:330 (without). Probe tests/test_probe_arch.py in the merged scratch copy used the drafts fixture with a `Review Gate` status from a pull_request run of a workflow also run on pull_request_review. With FAILURE, evidence gives `change request outstanding: Review Gate` and both `gh pr ready 7` and `gh pr edit 7 --add-reviewer bob` are refused as a failing check. With PENDING and SUCCESS, both pass.
- Exception path: ready_door calls the same `evidence.excepted(root, ref, head, gaps)` that `evidence.gaps` ends with, so the merge door and the ready door share one mechanism, keyed by PR and head prefix; it is not a copy. The new test covers the right head, another head and an unapproved ruling.
- Design section 7 and the gate row amended; docs/site doors.md and evidence.md agree with the code and the board line text. No other consumer of the old duty text exists (`git grep "green heads"`).
- Board layering: board.py still reads only evidence gap texts; there is no new import or cycle. guards.py already imports evidence.
- Breaking: the public API list (evidence.md:117-127) includes the hook output contract. The base shepherd charter already orders ready after green CI, and green CI was already required to merge, so no client gives a new input. Minor with release notes, which the PR body has.
- Confidence medium: the finding is shown by a probe, but how common a review gate that fails before review is in client repos is unmeasured.

## Residual risk
A flaky check now holds ready as well as merge until it is re-run (named in the spec's How this fails). After the fix, the review-context read adds one cached Actions call on a draft with unsettled statuses.
