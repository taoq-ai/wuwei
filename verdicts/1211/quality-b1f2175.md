Verdict: PASS
Gate: quality
Item: 1211
PR: taoq-ai/wuwei#1219
Head: b1f21754742d86c6119e15e867b349c33d590394
Confidence: medium
Breaking: no
Supersedes: none

## Findings
- [low] tests/test_hook.py:839 blocks: no. The test pins the parse path only. conftest.answered writes the answer row into the transcript before PostToolUse, so _shown passes at once; the real order (the harness writes the row after PostToolUse returns) and the real free-text row shape are not exercised, and tests/fixtures/transcripts/ask-flow.jsonl holds only an option-label answer. #1211's cause stays unmeasured by any test; the PR is right to leave the issue open.
- [low] tests/test_hook.py:849 blocks: no. Mutant view.py `day < d < ws.today()` changed to `day <= d < ws.today()` survives: the test does not pin the boundary of "not asked again" (a ruling made on the goal's own date). That is existing view code the item does not change; a note only.

## Probes
Ran at b1f2175 in a git archive copy (pytest -q tests/test_hook.py -k free_text_goal): 3 passed (3 collected, 0 skipped), 446 deselected. Each mutant was applied to both cli/wuwei/ and .claude/wuwei/cli/wuwei/ and run alone.
Mutants killed by the test: yes-prefix removed from startswith (fails on 'Yes, and close the item too'); goal.met ruling not recorded (fails on the No case); answer stored as first word only (fails on the No case, so the full text is pinned); approved flipped (fails); goal outcome blanked in the ruling (fails, so goal_status no longer matches and the goal is asked again); goal_status ignoring the ruling (fails, so "not asked again" is real).
Mutants surviving: the day<=d boundary above (not this item's change); a mutated default for an unknown goal id (not reachable in this test, equivalent here).
The test does not fail on main by design: it passes on main, so it is a pin, not a red-first test. That fits the promise ("a regression test pins"), which says the parse already records it.
Claim check (hook.py _confirm, _shown, _answers at the head): the text "is not recorded" in the issue is produced only by _unconfirmed (hook.py:321), reached only through _shown or transcript_rows returning None. _answers cannot emit it. _shown compares the whole answers dict of the call with the last toolUseResult.answers, so one answer that differs in the transcript voids every answer in the batch, which matches the issue's second case (a free-text answer voiding the labelled one). The cause named in the PR is supported by the code. The exact reason (what the transcript row holds for a free-text answer) is not in the repository; it sits in the workspace ledger, and I did not measure it.
Acceptance scenario: one goal.met ruling, approved false, full text, goal not asked again: asserted by the first parameter. The Yes and bare 'Nope' cases add coverage of the first-word rule.
Test quality: no wall-clock, network or shared-file dependence beyond the repository's own fixtures; asserts on rulings and goal_status, not prose. Runtime budget: 0 lines of runtime code changed (diff is tests/test_hook.py, +15).
Parser/guard probes: not applicable, no guard or parser code changed.
Simplicity: the inline `import datetime` and `from wuwei import view` could move to the module header if the module does not already import them; otherwise none. The 'Nope' case could be dropped without loss of mutant kills, but it is cheap.

## Residual risk
#1211 itself (free-text answer failing transcript confirmation) is unfixed and untested; the next item needs the real free-text toolUseResult row to reproduce it.
