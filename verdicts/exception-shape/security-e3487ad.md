Verdict: PASS
Gate: security
Item: exception-shape
PR: taoq-ai/wuwei#1136
Head: e3487adc9efb2678f8283bf174ede67df2b42179
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:374 blocks: no. Left from the previous note on invisible gaps (CWE-176). U+200B and `_x` are now refused, but the Hangul fillers U+115F, U+1160, U+3164 and U+FFA0 are Unicode letters (Lo), so they match `[^\W_]`. `exception: o/r#1 at abc1234: ㅤ. Accept?` passes and records the gap "ㅤ", which the owner sees as blank. This fails closed in evidence.excepted, because no gap text contains those code points; it also files a follow-up plan item with a blank title. A check that the gap holds a visible character, or a deny list of the four fillers, would close it.
- [low] blocks: no. Disclosed by the builder: a gap ended by a line break (`exception: o/r#1 at abc1234: CI failing\nAccept?`) records the gap "CI failing\nAccept", because exception_refs splits only on ". " and "?". It waives nothing beyond what the owner read: under near() only gaps that are substrings of that text match. It fails closed under excepted-exact. The exception-parser follow-up owns it.
- [low] blocks: no. Existing gap outside the item: evidence.excepted's two-way substring match lets an accepted short gap (`exception: o/r#1 at abc1234: e. Accept?`, which passes) waive every gap at that head. The planner says follow-up excepted-exact now owns this.

## Probes
- Delta 353b6f7..e3487ad: guards.py (plus its vendored copy, diff -r identical), tests, specs. hook.py is unchanged. The second alternative (owner review:, breaking:) has the same text.
- Previous findings, rule 6:
  - H1 (refs in the prose recorded as rulings, the blocking one): closed by `[^#]*?`. The refusal cases are in test_guards.py. Mutant N1 (prefix back to `[\s\S]*?`) is killed by 3 tests.
  - Regex cost: closed. The word-start lookbehind and the possessive ` *+` make every shape linear.
  - M5 optional colon: closed, mutant N6 killed.
  - Whitespace before the colon: closed (spaces only, mutant N4 killed).
  - Invisible gap: U+200B closed, the Hangul fillers are left (note above).
- Suite at the new head in a git archive copy: `pytest -q` gave 1710 passed, 2 skipped. CI at the head, read once from REST check-runs: tests 3.11/3.12/3.13, ziran-audit, Analyze (python, actions) success; CodeQL and ZIRAN "No new alerts in code changed by this pull request".
- probe2 (round 1 classes): 53,900 generated. Head: 900 passed, H0 0, H1 0, H2 0, H3 0. (Its blank-gap oracle counts Lo letters as visible, so it misses the fillers; probe3 fixes that.)
- probe3 (round 2 classes: fullwidth U+FF03 and a non-ref '#' in the prose, x.o/r, a/b/c, _o/r and ZWSP repo starts, NBSP, U+3000 and ZWSP around the colon, Hangul fillers, a Roman numeral, combining and bidi code points in the gap, newline tails, a later ref after a newline). 31,360 generated:
  - new head: 8,400 passed, H0 0, H1 0, H2 1,680 (all are newline tails), H3 2,688 (all Hangul-filler gaps);
  - old head 353b6f7: 19,600 passed, H1 2,450, H2 6,160, H3 5,376.
- Builder probe (probe.py) at the new head: 462,000 generated, 900 passed and recorded, 0 holes.
- Spot checks at the new head: the superseded-PR and other-sha questions from the previous verdict are refused. A U+FF03 ref in the prose passes and is not recorded (under-recording, fails closed). Hotfix prose and two-ref chains pass and record as written.
- Other classes (owner review:, breaking:, one-way:, scope:, plan:, unclassed): 462,000 questions, byte-identical at main and the new head (cmp).
- Route corpus: tests/fixtures/routes.json sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1. 251 routes, dump sha256 fe1e7d58b4973f3857f4d8dbcefd8df410c9fe08eb77b0673c2eb2c4bb7236da at main and at the new head, 0 moved.
- Checks that use no door words: infra ask and the canary leak on curl, wget and ssh, under cd, env -C, sudo -D, bash -c and an assignment prefix. 48 commands, identical at main and the new head.
- Mutants at the new head, each in a fresh copy, tested with test_guards.py and test_hook.py. 7 of 7 killed:
  - N1 prefix `[\s\S]*?`;
  - N2 no lookbehind (timing test);
  - N3 old gap-start class;
  - N4 `\s` around the colon;
  - N5 non-possessive spaces (timing test);
  - N6 optional colon;
  - N7 `\w` gap start.
- Cost (cost.py and cost2.py): all 23 shapes take at most 0.004 s at 36,000 characters and at most 0.043 s at 360,000. The old word run went from 6.7 s to 0.002 s.
- Gap texts evidence prints (grep of gap( calls in cli/wuwei): every one starts with a letter, a digit or an owner/repo name, so `[^\W_]` refuses none of them.
- Confidence high: every previous finding was re-probed at the new head with generated and spot inputs and the mutants are all killed. What is left fails closed.

## Residual risk
Blank-letter gaps and newline-ended gaps record text the owner does not see as written. Both fail closed. The breadth of excepted's substring match stays until excepted-exact lands.
