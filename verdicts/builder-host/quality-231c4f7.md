Verdict: PASS
Gate: quality
Item: builder-host
PR: taoq-ai/wuwei#1251
Head: 231c4f74fb9f1ad1e67deb061dd73a9ddd0daf5a
Confidence: high
Supersedes: builder-host/quality-57d90a2.md

## Findings
none

## Probes
- Read the delta 57d90a2f..231c4f74 (two runtime lines, one per tree, and tests) and ran `git archive 231c4f74` in my scratch folder. test_plan, test_watch, test_flow, test_charters, test_setup: 378 passed (the vendored-copy match test included). `bin/wuwei agents check`: agents match the charters. Runtime 3710 lines; `cli` and `.claude/wuwei/cli` identical.
- Mutants one at a time on both trees, 6 run, 6 killed by behavioural tests: dropping `and item.get('session')` from the stale condition (killed by the new I-3 case in test_flow, on both trees); the reason reverted to string concatenation (killed by the new `plan session I-9` assertion in test_plan); the stale host clause dropped; the status check dropped; the hook reading `hosted=True`; the session guard in `running` removed.
- closed: stale-condition crash on an idle host-session item with no record (board.py:164) at 231c4f7 (the I-3 case expects `no pull request yet`).
- closed: `plan session <unknown id>` with no session id raised TypeError (__main__.py:37) at 231c4f7 (refused as `wuwei: I-9 is not in the plan`, asserted).
- Open notes carried, not blocking: a host-session item with a PR never goes stale, so a dead session builder after its draft PR shows only through `get_session`; a re-add without `--host` resets host to agent (intended, tested).
- Simplicity: none to delete; the fix replaced a concatenation with an f-string, no new code.

## Residual risk
The recorded session has no time bound, so a dead session is surfaced only by the no-PR stale row or the planner's `get_session` read.
