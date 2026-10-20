Verdict: PASS
Gate: security
Item: 1178
PR: taoq-ai/wuwei#1188
Head: 120fb2a0f037e5c5cd065d34be7cce17f6cc0a1d
Confidence: high

## Findings
- [low] cli/wuwei/board.py:53 blocks: no. Untested guard (pre-existing line, more load now drafts pass it): dropping `evidence.item_for(root, pr, repo) is None` survives the suite twice in fresh copies. With it gone, a linked draft by the session login would show twice, under its item and as unplanned. That is a duplicate row, never a wrong-item link. Missing test: a linked draft by the session login shows under its item only.
- [low] cli/wuwei/evidence.py:426 blocks: no. CWE-1333 (inefficient regex), pre-existing: ITEM is quadratic on a crafted body with no match. A 64 KiB body of repeated `[WUWEI` takes 3.20 s in gaps() at main and 3.97 s at the head, because the new finditer adds one pass. The class and the attacker surface (any PR author's body) are the same at main and at the head. Bounding `[^\n]*?` in ITEM would close it.

## Probes
- Code read (git diff e5b9416..120fb2a): guards.py and hook.py are unchanged. The create and ready doors read the link through evidence.ITEM, item_for and gates_for, all unchanged, so the old line still names the item there. The only new reader is gaps(), which appends a gap whose text starts with "PR names its item by the old". PROCESS (start-anchored) classes that text as process, so blocking() drops it and the MERGED path (blocking only) never turns it into a post-merge escape.
- Route differential: all 263 routes in tests/fixtures/routes.json (sha256 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49 at both main e5b9416 and the head) run through guards.bash in scratch copies of each. The PR 5 and draft PR 7 bodies use the old line, the footer, and both. Each runs gapped (no test, no gate) and clean (quality PASS attested on o/r#5).
- Results: no route's verdict, decision or reason moves in any of the 6 scenarios. The gapped runs give push 34, refusal 103, pass 67, create 13, merge 25, ready 21 on both sides; the clean runs give pass 124, refusal 103, push 34, merge 2. The only move: with the old line clean, merge.checked gains exactly the old-line process text on 23 routes. Footer and both-link bodies move nothing.
- Exception-ruling differential: the owner's approved exceptions for "no test in the diff" and "quality" at the head were added to the gapped PR. Again no verdict or reason moves (pass 89, merge 3 on both sides). For the old line, merge.checked gains the line on 22 routes. Excepting the old-line gap itself empties the process list, and the merge still passes on both sides.
- Board adoption probe, main against head, PRs 60-70 in acme/app. The head newly lists exactly two own drafts as unplanned: #64 (unlinked) and #62 (footer naming the unknown item NOPE-9).
- Not listed at either side: another author's unlinked draft (#65), another author's ready PR (#67), a login differing only in case (#68) and a ghost author with an empty login (#69). So no other author's PR appears.
- Own drafts linked by the old line (#60), the footer (#61) or the branch name (#63) stay under I-1 only, never also as unplanned. Adopted rows carry item 'unplanned' only, and no consumer writes the plan from them (grep of 'unplanned' and 'prs' writers in cli/wuwei).
- Mutants, each applied to cli/wuwei and .claude/wuwei/cli/wuwei in a fresh git-archive copy and run one at a time. The suites were test_evidence, test_review_request, test_guards, test_replay, test_hook, test_plan, test_status_perf, test_view and test_watch.
- m1, the PROCESS alternative removed (the gap becomes safety and holds a merge): killed by test_the_old_item_line_alone_is_process_fit_that_names_the_footer, test_the_old_item_line_shows_on_the_full_board_only, test_a_merge_flows_past_process_gaps_and_records_them and test_status_perf.
- m2 (all to any): killed by test_the_old_item_line_alone. m3 (the empty-links guard dropped): killed by test_gaps_are_classed_as_process_or_safety. m4 (the isDraft skip restored): killed by test_an_unlinked_draft_by_the_session_login_shows_as_unplanned.
- m5 (the author filter dropped, which would show other authors' PRs): killed by test_a_pr_raised_by_hand_is_adopted_by_the_board, test_an_unlinked_draft_by_the_session_login_shows_as_unplanned and test_the_same_orchestration_state_reminds_once_while_the_pr_count_moves.
- m6 (the item_for filter dropped): survived twice; see the note above.
- Full suite at the head (uvx python 3.13, offline gh stub on PATH, CLAUDE_CODE_SESSION_ID unset): 2829 passed, 4 failed, 1 skipped. The 4 failures are the known bash 3.2 ones on main: test_codex hook shells and 3 test_bash_runs_the_push_in_each_refused_shape cases.
- CI at 120fb2a (gh api check-runs, read twice, the second after test (3.12) settled): 8 of 8 success, including CodeQL, Analyze (python, actions), ZIRAN and ziran-audit. Agent tooling, dependencies and workflows are unchanged, so no supply-chain surface is added.
- The head contains main e5b9416, and git merge-tree onto #1187's head (694ddd7) is clean. wuwei evidence taoq-ai/wuwei#1188 names this security gate and the owner review on cli/wuwei/evidence.py.
- Confidence is high: the code change is 5 lines, the door code is untouched, and the differential across 8 body and evidence scenarios shows no verdict or reason move.

## Residual risk
Unlinked drafts by the session login, up to 7 days old, now feed the Stop and SessionStart board. That brings their titles (self-authored) into model context and counts them toward the shepherd duty. This is the intended workflow, not a trust change.
