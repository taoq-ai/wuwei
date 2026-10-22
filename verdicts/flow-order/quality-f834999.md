Verdict: FIX
Gate: quality
Item: flow-order
PR: taoq-ai/wuwei#1243
Head: f83499971cc36616632c52b9247eb27082d352da
Confidence: medium

## Findings
- [medium] cli/wuwei/plan.py:55 blocks: yes. Failure: the guard that counts only open waiters in cost() has no test. With it removed (mutant, both trees) tests/test_flow.py passes (27/27). Input: I-2 added with --after I-1, then I-2 marked done or dropped; the head rescoring gives I-1 score 10.0, the mutant leaves 20.0, so a closed waiter keeps inflating the priority of the item it no longer waits on (requirement: the item "others wait on adds their cost of delay"; a closed item waits on nothing).
- [medium] cli/wuwei/plan.py:89 blocks: yes. Failure: the status == 'open' guard on the one-expedite rule has no test. Without it (mutant, both trees) test_flow.py passes. Input: expedite X is done, then `plan add Y --class expedite` is refused with "X is already expedite" forever, so the owner can never start another expedite item after the first finishes (requirement: at most one expedite item is in progress).
- [low] cli/wuwei/board.py:140 blocks: no. Untested: changing the building stage (no PR, 4) to the fix-round stage (3) passes test_flow.py; no test puts a PR-less item behind an item with a PR.
- [low] cli/wuwei/plan.py:57 blocks: no. Untested: narrowing `except (ValueError, KeyError, TypeError)` to `ValueError` passes test_flow.py; the hand-edit test hits only the ValueError path.
- [low] cli/wuwei/plan.py:89 blocks: no. `plan add` accepts a cycle (A after C after B after A). Probed: all three show "waiting on", none is listed in the Stop reminder, no loop or crash in cost (it is one level, not transitive, so a chain adds only direct waiters). The three items go silent; nothing refuses or names the cycle.
- [low] cli/wuwei/board.py:140 blocks: no. A waiting row has its gaps made non-actionable before stage() reads them, so a waiting PR whose only open gap is a red CI or a fix round reads as stage 0 (ready to merge) and floats to the top of its class. Rows with gates owed stay at stage 2.
- [low] blocks: no. A rescore stamps `changed` on the base item when a waiter closes, so that derived change can win a merge over another clone's real edit to the same item (title, promise) made in the same window; an unchanged score does not stamp.

## Probes
- Ran tests/test_flow.py, test_plan.py, test_sync.py, test_watch.py, test_hook.py at the head: 694 passed, none skipped by the run.
- Acceptance: the four criteria each have a test in tests/test_flow.py through board.compute, board.text and hook.handle (Stop); the one-expedite refusal goes through plan.add and the CLI (exit 2).
- Mutants in a git archive copy, both trees, test_flow.py only, one at a time: 20 killed (stale before stage, class index, stage key, age key, live-seat check, 4h threshold, open-waiter filter in board, waiting made non-actionable, fixed-date default, Fibonacci clamp, step per day, time-in-FIB, self-wait refusal, expedite id exclusion, rescore in save, waiting term, stored-score fallback). Survived: plan.py:55, plan.py:89, board.py:140, plan.py:57 (findings above). A comment-text mutant also survived and is not a finding. Re-ran 11 and 14 in a fresh copy: both survive; the probe shows the harm (A score 20.0 stays 20.0 after the waiter is done; second expedite refused after the first is done).
- Sort: key is (class index, not stale, stage, opened or added or ''), a stable sort; ties keep input order; missing dates sort first as ''; a bad class falls to standard; a hand-edited score or date does not break the board (test). Dates mix ISO forms as strings, which orders correctly for same-format values.
- cost: no recursion, so a waiter cycle, a chain and a case-different id (compared lowercase) cannot loop; probed with A/B/C cycle: scores 20.0 each, board and Stop returned.
- changed stamp (#1238): save() rescores without aging (days None), so a plan whose stored scores already equal the rescore is unchanged; probed two extra saves with a waiter: `changed` identical. A merge of another clone's already rescored items does not stamp. Not every save churns it.
- Stop reminder (#1099): lines are `item (pr): gap text` compared as a set; reordering does not make a line new; the stale gap text holds the last-event minute, constant until an event. test_hook's unchanged-reminder tests pass.
- Probes for guards/hook parsing (route corpus, bash combinatorial): not run, the diff touches neither guards.py nor hook.py.
- Simplicity: none to delete; the stage()/flow() split is used; `when` is the only date reader added. The `delay`/`score` split is the shared numerator, needed.
- Not probed: wall-clock, ordering or shared-file flakiness beyond the five-hour and four-hour tests using ws.now() relative to the clock (they pass with margins of an hour).

## Residual risk
Ordering and waiting are covered by behaviour tests; the two closed-item guards need one assertion each. A cycle of waits is silent.
