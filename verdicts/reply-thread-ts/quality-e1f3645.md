Verdict: PASS
Gate: quality
Item: reply-thread-ts
PR: taoq-ai/wuwei#1232
Head: e1f3645f2fdaa2e969df1b8d850492fb558289e3
Confidence: medium
Breaking: no

## Findings
none

## Probes
- closed: forwarded or quoted link closes the owe (thread_ts branch matched channel and root ts as bare substrings) at e1f3645. My 11-case probe in a fresh git archive copy of e1f3645: the forward to C2 quoting the link stays open (it closed at ce7aec9, open at main); root ts in text only with channel C2 stays open; C12 for C1 stays open; thread_ts first, cid first, &amp; and angle-bracket links close on a send naming C1 and the root ts; a top-level link closes on its own ts and stays open on a channel-only send. Output read: "11 passed", CASE lines as listed.
- closed: the untested `thread[4] and` guard (my M5) at e1f3645. The guard is gone: keys are built per candidate place with `if ts`, so a None root ts yields no place and no `in None` TypeError. My equivalent mutant N5 (drop `if ts`) survives, but it only adds the key '"None"', which a real send would have to carry as the string "None", so it is a note and not a hole.
- closed: untested regex shapes (M6, M7, M10) at e1f3645: all three are now killed by behavioural tests (M6 by the stays-open test, M7 and M10 by the cid-first case).
- tests/test_watch.py at the head: 50 passed (own run, fresh copy). cli/wuwei and .claude/wuwei/cli/wuwei are identical (diff -r shows only __pycache__).
- Mutants, both hook.py copies, one at a time, tests/test_watch.py plus tests/test_review_request.py, 57 tests: killed by behavioural tests: N1 any to all (4 failed), N2 all to any within a place (4 failed), N3 drop root place (3), N4 drop own place (2), N6 unquote channel (1), N7 unquote ts (2), N8 drop channel key (1), M6 (1), M7 (1), M8 digits 9 (3), M9 group required (1), M10 (2). Survived: N5 (above) and N9, quoting the non-Slack place key, which is main-identical code the item does not change; untested, low.
- Standards line: the generated combinatorial probe of AGENTS.md "Testing the guards" does not apply. The change reads a Slack link in hook._replied, not a Bash command through guards.py; no door program, no stub on PATH, guards.py untouched. Replaced by the 11-case link-shape probe above (0 door runs, 0 holes at this head). Route corpus not re-run by me; the builder's 288 routes with 0 moves came with the earlier head.
- Behaviour change worth the owner's eye on the owner path: the own ts and channel of a link with no thread_ts now close only as whole JSON values, so a tool that sends the channel or ts inside a longer string (for example a combined "C1:ts" field) no longer closes. This is deliberate in the delta; for the Slack tool the item targets the fields are whole values.
- Simplicity: none to delete; the any(all(...)) form replaced the earlier two-branch condition and the thread[4] guard.

## Residual risk
Tools that carry channel or ts inside a longer string value stop closing owes; fail-open to "stays owed", the safe direction. Full suite and CI not re-run by me.
