Verdict: PASS
Gate: quality
Item: flow-order
PR: taoq-ai/wuwei#1243
Head: be06fb72bdb29453864e04fe73a34c8325da5b93
Confidence: medium
Breaking: no
Supersedes: flow-order/quality-ded692c.md

## Findings
none

## Probes
- Delta ded692c..be06fb7: plan.py reaches() now takes a seen set (each id walked once), plus test_a_wait_on_a_merged_cycle_with_forks_is_checked_in_linear_time. Both trees carry it.
- Mutants on the seen check, both trees, test_flow.py, under `timeout 60`, one at a time: 7 of 7 killed, none hung or timed out. Seen test removed (`True and`), `not seen.add(key)` alone, `key not in seen` alone (never added), `seen.add(key)` (never walks), a fresh set per fork, a pre-filled seen set, and the self-id match removed. The fork test kills the first three and the fresh-set one; the cycle-refusal and self-wait tests kill the rest.
- closed: the untested depth-stop note (plan.py:81 at ded692c). The depth cap is gone; the fork test now pins termination on a merged cycle.
- Ran test_flow, test_plan, test_sync at be06fb7: 81 passed. test_watch and test_hook not re-run (the delta touches only plan.add).
- The 5-second bound in the test is a wall-clock check, but it separates a linear walk from a 2^99 one by a wide margin; the mutants fail by that bound or by RecursionError.
- Guard-parsing probes: not run, no guards.py or hook.py in the delta.
- Simplicity: none to delete. A chain of about 1000 waits would now hit Python's recursion limit where the old cap stopped at 99; a plan that size is not realistic, noted only.

## Residual risk
Low: a recursive walk over a very long wait chain.
