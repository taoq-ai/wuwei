Verdict: FIX
Gate: quality
Item: 1209
PR: taoq-ai/wuwei#1214
Head: 20f6127585b5e6e2e958f16aa74576b7f238d862
Confidence: medium
Breaking: no

## Findings
- [medium] tests/test_plan.py:289 blocks: yes. Failure: the repo guard is untested; reversing `item.get("repo") or ""` to `item.get("repo", "")` in cli/wuwei/__main__.py and its vendored copy leaves the new test green, and a null repo then prints the text "None" instead of a blank, which the promise names ("prints a blank for a null goal, tier, status or repo") (requirement 1209 promise). The test only asserts `'R-10' in out`, never the blank.
- [low] cli/wuwei/__main__.py:66 blocks: no. A null status prints "open" (the missing-key default), not a blank as the promise literally says; the acceptance (exit 0, item listed) holds. Either assert and document the "open" choice in the test, or print blank.

## Probes
- Archive copy of 20f6127 under the scratchpad (sentinel-quality-1209/a). tests/test_plan.py: 45 passed. Vendored-copy and budget tests: 10 passed; runtime is 3387 lines (under 3,400, no change from main).
- Mutants (each applied to cli/wuwei/ and .claude/wuwei/cli/wuwei/, run with `pytest -q tests/test_plan.py -k no_goal`): status reversed killed by test_the_plan_list_shows_an_item_with_no_goal (TypeError); tier reversed killed (TypeError); goal reversed killed (TypeError); repo reversed SURVIVED (1 passed). Re-ran each from a fresh copy.
- Real run with a plan.json holding goal, tier, status, repo all null: exits 0 and prints `      0  R-10       open                       t`; repo cell is blank at head.
- The new test is a real consumer (calls cli.main(['plan'])) and failed before the change for goal, tier and status (the mutants reproduce the old code).
- Other `item.get(k, default)` sites with a null hazard (plan.py:39 score, hook.py:83 tier/repo, view.py:72 tier escape) are outside this item's promise: note only, no verdict effect.
- No guard parsing touched; the combinatorial probe and route differential do not apply.

Simplicity: none; the four `or` defaults are the smallest change. The comment on the print line is the only extra and is fine.

## Residual risk
A null repo or status regression would pass the suite unseen. Fix is a one-line assertion on the output row (blank repo cell, for example `out.rstrip().endswith('t')` style check on the row) in the same test.
