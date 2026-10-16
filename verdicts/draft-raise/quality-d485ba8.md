Verdict: PASS
Gate: quality
Item: draft-raise
PR: taoq-ai/wuwei
Head: d485ba8e186600331d864dccf7e37db02fb3e210
Confidence: medium
Breaking: no

## Findings
- [low] blocks: no. The segments() clause noted at the previous head (`len(segments(command) or ()) == 1 and`, an equivalent mutant) is still in cli/wuwei/guards.py; deleting it would free a line at the 3000 cap. Carried over, not new.

## Probes
- Suite at d485ba8 in a clean worktree (merge of origin/main 034d067 included): 930 passed, 2 skipped (pytest -q -p no:cacheprovider).
- Size: wc -l cli/wuwei/*.py = 3000, which tests/test_setup.py asserts as at most 3000.
- Vendored .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py (cmp); the agents drift test passes in the suite.
- The fix is the four in-place lines: `[0-9]` for `\d` in the two API routes and the PR URL pattern, `isascii() and isdigit()` in _repo_number and pre_tool. Mutants, each caught: merge route back to `\d` (1 failed); ready route back to `\d` (3 failed); URL pattern back to `\d` (1 failed); _repo_number isascii removed (3 failed); pre_tool isascii removed (1 failed).
- Merge check: skills/wuwei/SKILL.md moved to skills/wuwei-rules/SKILL.md with the draft edits carried (the draft and gates lines are at lines 28 and 41 there); skills/wuwei-watch/SKILL.md kept its edits; no routes.json source cites the old skills/wuwei path, and every charters, skills and docs line cited in routes.json sources is within its file (script over tests/fixtures/routes.json).
- Non-ASCII in the added lines is only the fullwidth digits in the spec artifacts and the `gh pr merge ７` route, which are the test input for this fix; no em dashes, en dashes or emoji.
- Simplicity: delete the equivalent segments() clause as above; nothing else.

## Residual risk
Number parsing now accepts ASCII digits only on every path; any other Unicode shape reads as no number and the door denies, so the risk is friction, not a gap.
