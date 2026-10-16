Verdict: PASS
Gate: arch
Item: 1067
PR: taoq-ai/wuwei
Head: b09b20469703ab3995713a84b5d95c259d03df04
Confidence: high
Breaking: yes: the merge door now refuses `gh pr merge --auto` (and the MCP auto-merge tools) on a PR whose review-triggered status is pending. Before this change that status read `CI running`, which guards.merge_door exempts under --auto, so arming auto-merge was allowed. Agents and owners who arm auto-merge early on repositories like ai-stacks now get a deny. The gap texts in `wuwei status`, the board and the Stop reminder also change from `CI running`/`CI failing: X` to `waiting on review: X`/`change request outstanding: X`. Acceptance 6 asks for this; the PR needs the Announcement: line and the owner's breaking: confirmation.

## Findings
- [low] cli/wuwei/evidence.py:349 blocks: no. Carried from arch-3fb3f40 and unchanged: the per-run read `actions/runs/<id>` is not cached, so every evidence read pays one call per unsettled review-candidate status. A run's workflow path never changes and could share the day cache.
- [low] cli/wuwei/evidence.py:348 blocks: no. Carried and unchanged: a failed list read is not cached, so a token without Actions read pays one failed request per evidence read (How this fails 3). The status stays CI, never a pass.
- [low] cli/wuwei/evidence.py:359 blocks: no. Carried and unchanged: failure and error map to `change request outstanding` without reading the reviews. This is recorded in the spec's Clarifications. The stale-approval duty now fires alongside it, which was the harm found in the previous round.

## Probes
- `git diff 3fb3f405 b09b2046`: one commit touching evidence.py (4 lines changed), tasks.md and tests/test_evidence.py. Nothing else changed since my previous verdict.
- The previous blocking finding (evidence.py:406, the stale-approval duty) is closed. The duty now matches `startswith(('CI failing', 'change request outstanding'))`. test_a_failing_review_gate_still_names_an_approval_at_an_older_commit asserts both gaps for the input I named. Reverting the fix in a scratch copy fails exactly that test.
- The previous low note on the surviving `paths and` mutant is closed. The mutant is now killed by test_a_repo_without_review_workflows_reads_no_run.
- The regex moved inside the try and TypeError is now caught. Mutant: dropping TypeError fails test_an_oddly_shaped_actions_reply_leaves_the_status_ci[reply0] and [reply1]. Mutant: removing the try fails test_an_unreadable_actions_host_leaves_the_status_ci. Catching more can only return set(), which leaves statuses as CI gaps, so it cannot produce a pass. A status with a non-string target_url now stays CI instead of escaping to `evidence unreadable`, which was non-actionable; that is the safer side.
- Full suite at b09b204 in a scratch copy (`python3 -m pytest -q`): 286 passed. Runtime lines from cat of cli/wuwei/*.py: 3000.
- Confidence high: the delta is small, every change is pinned by a test that I watched fail under its mutant, and nothing outside the fix moved.

## Residual risk
The live ai-stacks read (SC-001) is still unmeasured here because this session gets 403 from ai-stacks. The breaking --auto change rests on the owner's confirmation at the PR.
