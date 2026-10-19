Verdict: PASS
Gate: arch
Item: goal-met
PR: taoq-ai/wuwei#1145
Head: edf2739ba759c76b8f1de8bc26cbba8adc42f6a8
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/hook.py:264 blocks: no. A goal.met answer for an id that goals.md does not hold records `outcome: ''`. If the owner later adds that id with no Outcome line, the new goal starts out met. Probe (edges.py, case 4): a yes to `goal: G-5 met?` with no G-5 in goals.md, then `## G-5` added with only a Date, gives goal_status met ['G-5'] and `Met goals: G-5.`. The pass never prints an absent goal, so a planner has to invent the question, and the seeded template carries an Outcome line. That makes this an edge, not a promise break. Cheapest fix: record no ruling, or a note, when goals.md does not hold the goal.
- [low] cli/wuwei/view.py:42 blocks: no. If goals.md has two headings that differ only in case (`## G-1` and `## g-1`), both become G-1. The hook takes the last Outcome, and goal_status lists both, so the pass offers G-1 while the report lists G-1 as met (edges.py, case 5). goals.md is malformed in this case. Noted for the record.
- [low] cli/wuwei/report.py:29 blocks: no. Carried from 0039ce2 and narrowed. `report.day(root, <past day>)` now reads today's goals.md as well as every ruling, so a past report shows the current met set. This is a limit on past reports. The all-days Assumption covers it.
- [low] blocks: no. Carried: a goal held by a no still shows nowhere (no `Held goals:` line). Also carried: the lead learns of met goals only through charter text, and `plan add --goal` accepts a met goal. Both are follow-ups, outside the promise.

## Probes
- closed: a goal.met ruling keyed by bare G-n (view.py:42) at edf2739. The hook now records the Outcome from view.goals, and goal_status keys rulings by (goal, Outcome). Re-ran sentinel-arch-goal-met/probe/reuse.py on a git archive copy of the head. Before the rewrite: ([], ['G-1']). After the owner rewrites G-1 in place: ([('G-1', '2026-10-10')], []), and `Met goals: none.`. test_a_goal_the_owner_rewrites_in_place_is_a_new_goal covers it.
- closed: the untested `.upper()` lookup at edf2739. Mutants no-upper-in-status and no-upper-in-hook are each killed by test_a_plan_pass_offers_each_goal_whose_date_passed_once (the g-10 and g-11 headings).
- closed: SKILL.md step order at edf2739. Step 1 now reads the measure as step 5 says before asking.
- Decision check: keying by Outcome text settles that a goal is its id plus its exact Outcome line. The spec records this under Assumptions: a typo fix asks the owner again, it fails toward asking, and it is overturned if owners often reword outcomes. design.md:50 states the rule. edges.py shows a typo fix after a yes, and also after a no, makes the goal due again. Trailing whitespace and the key's case do not (view.goals strips the value and matches the key without case). Restoring an earlier Outcome brings back the ruling given for it. This is a two-way choice: rulings keep both goal and outcome, so dropping the key later is cheap. It is recorded, so it is not a finding and not ESCALATE.
- Merge check: edf2739 merges main dc39cae. Main's runtime changes are in hook._verdict_problem (the next free verdict name), board.compute (a thread pool), ws.atomic_write (a thread-id temp name) and guards.py. None of them touches _answers, goal_status, view.goals, ws.record or ws.rows (git diff 5e90651 edf2739 -- cli/wuwei). `git diff dc39cae edf2739 --stat -- cli/wuwei` shows only the item's four files. The test_hook.py conflict was append-only.
- Suite at the head (git archive copy): /root/.local/bin/pytest -q gave 1884 passed, 2 skipped.
- Spot mutants (fresh copies of the head with the .claude mirror mutated too; test_plan, test_hook and test_report run): all 4 killed. key-without-outcome is killed by the rewrite test. hook-outcome-empty is killed by 5 tests. no-upper-in-status and no-upper-in-hook are each killed by 1 test.
- Route differential: specs/goal-met/differential.py on archive copies of main dc39cae and the head. 257 routes each, 0 moved. routes.json sha256 is 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0 at both. The builder's figure of 251 predates the merge, which added routes. goal: probe: main gave 20736 generated, 0 recorded, 810 holes; the head gave 20736 generated, 810 recorded, 0 holes.
- Fitness: runtime lines (cat cli/wuwei/*.py | wc -l) are 3011 at dc39cae and 3024 at the head, +13: within the item budget of 13 and the 3400 limit. `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows no difference.
- Layering: hook now imports view, and view imports only plan and ws, neither of which imports hook, so there is no cycle. The hook reads goals.md only inside the goal: branch, so the extra read stays off the hot path.
- Contract: goal.met rows and their `outcome` field are new in this unreleased item. Their consumers are view.goal_status, through report.py:29 and __main__.py:58. evidence.py's ruling readers filter by kind or pr and skip these rows. No existing client changes, hence Breaking: no.
- Confidence high: the blocking scenario was re-run and is now closed, the delta and the merge diff were read in full, and the suite, the mutants and the differential were re-run here.

## Residual risk
Outcome-text identity means any rewording asks the owner one more question. That is the recorded trade, and it fails toward asking. Free-text answers still record as a no, and a no given near midnight UTC can be off by one day against a naive goal date.
