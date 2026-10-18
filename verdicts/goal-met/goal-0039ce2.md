Verdict: PASS
Gate: goal
Item: goal-met
PR: taoq-ai/wuwei#1145
Head: 0039ce218d7c4fccf73850e5602eec6eda001012
Confidence: medium

## Findings
- [low] blocks: no. cli/wuwei/view.py:42-46. The ISO-date check is only partly pinned. In a fresh `git archive` copy, replacing `re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', date)` with `re.match(r'[0-9]{4}-[0-9]{2}', date)` leaves tests/test_plan.py, tests/test_hook.py and tests/test_report.py green (170 passed). The reversed guard would offer a month-only date such as `Date: 2026-10` from 2026-10-18. The head stays silent for it. Reported as untested; the missing test is a goals.md block with `Date: 2026-10` that is not offered. The PR body's "20 of 20 killed" came from the builder's own mutant set, which I could not read; my 16 mutants killed 15 of 16 (this is the one that lived).
- [low] blocks: no. Issue #975 says the pass offers a goal when "the date has passed, or the measure is met". The head offers only date-passed goals. The promise's Outside clause excludes reading a measure automatically, and the hook records a `goal: G-n met?` ruling at any date. The run skill tells the planner to ask only for goals the pass names, so a measure-met goal before its date is not offered. This is a scoped-out half of the issue, not drift against the item's promise. A follow-up item or an issue comment should say so.
- [low] blocks: no. "A met goal gets no new items" rests on one sentence in charters/lead.md, which the lead is told to read from the report's `Met goals:` line. `plan add` does not refuse an item for a met goal. The promise (3) asks for exactly the charter sentence, so this matches the item. It is an instruction, not a guard.
- [low] blocks: no. "Offered once" means one line per plan pass. A goal that is not answered is listed again at the next pass. This fits acceptance 1 (one line per pass) and is the sensible reading.

## Traceability (promise, acceptance and issue #975 against running code at the head)
- Promise (1) and acceptance 1: `cli/wuwei/__main__.py` prints `goal G-n dated <d>: ask the owner 'goal: G-n met? <evidence>'` for each goal from `view.goal_status`. `test_a_plan_pass_offers_each_goal_whose_date_passed_once` passes. It covers yesterday offered; today, tomorrow, empty and non-ISO dates, non-`G-n` headings and goals ruled met not offered.
- Promise (2) and acceptance 2 and 3: `hook._answers` records `ruling {kind: goal.met, goal, approved, question, answer}`. `test_a_yes_to_a_goal_met_question_records_the_goal_as_met`, the Codex test and `test_a_no_keeps_the_goal_quiet_until_its_date_moves` pass. The no holds until the date moves past the day of the no, as the promise says.
- Promise (3): `report.day` prints `Met goals: <ids>|none`. The lead charter, the skill and docs/design.md carry the sentences. `bin/wuwei agents check` prints "agents match the charters". The `.claude/wuwei` copies of view.py, hook.py, report.py and __main__.py are byte-identical to the tree.
- "goals.md changes only by the owner": `grep -n goals.md cli/wuwei/*.py` shows the pre-existing writers only (setup.py:96-98 creates the file when absent, upgrade.py:52 is the migration). The diff adds no write.
- Issue #975 acceptance "a goal dated yesterday is offered once; No keeps it open; a met goal gets no new items and shows as met in the report": met, as above, except for the two notes.
- The builder's explain-back in specs/goal-met/spec.md matches the item, and the complement cases (early yes, early no, a no on the goal's own date, the latest ruling counts) are stated and tested.
- Other ruling consumers (evidence.py:345, 435 and 447; report.py:128) filter on `kind` or `pr`, and a goal.met row matches none of them.

## Probes
- Suite at the head: `pytest -q` gave 1780 passed, 2 skipped (PR body: same).
- Red run: head tests onto main code, `pytest -q tests/test_hook.py tests/test_plan.py tests/test_report.py tests/test_codex.py -k goal` gave 6 failed, 1 passed. This is the body's 5 failed 1 passed plus the later Codex test.
- Generated probe `goal_met_probe`: head 20,736 generated, 810 recorded, 0 holes. Main code with head tests: 20,736 generated, 0 recorded, 810 holes. The PR body's counts match.
- Route corpus: sha256 `12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1` at main and at the head. I ran `specs/goal-met/differential.py` against each of the two `git archive` trees (main 3d2eb29, head 0039ce2): 251 routes through `guards.bash` and the PreToolUse hook, 0 routes moved, 0 differ from their recorded verdict. The route table is empty.
- Runtime: `wc -l cli/wuwei/*.py` gave 2986 at 3d2eb29 and 2999 at the head, so +13 within the budget of 13 (the promise's "+9" estimate was exceeded but the budget holds). Diff stat 475 insertions and 12 deletions matches the body, and so do 130 test lines and 296 spec-artifact lines.
- Mutants, 16 run (view.py thresholds `<`, `<=` and `<`/`<=` on today, the not-met check, the kind filter, the G-n check, the met list, hook regex flags and `and answer`, `approved`, `.upper()`, `re.search`, the digit quantifier, the report line, and the pass printing the met list): 15 killed, 1 survived (see the first finding). The survivor was re-run in a fresh copy and lived again.
- Not run: an end-to-end `bin/wuwei plan pass` in a scratch workspace was refused by the Bash door because the command named `.wuwei`. The tests drive the same path through `cli.main` and `hook.handle`.

## Residual risk
Free-text answers such as "Met" are recorded as open, which the PR states as an assumption; the skill asks for Yes and No. Two answers to the same goal in the same second order by file. The "measure met before the date" half of #975 is not surfaced by the pass.
