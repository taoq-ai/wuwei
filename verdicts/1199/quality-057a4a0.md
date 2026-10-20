Verdict: FIX
Gate: quality
Item: 1199
PR: taoq-ai/wuwei#1207
Head: 057a4a0de505990802b14b50420519227cc5d3e8
Confidence: medium
Breaking: no

## Findings
- [medium] tests/test_evidence.py:593 blocks: yes. Failure: the CCR-route test now holds one reviewer-last and one owner-last unresolved thread, so reversing the guard at cli/wuwei/gh.py:109 (`not in logins` to `in logins`) still yields 1 and survives (re-run in a fresh copy of both trees, 0 tests fail); a CCR PR with one unresolved reviewer-last thread would then report 0 unanswered and the merge door would open (CWE-754 class, unanswered review reaching merge). The added owner thread made the test symmetric; the old single-thread fixture killed this mutant. Fix: assert on a fixture where the two counts differ (for example two reviewer-last threads and one owner-last, expect 2).
- [medium] tests/test_watch.py:260 blocks: yes. Failure: no test gives an owe two PRs, so changing `all` to `any` at cli/wuwei/board.py:35 survives (re-run in a fresh copy of both trees, 0 tests fail); an owe whose where names acme/app#7 (owner answered) and acme/app#8 (reviewer-last thread) would close while #8 still owes a reply. Fix: add a two-PR owe with one answered and one not, and assert it stays listed.
- [low] cli/wuwei/board.py:35 blocks: no. The 180-character line is within what the tree already holds (the base board.py already has a 180-character line, evidence.py 176, guards.py 160), so the length matches convention, but the comprehension packs the try comment, two network reads per PR and the chained `== 0 <` comparison into one line; splitting the owner-answered test into a named helper would read better and cost no lines if the two `p.split('#')` calls are shared.
- [low] cli/wuwei/board.py:35 blocks: no. board.replies now makes up to two uncached gh reads per PR-keyed owe on every board read (owner_login is cached a day, the thread reads are not); test_status_perf passes, but the cost scales with open owes and is unmeasured.
- [low] cli/wuwei/gh.py:96 blocks: no. The GraphQL route catches only GhError; a 200 reply with `pullRequest: null` raises TypeError, which board.replies (catches GhError only) now lets crash the board for an owe naming an inaccessible PR. gh normally exits non-zero on GraphQL errors, so I could not name a run that reaches it; a note only.

## Probes
- CI at head 057a4a0: test 3.11/3.12/3.13, Analyze (actions, python), CodeQL, ZIRAN, ziran-audit all SUCCESS (gh pr view 1207, read once).
- Suite at head from git archive, PATH with offline-gh, CLAUDE_CODE_SESSION_ID unset, no -x: 3001 passed, 1 skipped, 4 failed (test_the_hook_commands_run_under_either_harness_shell and three test_bash_runs_the_push_in_each_refused_shape cases), the four the brief names as failing on main in this shell. Vendored-copy match test passes.
- Mutants applied to cli/wuwei and .claude/wuwei/cli/wuwei together, run against tests/test_evidence.py, test_watch.py, test_status_perf.py, one at a time. Killed (17 tried, 15 killed): evidence owner dropped from logins (3 tests); evidence author dropped (2 tests); GraphQL null-author guard removed (test_a_thread_whose_last_comment_is_the_owners_is_answered_though_unresolved); GraphQL `in` for `not in`; GraphQL first login only; GraphQL last comment to first; CCR first login only; CCR resolved flag ignored; review-comments `in` for `not in`; review-comments first login only; board drop the at-least-one-thread guard (`== 0 <=`); board `== 0` to `<= 1`; board empty logins swapped for the owner; board GhError answered True (test_an_owe_keyed_to_a_pr_stays_open_when_its_threads_are_unreadable); board answered ignored. Survived, re-run fresh: CCR `in` for `not in`, board `all` to `any` (the two blocking findings).
- Acceptance coverage: scenario 1 (owner last not counted) and scenario 2 (reviewer last counted) are driven on GraphQL (test_a_thread_whose_last_comment_is_the_owners_is_answered_though_unresolved), CCR and review comments in their existing tests, but the CCR test cannot tell the two apart (finding 1). Scenario 3 (owe closes) is test_an_owe_keyed_to_a_pr_closes_when_every_unresolved_thread_ends_with_the_owners_reply, which reaches board.replies through the real consumer.
- Null author (deleted account): killed on GraphQL only; the CCR and review-comment routes get None from _author and count it unanswered by construction, with no test of that input there.
- Route differential (main versus head over tests/fixtures/routes.json): not re-run by me; the PR body reports 23 intended moves in an owner-last scene. This gate was asked for quality only.
- Confidence is medium: mutants and suite were run myself on the head; the route differential and the two-read cost are unmeasured here.

Simplicity: nothing to delete in the diff. The new `answered` expression in board.py:35 could be a short helper to replace the one-line comprehension, same logic. The removed `resolved` local in gh.py:105 is an inlined line, not a cut.

## Residual risk
After the two test fixes the guards are covered on all three read paths; the remaining risk is the unmeasured per-board-read gh cost and an unhandled TypeError shape on the GraphQL route.
