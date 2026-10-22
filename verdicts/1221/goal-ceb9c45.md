Verdict: PASS
Gate: goal
Item: 1221
PR: taoq-ai/wuwei#1247
Head: ceb9c4596f7b0a4774114a484f8d6c5c8b8986df
Confidence: medium
Breaking: no

## Findings
- [low] blocks: no. PR body (What and why, line 1) and charters/planner.md:41: "green CI stays a condition for ready" reads as if the ready door enforces it; the door refuses only a failing check, so a draft whose gates passed can be marked ready while CI still runs and only the shepherd charter (charters/shepherd.md:14) holds it. The door never held ready for running CI before this PR, so nothing regresses, and the first Assumptions bullet and spec.md Clarifications say it with an overturn condition. Note for the owner: issue step 3 reads "gh pr ready and merge still require green CI at the head", while the issue's own acceptance and the plan promise name only a red check; if the owner wants the door to wait for green, that is a follow-up (ci_gaps already returns `CI running`, so the change is small).
- [low] charters/planner.md:43 and charters/_way.md:13: the rewrapped paragraphs left lines far over the file's wrap width (the builder and shepherd edits are wrapped). Cosmetic; agents are rebuilt, so no drift.
- [low] blocks: no. The PR body's "Closes #1221" will close the issue although the running-CI half of its step 3 is by design left to the charter; the Assumptions bullet is the record.

## Probes
- Trace: issue #1221 (Proposal 1 to 3, Acceptance 1 to 3) -> plan item 1221 promise and four acceptance scenarios -> specs/gates-at-push/spec.md (explain-back, FR-001..005, How this fails x3) -> charters, board.py:123, guards.py:326-332. The spec's explain-back matches the plan and the issue; it adds nothing the issue did not ask for except the owner-exception path (below).
- Acceptance 1 (builder hands back without a CI read, CI unread): charters/builder.md:75-77 and agents/builder.md:204-206; pinned by tests/test_charters.py test_gates_start_at_push_in_parallel_with_ci_and_green_ci_still_holds_ready.
- Acceptance 2 (owed gates named with CI running, no gate seat): board.py:123 drops the old `CI `/`required check` exclusion and keeps only `CI failing`; tests/test_watch.py covers CI running, no check started, a missing required check (duty shown) and a red head (no duty).
- Acceptance 3 (verdict attested while CI ran counts when CI turns green; no hook discounts it): tests/test_hook.py test_a_verdict_attested_while_ci_ran_counts_once_ci_turns_green_at_that_head; I read evidence.py (lines 469-530) and found no path where CI state gates attestation or counting; CI only adds gaps.
- Acceptance 4 (gates passed + failing check: ready and merge refused naming the check; green passes): tests/test_guards.py test_a_draft_whose_gates_passed_stays_draft_while_a_check_fails_and_names_it (every READY route; red, running, green; exception at wrong head and unapproved) and test_a_merge_with_its_gates_passed_and_a_failing_check_is_refused_naming_it. The merge half passes at main and is pinned, as the PR says.
- Time saved reaches the seats: charters/planner.md:40-42 tells the planner to launch the gates "at that head at once, in parallel, while CI runs: do not wait for CI"; charters/builder.md:75-77 tells the builder to hand back as soon as the push lands; skills/wuwei-watch/SKILL.md:26-28 matches. grep for remaining waits ("once CI has run", "wait for CI") in charters, agents and skills found none; the only CI-green waits left are ready/merge ones (shepherd.md:14, _pr.md, _way.md). The planner charter is not copied into agents/ (only builder and shepherd are), so no stale copy.
- Running CI and the ready door: not a breach of the promise as the plan states it ("the ready door refuses ... while a check fails"); pre-existing behaviour (the door read only the gate gap), so no regression; the PR discloses it under Assumptions with what would overturn it. Charter text (shepherd, _pr, _way, builder) consistently puts the wait for green on the seat, and _way says the door "refuses a failing check", which is accurate.
- Owner exception on a red head: the issue is silent; the exception reuses evidence.excepted exactly as the merge door does, is per PR and per head (tests cover wrong head and unapproved), and avoids a stuck draft. Within the owner's trust model (exceptions are the owner's); disclosed in the PR body and design section 7. Not a goal change.
- Counts read at the head: runtime `cat cli/wuwei/*.py | wc -l` = 3554 (PR says 3,554); `git diff --shortstat origin/main...HEAD` = 509 insertions + 64 deletions = 573 (PR says 573); sha256 of tests/fixtures/routes.json = de377966...d71c1 (matches the PR). Did not re-run the suite or the route differential (told not to run the full suite).
- Doc medium: design section 7 row and the doors/evidence site pages state the ready door's new refusal and the board line text; the old text "gates owed on green heads" is gone from docs (grep on the diff).

## Residual risk
Gates may spend a round on a head CI later turns red (accepted by the issue; the delta rule bounds it). A draft can be marked ready while CI still runs if a shepherd ignores its charter; merge is still held by the merge door.
