Verdict: PASS
Gate: quality
Item: door-words-text
PR: taoq-ai/wuwei#1245
Head: 80d75535c4d20efd080bc0c342a4870a00a1cab9
Confidence: medium

## Findings
none

## Probes
- Delta read as the PR's own change to the door text, 01587bf..80d7553 in guards.py:366 and tests/test_guards.py. The door-words change is one edit: `.strip()[:40]` on each found word, plus the new test test_the_door_words_found_are_listed_each_once_and_bounded. The rest of the delta in `cli/wuwei` (hook.py, ws.py, the `known`/`again` block in `pre_tool`) and in tests (test_hook.py, transcripts) is the merge of origin/main, not this item. Both `cli/wuwei/guards.py` and `.claude/wuwei/cli/wuwei/guards.py` hold the `[:40]` cut. The decision condition is unchanged, so the earlier fail-open/closed reading stands.
- Closed: unbounded `.wuwei` echo at 80d7553. Length probe on 1 MB commands: slashes 333 bytes (was 1,000,305), dots 333, whitespace in `wuwei hook` 303, 30,000 lines naming all four groups 335. The 24 s scan time is the existing parser cost, unchanged from main.
- Closed: untested join at 80d7553. Mutant "list only found[0]" (applied to both trees, one at a time) is now killed by test_the_door_words_found_are_listed_each_once_and_bounded.
- New mutant dropping `[:40]` (both trees) is killed by the same test (the 1 MB slash run gives a reason over 1,000 characters). The test reaches the real consumer, `guards.pre_tool`.
- tests/test_guards.py on a git archive of 80d7553: 1959 passed. The coordinator reports 2003 passed for test_guards plus test_setup; I did not run the full suite.
- Runtime lines under `cli/wuwei` at 80d7553: 3582 of 3600 (this includes merged main code; the item's own runtime change stays +1 line).
- The cut at 40 characters cannot shorten a real door word (the longest is `.wuwei/ledger` or `wuwei hook`, under 15 characters), so the found text stays exact for ordinary commands.
Simplicity: none deletable; the cut is a one-token change to an existing expression.

## Residual risk
Message text only; the decision path is unchanged. A very long `.wuwei` run is now shown cut at 40 characters, which is acceptable for a hint.
