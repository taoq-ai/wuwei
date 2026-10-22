Verdict: PASS
Gate: goal
Item: 1221
PR: taoq-ai/wuwei#1247
Head: ceb9c4596f7b0a4774114a484f8d6c5c8b8986df
Confidence: medium
Breaking: no

## Findings
- [low] charters/planner.md:41 blocks: no. "green CI stays a condition for ready" (also the PR body's first line) reads as if the ready door enforces it; the door refuses only a failing check, so a draft whose gates passed can be marked ready while CI still runs and only the shepherd charter (charters/shepherd.md:14) holds it. The door never held ready for running CI before this PR, so nothing regresses, and the first Assumptions bullet and spec.md Clarifications say it with an overturn condition. Owner note: issue step 3 reads "gh pr ready and merge still require green CI at the head", while the issue's acceptance and the plan promise name only a red check; if the owner wants the door to wait for green, that is a follow-up (ci_gaps already returns `CI running`).
- [low] charters/planner.md:43 blocks: no. The rewrapped paragraph left lines far over the file's wrap width (same in charters/_way.md:13); cosmetic, agents are rebuilt so no drift.
- [low] blocks: no. PR body: "Closes #1221" closes the issue although the running-CI reading of its step 3 is left to the charter by design; the Assumptions bullet is the record.

## Probes
- Trace: issue #1221 (Proposal 1 to 3, Acceptance 1 to 3) to plan item 1221 (promise and four acceptance scenarios) to specs/gates-at-push/spec.md (explain-back, FR-001..005, How this fails x3) to charters, board.py:123, guards.py:326-332. The explain-back matches the plan and the issue; it adds nothing unasked except the owner-exception path (below).
- Acceptance 1 (builder hands back without a CI read, CI unread): charters/builder.md:75-77 and agents/builder.md:204-206; pinned by tests/test_charters.py test_gates_start_at_push_in_parallel_with_ci_and_green_ci_still_holds_ready.
- Acceptance 2 (owed gates named with CI running and no gate seat): board.py:123 drops the old CI and required-check exclusions and keeps only `CI failing`; tests/test_watch.py covers CI running, no check started, a missing required check (duty shown) and a red head (no duty).
- Acceptance 3 (verdict attested while CI ran counts when CI turns green; no hook discounts it): tests/test_hook.py test_a_verdict_attested_while_ci_ran_counts_once_ci_turns_green_at_that_head; evidence.py lines 469-530 read, no path where CI state gates attestation or counting (CI only adds gaps).
- Acceptance 4 (gates passed and a failing check: ready and merge refused naming it; green passes): tests/test_guards.py test_a_draft_whose_gates_passed_stays_draft_while_a_check_fails_and_names_it (every READY route; red, running, green; exception at wrong head and unapproved) and test_a_merge_with_its_gates_passed_and_a_failing_check_is_refused_naming_it. The merge half passes at main and is pinned, as the PR says.
- Time saved reaches the seats: charters/planner.md:40-42 launches the gates "at that head at once, in parallel, while CI runs: do not wait for CI"; charters/builder.md:75-77 hands back as soon as the push lands; skills/wuwei-watch/SKILL.md:26-28 matches. A grep for remaining waits ("once CI has run", "wait for CI") in charters, agents and skills found none; the CI-green waits left are for ready and merge only (shepherd.md:14, _pr.md, _way.md). The planner charter is not copied into agents/, so no stale copy.
- Running CI and the ready door: not a breach of the promise as the plan states it ("the ready door refuses ... while a check fails"); pre-existing behaviour (the door read only the gate gap), so no regression; the PR discloses it under Assumptions with its overturn. Charter text consistently puts the wait for green on the seat, and _way says the door "refuses a failing check", which is accurate.
- Owner exception on a red head: the issue is silent; the exception reuses evidence.excepted as the merge door does, is per PR and per head (tests cover wrong head and unapproved), and avoids a stuck draft. Disclosed in the PR body and design section 7. Not a goal change.
- Counts read at the head: runtime `cat cli/wuwei/*.py | wc -l` = 3554 (PR: 3,554); `git diff --shortstat origin/main...HEAD` = 509 + 64 = 573 changed lines (PR: 573); sha256 of tests/fixtures/routes.json = de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (matches the PR). The suite and the route differential were not re-run (brief said not to run the full suite).
- Docs: design section 7 row and the doors and evidence site pages state the new ready refusal and the board line text.
- Confidence medium: text and tests traced, no suite, differential or mutant re-run; an owner reading of "require green CI" as a door condition would turn the first finding into a FIX.

## Residual risk
Gates may spend a round on a head CI later turns red (accepted by the issue; the delta rule bounds it). A draft can be marked ready while CI still runs if a shepherd ignores its charter; the merge door still holds a running head.
