Verdict: PASS
Gate: quality
Item: route-fixtures
PR: taoq-ai/wuwei
Head: ad6e9f0543cdf61fa3252badd0cb54671511b90f
Confidence: medium

## Findings
- [low] tests/test_guards.py:489 blocks: no. door_reached maps both the PR-standard note (create passes) and the create_door refusal to 'create', so the 'create' routes cannot tell a create guard that refuses from one that passes. Mutant: create_door skipped entirely, no every_route test fails (only the existing test_a_pr_opens_only_once_its_gates_pass_on_the_branch). Harm is limited: that test covers it, and the fixture's 'create' is the door reached, as the promise words it.
- [low] tests/test_guards.py:491 blocks: no. The 'refusal' verdict is any deny not matching the merge, push or create phrases, so a refusal route denied by a different guard (a ledger or secret deny) would still read 'refusal'. Pass and door routes are exact; only refusals are loose.
- [low] blocks: no. The canary scan falls back to the prefix 'wuwei-canary-' when .wuwei/canary is absent (as in a git archive); in the real workspace it reads the real canary.

## Probes
- Merged onto current origin/main (16205839, git archive of main plus the branch's tests/ and specs/): 524 passed, 2 skipped (ssh-keygen absent, pre-existing). git merge-tree of origin/main and the head is clean.
- No runtime change: git diff origin/main...head --stat -- cli is empty; the diff is tests, fixtures and specs only.
- Mutant, --admin check removed: fails exactly the route 'gh pr merge 5 --admin' (plus existing tests).
- Mutant, GUARDED_API branch off: fails the 8 refusal api routes and no pass route.
- Mutant, merge_door opens (returns None): fails all 5 merge routes, no others. Force-push check off: fails the 2 force routes. Default-branch push check off: fails 'git push origin main' and 'git push origin --delete main'. Repo delete off: fails the repo delete route.
- Mutant, a guard that refuses a pass route (the review_threads read, then the shepherd ping POST): each fails exactly its own route test. Acceptance 2 and 3 hold.
- Mutant, create_door skipped: no route test fails (first finding).
- door_reached: a wrongly refused or noted pass route fails; a merge, push or refusal route that passes fails; a wrong deny reason on a merge or push route reads as another door and fails. Loose spots are the two findings above.
- Secret scan reads every file under tests/fixtures with guards.SECRETS, the canary and local-path patterns (acceptance 4); it asserts files exist, so it is not an empty loop.
- Payload replay: each of the 7 payloads goes through hook.handle with no hook.error row and an exact seat.started or seat.stopped agent list per file (rejected and Pre payloads record none), plus a test that the directory holds exactly the listed files. Meaningful: removing the seat.started record in hook.py would fail the accepted and Codex payloads (read from code, not mutated).
- Acceptance coverage: all four scenarios have a test.
- Simplicity: none; the two corpus-shape tests guard the tables and are small.

## Residual risk
Create and refusal verdicts are coarse, so a guard change that moves a route between refusal reasons, or between a create note and a create refusal, will not show in the fixture diff. Mutants were run by hand on ten guards, not exhaustively.
