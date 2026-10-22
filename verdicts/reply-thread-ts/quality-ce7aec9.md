Verdict: FIX
Gate: quality
Item: reply-thread-ts
PR: taoq-ai/wuwei#1232
Head: ce7aec9786c92ce6a3940395cfea12d07362809e
Confidence: medium
Breaking: no

## Findings
- [medium] cli/wuwei/hook.py:306 blocks: yes. Failure: the new branch tests `thread[1] in sent and thread[4] in sent` against the whole json.dumps of the tool input, so a send to ANOTHER channel or a DM whose text quotes the very link ("fyi, Omer asked here https://x.slack.com/archives/C1/p1729590000123456?thread_ts=1729580000.000100&cid=C1") holds "C1" (from /archives/C1/) and the root ts (from ?thread_ts=) and closes the owed reply with no reply sent into the thread; at main d7a574a the same send leaves R-1 open, because the old key was the dotted own ts, which a link never contains (CWE-697, requirement: closes only on a send that names that channel and the root thread ts). Fix: match the channel and root ts as whole JSON values, for example `f'"{thread[1]}"' in sent and f'"{thread[4]}"' in sent`, and add a test for the forwarded-link send.
- [low] cli/wuwei/hook.py:306 blocks: no. The `thread[4] and` guard is untested: with it removed (both copies) all 45 tests in test_watch.py and test_review_request.py pass, yet an owe on a top-level link plus a send that names the same channel without a ts raises `TypeError: 'in <string>' requires string as left operand, not NoneType` in the hook (printed as "wuwei hook PostToolUse: TypeError"), aborting the loop over the remaining owes. Missing test: a top-level-link owe, a send naming only its channel, assert open and no error.
- [low] cli/wuwei/hook.py:305 blocks: no. Regex shape mutants survive: dropping `\b`, restricting thread_ts to directly after the p-ts (`\?thread_ts=`), and `\S*?` to `[^&]*?` all pass 45 tests. The cid-before-thread_ts shape (`?cid=C1&thread_ts=...`) works at head (probe) but no test pins it, so a later narrowing of the regex would break it unnoticed.
- [low] blocks: no. Slack app links (https://app.slack.com/client/T1/C1/thread/C1-<root>) have no /archives/ path, so they fall to the whole-URL key and never close; same at main, so a note and not part of this item's promise. Channel matching is a bare substring (C1 in C12), an existing looseness the new branch inherits.

## Probes
- Red/green: at base d7a574a with the head's test file, 1 failed (test_a_send_into_the_thread_closes_a_reply_owed_on_a_message_inside_it), 37 passed; at head 38 passed. The "either" own-ts test and the stays-open test pass at base by design; they were checked by mutant, not by red.
- Mutants run one at a time on both cli/wuwei/hook.py and .claude/wuwei/cli/wuwei/hook.py (pytest tests/test_watch.py tests/test_review_request.py): killed by behavioural tests: M1 drop root-ts branch (the in-thread close test); M2 drop channel check in the branch and M3 drop root-ts check (test_a_thread_reply_stays_owed_on_another_channel_or_thread); M4 drop the own-ts alternative (test_a_send_into_the_thread_closes_the_reply_by_itself, which shows the "either" half is pinned both ways: M1 and M4); M8 thread_ts digits 10 to 9; M9 thread_ts group made required. Survived: M5 drop `thread[4] and` (finding 2), M6 drop `\b`, M7 thread_ts only directly after the p-ts, M10 `[^&]*?` (finding 3).
- Link shapes read through hook.handle at head (my probe, 11 cases): `?thread_ts=R&cid=C1` closes; `?cid=C1&thread_ts=R` closes; `&amp;` closes; angle-bracket `<url|text>` closes; top-level link plus channel only stays open; top-level link plus own ts closes. App link stays open (note). Probe at main: all thread_ts shapes stay open, which is the bug the item fixes.
- Looseness probe (finding 1): forward of the link to C2 closed at head, open at main. Link text in channel C2 with "C1" and root ts anywhere in the payload also closes at head, open at main.
- Parser probe of AGENTS.md "Testing the guards": does not apply. The change reads a Slack link inside hook._replied, not a Bash command through guards.py, so no door program, no stub on PATH and no route corpus move (guards unchanged; the builder reports 288 routes, 0 moves, which I did not re-run). Replaced by the 11-case link-shape probe above, hand-written across spelling classes (param order, escaping, wrappers, other channel, forwarded link). Probe: 11 cases generated, 0 ran a door program (not applicable), holes: 1 (finding 1).
- Vendored copy: cli/wuwei and .claude/wuwei/cli/wuwei are identical at the head (diff -r shows only __pycache__).
- Simplicity: none to delete. The branch could fold into one expression by building the key list per candidate (own ts, then root ts) and using any(all(...)), which would drop the `thread and thread[4]` guard and the None TypeError hazard; optional.
- Closed: none (first round).

## Residual risk
A forwarded or quoted link closes an owed reply wrongly until finding 1 is fixed; the gate is on an owner path, so owner review should look at the match rule. Full suite and CI not re-run by me.
