Verdict: PASS
Gate: quality
Item: flow-order
PR: taoq-ai/wuwei#1243
Head: ded692c8a56b16d88d83fc4749c67ad5145f1b52
Confidence: medium
Breaking: no
Supersedes: flow-order/quality-f834999.md

## Findings
- [low] cli/wuwei/plan.py:81 blocks: no. Untested: removing the `depth < 99` stop in reaches() passes tests/test_flow.py. Input: a plan.json that already holds a cycle (A after B, B after A, as two clones can merge to) and then `plan add C --after A`; the head accepts it (C is not in the cycle), the mutant dies with RecursionError. A test with a hand-written cycle would pin it.
- [low] cli/wuwei/plan.py:149 blocks: no. Untested: dropping `!= item.get('status')` from the reopen check in mark() passes; it matters only when two open expedite items already exist (a merge) and an evidence run marks the first open again.

## Probes
- closed: plan.py:55 closed-waiter guard at ded692c. test_a_closed_waiter_stops_adding_its_cost_of_delay[done|dropped|parked] kills the mutant (re-run in a fresh copy, both trees).
- closed: plan.py:89 one-expedite status guard at ded692c. test_a_done_expedite_item_frees_the_class_and_a_restore_is_held_to_one kills the mutant (fresh copy, both trees).
- closed: stage order of a waiting row at ded692c. Stage is read before flow adds waiting or stale gaps; test_the_stage_is_read_from_the_rows_own_gaps_before_waiting_or_stale_text kills the mutants that read no gaps and that move building to the fix-round stage.
- closed: the cycle note. plan.add refuses a wait that reaches the item; kills: reaches without the transitive walk, without the stored after lists, depth < 0, all by test_a_wait_that_would_close_a_cycle_is_refused.
- Delta mutants (both trees, test_flow.py, one at a time): 13 meaningful killed (cost open filter, expedite status, mark reopen check removed whole, add inheriting the stored class, transitive walk, waits lookup, depth bound 0, stamp ignoring score restored to plain compare, stamp comparison perturbed, first-PR days order, stage gaps emptied, building stage). Survivors: the two notes above and two no-op edits of mine (not findings).
- Stamp: test_a_rescore_never_stamps_an_item_so_another_clones_edit_wins_the_merge shows a score-only change leaves `changed`, and clone Y's promise edit wins the merge while the score follows. The comparison still stamps a real edit (title or promise), killed by the test.
- Ran test_flow, test_plan, test_sync, test_watch at ded692c: 153 passed. test_hook not re-run (delta does not touch the hook or its input).
- Guard-parsing probes: not run, no guards.py or hook.py in the delta.
- Simplicity: none to delete; expedite() replaces the duplicated check in add and mark, and the stage moved inline into flow (one caller).

## Residual risk
A plan holding a merged wait cycle is handled by the depth bound but untested; the board still shows its members as waiting.
