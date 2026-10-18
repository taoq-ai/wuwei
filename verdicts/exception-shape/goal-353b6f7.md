Verdict: PASS
Gate: goal
Item: exception-shape
PR: taoq-ai/wuwei#1136
Head: 353b6f7be63f519df6adcaeedf49d80de0627748
Confidence: high

## Findings
- [low] blocks: no. The promise lists routes.json among the files and acceptance 4 says "except the new rows", but the diff adds no row. The builder recorded why (the corpus is read through guards.bash, shell commands only; an AskUserQuestion never reaches it), named it an assumption in spec.md, analysis A1 and the PR body. Acceptance 4 itself (no route moves) holds: 0 of 251. Question-shape cases live in tests/test_guards.py and tests/test_hook.py.
- [low] blocks: no. The guard is stricter than the promise's literal text: it also refuses a gap whose first character is ".", "?" or ":" and a gap that itself names "#n at <sha>", because the hook would record an empty gap there. The PR body and spec "How this fails" disclose both. Not a drift from the goal (the owner's answer is never recorded as nothing).
- [low] blocks: no. "breaking: o/r#1 at abc1234. Proceed?" (no colon, no gap) still passes at head, as at main. The promise says breaking: keeps its shape, so it is out of scope. A candidate follow-up of the same silent-failure class if the hook reads breaking: from a gap.
- [low] blocks: no. specs/ lists routes.json in the promise but analysis A1 is the only trace; no other claim without a requirement found.

## Probes
- Trace: issue #1130 test -> promise -> acceptance 1-4 -> guards.py diff (one regex, 5 lines) plus tests. Run with my own probe against git archive copies of main efcd9e7 and head 353b6f7: `exception: o/r#1 at abc1234. Some prose. Accept?` DENY at head (PASS at main); `exception: o/r#1 at abc1234: <gap>. Accept?` PASS and hook.exception_refs gives gap "<gap>"; the issue's own example `taoq-ai/taoqi#124 at 4bc9c28. WUWEI is holding ...` DENY at head, PASS at main with empty gap.
- Acceptance 1: reason contains the shape text (asserted by test_an_exception_whose_refs_are_not_followed_by_a_gap_is_refused_with_the_shape). Acceptance 2: test_an_exception_answer_records_the_gap_after_the_refs runs hook.handle PostToolUse and reads the ruling row (kind, pr, head, gap). Acceptance 3: probe PASS with refs [(o/r,1,abc1234),(o/r,2,def5678)] and gap "no test in the diff".
- Suite at head (pytest -q in the git archive copy): 1695 passed, 2 skipped. Body says 1695 passed, 2 skipped: matches. `-k exception` on tests/test_guards.py and tests/test_hook.py: 17 passed (body: 17 passed).
- Runtime lines (wc -l cli/wuwei/*.py): main 2976, head 2977 (+1, budget 2): matches body. diff -r cli/wuwei vs .claude/wuwei/cli/wuwei: identical except __pycache__.
- Corpus: routes.json sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at main and at head (unchanged, matches body). 251 routes; test_every_route_reads_as_recorded: 251 passed at head and 251 passed at main; the diff touches only the AskUserQuestion branch. Moved routes: 0 (matches body).
- Generated probe, builder's own probe.py and others.py run read-only against my copies: main generated 462,000, passed and recorded 88,375, holes 184,625; head generated 462,000, passed and recorded 18,090, holes 0. Refused at head though the hook could read (refs and gap): 70,285. All match the body. Other classes (owner review:, breaking:, one-way:, scope:, plan:, unclassed word), 462,000 questions: decisions and reasons identical main vs head (cmp). 462,000 = 8 x 10 x 75 x 11 x 7, as the body says.
- My own independent probe (6 prefixes x 6 refs x 14 separators x 9 gaps x 5 tails): generated 22,680; main passed 17,640 with 11,226 holes; head passed 1,941 with 0 holes.
- CI at head via check-runs: tests 3.11, 3.12, 3.13, ZIRAN, ziran-audit, CodeQL, Analyze (python), Analyze (actions) all completed success.
- Count claims not re-run: the 6-of-6 mutant kills and the 0.36 s timing (quality gate territory).
- Explain-back (spec.md "The promise in my words") matches the item promise and the four acceptance scenarios.

## Residual risk
A legitimate gap that quotes a "#n at <sha>" ref is now refused and must be reworded; a lead resends in one turn and nothing is recorded wrong. Not run here: mutants, timing of the quadratic match.
