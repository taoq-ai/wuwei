Verdict: PASS
Gate: quality
Item: draft-raise
PR: taoq-ai/wuwei
Head: 02be6b9d05864d882c0e21f0c7a5b5fbef2e0bed
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:208 blocks: no. The `len(segments(command) or ()) == 1 and` clause is now an equivalent mutant (forced true, 684 tests still pass): the allowlist excludes `;`, `&`, `|` and newlines, so a multi-segment command already fails the all(...) check. Delete it; that also frees a line at the cap and drops a segments() call.
- [low] cli/wuwei/guards.py:209 blocks: no. Allowing whitespace in the allowlist, or dropping `:` from it, survives; neither lets a bad input through (a quoted word with a space is not a shell expansion, and a missing `:` only makes an --input draft read as not a draft, which denies). Notes only.

## Probes
- Suite at 02be6b9 in a clean worktree: 918 passed, 2 skipped (pytest -q -p no:cacheprovider).
- Size: wc -l cli/wuwei/*.py = 3000, which tests/test_setup.py asserts as at most 3000.
- Vendored .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py (cmp).
- No em dashes, en dashes or emoji in the added lines of the delta (scan of non-ASCII above U+2000: none).
- Mutants caught: allowlist check forced true (8 failed); `.` or `/` or `=` or `@` dropped from the allowlist class (5 failed); the `gh` first-word check turned into `or` (23 failed); PR segment on the merge route reverted to `(\d+)` (4 failed) and on the ready route (6 failed); the `[^/]*` suffix removed from merge (3 failed) and from ready (5 failed).
- Mutants surviving: the segments check (equivalent, finding above); whitespace and `:` in the allowlist (no bad input, notes above).
- Simplicity: delete the `len(segments(command) or ()) == 1 and` clause; the allowlist replaces it.

## Residual risk
The allowlist and the PR segment pattern read endpoint shapes the way gh and GitHub do; an unknown shape fails closed (an --input draft reads as not a draft, a PR segment without digits meets no door but then is not a PR route).
