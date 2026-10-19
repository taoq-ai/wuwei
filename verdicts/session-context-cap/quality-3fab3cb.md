Verdict: FIX
Gate: quality
Item: session-context-cap
PR: taoq-ai/wuwei#1149
Head: 3fab3cb650f206a9bf7834fd2dcb83cb8722778d
Confidence: high

## Findings
- [medium] tests/test_charters.py:292 blocks: yes. Failure: the 9,900 board room (cli/wuwei/hook.py:303) is the only thing that keeps the left-out line whole, and no test pins it. Mutant X1 (`> 9900` to `> 10000`) and X2 (`> 9990`) both survive all 5 session_start tests. On the test's own 40-item input, X1 returns exactly 10,000 characters ending in "11 more items left out; `wuwei status` lists them a". Across 60 title lengths X1 cuts the line in 15 boards and drops the count entirely in 7 (for example 40 items titled 'fix: ' + 112 'y'). Head cuts it in 0 of 60. That breaks acceptance 2 and FR-003 ("says how many items were left out") with the suite green. The test asserts `<= SESSION_CAP` where acceptance 2 says "stays under 10,000", and its regex `^(\d+) more items left out` still matches a cut line (test-quality class: an assertion that still passes with the change removed). Fix: for items=40, assert `len(text) < SESSION_CAP` and that the text ends with the whole line `f'{items - shown} more items left out; `wuwei status` lists them all.'`. Either assertion kills X1 at the existing input.
- [low] cli/wuwei/hook.py:303 blocks: no. Limit, recorded in the spec (A3): the trim drops lines from the end of board order (replies, then repositories by name, then items with no repository), not the lowest scores. Ran through bin/wuwei: on a two-repository board with acme/app at scores 1.0x and zeta/app at 90 to 71, the context drops 12 zeta/app items, the highest scores on the board, and keeps every low-score acme/app item. The left-out count and the `wuwei status` pointer make this visible. A board-wide score order would need board.py.
- [low] cli/wuwei/hook.py:303 blocks: no. A board that ends in a line other than an item (an andon reason or a gap text that holds a newline) stops the trim. The final `[:10000]` then cuts mid-line and can drop the left-out count. The cap holds, and the third test pins the cut at exactly 10,000. GhError keeps a single stderr line (gh.py:18), so the remaining source is a multi-line andon reason. Recorded in the spec (How this fails 2).
- [low] cli/wuwei/hook.py:298 blocks: no. Untested: mutant X5 (drop the `\Z` arm of the lookahead) survives, because Done is not the last section of _common.md today. The arm guards against a reorder of the charter. Keep it; no deletability claim, no differential run.
- [low] cli/wuwei/hook.py:297 blocks: no. Untested, and already untested at main: mutant X10 (drop the `is_file()` fallback in `read`) survives, since every charter is present in the tree. Mutant X4 (`startswith('- ')` to `startswith('-')`) survives too. No board line starts with '-' without a space, so I make no equivalence claim and ran no differential.

## Probes
- The 3 new fitness tests fail on main's hook.py, run in a copy of the head tests: 16,100 characters for an empty workspace, 28,646 for 40 items, 29,170 for 30 andons. All 3 pass at the head.
- The tests call hook.handle, which main() calls after it reads stdin. Through the real door, `bin/wuwei hook SessionStart` with a stub gh on PATH and a JSON payload on stdin: main gave 16,101 / 22,619 / 22,609 characters (empty / 40 items / two repositories). Head gave 5,344 / 9,798 / 9,953, with the CLI line and the planner.md path present and 13 and 12 items counted as left out (tools/harness.py).
- measure.py at the head with 3,000-character goals and standards: 5,229 characters empty; 9,846 for 40 items (28 shown, 12 left out); 9,847 for 200 items (28 shown, 172 left out).
- Builder's mutants.py rerun at the head in fresh git archive copies: 8 mutants, 8 killed, 0 holes.
- My mutants, each in a fresh git archive copy, with the 5 session_start tests: X3 (drop the item-line guard), X6 (drop re.S), X7 (count not incremented), X8 (parts not counted) and X9 (cut at 10,001) were killed. X1, X2, X4, X5 and X10 survived. I reran X1 in its own fresh copy: it survived, and the countline probe gave 15 of 60 left-out lines cut and 7 counts lost, against 0 at the head.
- Suite at the head: `pytest -q` gave 1780 passed, 2 skipped (test_release.py, ssh-keygen is absent). 5 session_start tests collected, none skipped.
- CI at the head, read once with `gh api repos/taoq-ai/wuwei/commits/<head>/check-runs`: CodeQL, ZIRAN, Analyze (actions, python), test 3.11/3.12/3.13 and ziran-audit all succeeded.
- Runtime lines: hook.py went from 391 to 394 lines and cli/wuwei/*.py from 2,992 to 2,995 (wc -l), so +3 against a budget of 6. The vendored .claude/wuwei/cli/wuwei/hook.py is byte-identical to cli/wuwei/hook.py (diff).
- Readability: session_start is dense (a lambda with noqa E731, an inline regex in the parts list, a conditional inside join). Both the lambda and the line lengths match this repository's habits (8 other E731 lambdas in cli/wuwei). The precedence of `lines + [...] if cut else lines` is correct. Not a finding.
- Confidence is high: the code meets the cap in every probe through the real door, and the one blocking finding is a test that does not pin acceptance 2. The mutant and the concrete inputs reproduce it.
- Simplicity: none. Each line carries the cap, the pointer or the count. The `\Z` arm and the `is_file` fallback are fail-safe handling for a charter reorder or a missing file, not code to delete.

## Residual risk
The planner now gets planner.md, goals and standards only by path. A planner that skips the pointer misses those rules (the spec records this). On multi-repository boards the trim drops the highest-scored items when they sit in the last repository.
