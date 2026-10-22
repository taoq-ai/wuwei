Verdict: PASS
Gate: arch
Item: flow-order
PR: taoq-ai/wuwei#1243
Head: ded692c8a56b16d88d83fc4749c67ad5145f1b52
Confidence: medium
Breaking: no (minor: new plan add options --class and --after, new plan fields and board row keys, a longer status row head and a new row order; the delta adds refusals only for new behaviour: a restore of a second expedite item and a wait that closes a cycle)
Supersedes: flow-order/arch-f834999.md

## Findings
- [low] cli/wuwei/plan.py:97 blocks: no. The cycle walk has a depth cap but no visited set, so on a plan that already holds a branching cycle (only from a sync merge or a hand edit: X after [Y, Z], Y after [X], Z after [X]) `plan add W --after X` walks about 2^49 paths and hangs; probe stopped it at 20 s. The comment "a merged cycle stops at 99" holds only for a non-branching cycle. A visited set fixes it in one line.
- [low] blocks: no. Carried notes from f834999: the aged score is read only in `wuwei status --json`, a waiter's cost of delay mixes units after a framework switch, and two clones each adding an expedite item still merge into two open expedite items (plan.merge does not run the expedite check).

## Probes
- Delta read: `git diff f834999..ded692c` (one commit, ded692c8 fix(board)), cli/wuwei/board.py, cli/wuwei/plan.py, the vendored copies, docs, tests/test_flow.py.
- closed: derived score restamps the item waited on, a concurrent edit is lost in plan.merge at ded692c (my f834999 stamp probe now passes: A not restamped, Y keeps "NEW promise from Y", score 2.6; new test test_a_rescore_never_stamps_an_item_so_another_clones_edit_wins_the_merge)
- closed: plan restore opens a second expedite item at ded692c (my probe now raises "E2 is already expedite"; plan.expedite runs in plan.add, including a re-add without --class, and in plan.mark when a closed item goes open)
- closed: a two-item wait cycle is accepted at ded692c (my probe now raises "B is not in the plan, or is this item or waits on it")
- closed: stage read after flow added stale or waiting gaps at ded692c (the stage is now computed from the row's own gaps before any is added; test_the_stage_is_read_from_the_rows_own_gaps_before_waiting_or_stale_text)
- closed: days counted from the last PR read at ded692c (rows sorted newest first so the first PR is written last; test_time_in_progress_counts_from_the_items_first_pr)
- Mutants in fresh git archive copies, applied to cli/wuwei and .claude/wuwei/cli/wuwei, `pytest tests/test_flow.py tests/test_sync.py` each run alone: stamp comparison back to whole-row equality killed by test_a_rescore_never_stamps...; mark expedite check removed killed by test_a_done_expedite_item_frees_the_class_and_a_restore_is_held_to_one; reaches recursion removed killed by test_a_wait_that_would_close_a_cycle_is_refused; add check back to cls only killed by test_a_done_expedite_item... (its re-add case). 4 of 4 killed.
- Tests in the ded692c archive: test_flow, test_setup, test_sync, test_status_perf, 93 passed (my two old acceptance probes now fail as expected, since they assumed the refused inputs were accepted). Full suite not run (the coordinator reports 3539 passed).
- Budget: `cat cli/wuwei/*.py | wc -l` 3535 at ded692c against 3448 on main (+87, within the stated cap of 90 and the 3,600 limit); vendored copy 3535 and `diff -r` shows no difference.
- Composition unchanged: one scoring system (plan.delay and plan.score), flow order by class, stale, stage and age; the stored score is still clock independent and now stamp neutral, matching the design.md text added in the delta.
- Confidence medium: each closed finding is shown by a probe and a killed mutant; sync merge was exercised through plan.merge, not a real push and pull.

## Residual risk
Plan states that only a merge or a hand edit can produce (a wait cycle, two expedite items) are not repaired at merge time; the board shows them but nothing refuses or reports them.
