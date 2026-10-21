Verdict: FIX
Gate: quality
Item: 1213
PR: taoq-ai/wuwei#1218
Head: f329be5ee1cab09c9cc1b1ba9959ec6550d130ad
Confidence: medium

## Findings
- [medium] charters/_gate.md:29 blocks: yes. Failure: rule 5 no longer says a trust-boundary security finding about shell or gh parsing still blocks without a run; "Without one it is a note." now reads as the specific rule over the earlier general "always blocks", so a gate that finds a real trust-boundary hole in how a wrapper parses a command but has no stub run may file it as `blocks: no` and the hole merges (requirement: rule 5 "a trust-boundary defect blocks", dropped by a824b82 exception clause).
- [low] charters/_gate.md:16 blocks: no. "Call code equivalent or deletable" drops "a mutant or other"; "mutant" is still covered by the later "a surviving mutant alone is reported as untested", so no gate loses a decision, but the equivalent-mutant case is now implicit.
- [low] tests/test_setup.py:78 blocks: no. The new test asserts the added sentence only; no test pins the trust-boundary exception in rule 5, which is why the trim passed 224 tests. A string assertion on 'trust-boundary security finding' with 'still blocks' (or the replacement wording) would have failed before the trim.

## Probes
- Copy: `git archive f329be5` in the scratch folder; `pytest -q tests/test_setup.py tests/test_charters.py`: 224 passed; `bin/wuwei agents build`: "agents match the charters".
- Word counts (wc -w agents/sentinel-*.md): arch 2248 (ceiling 2250), goal 1979, quality 2068, security 2105. Arch has 2 words of headroom, so the exception cannot be restored verbatim (8 words) without another cut; the trim was made for that reason.
- Rule 5 diff: the removed clause ", except a trust-boundary security finding, which still blocks" is not a repeat of "A trust-boundary security finding always blocks." two lines earlier. It is the tie-break for the one case where the note rule and the blocking rule meet (a security finding about shell, wrapper or gh parsing with no run). Before: blocks. After: ambiguous, and by specific-over-general it is a note. That is a behaviour change in a charter whose purpose (#1213) is to stop gates splitting on exactly such conflicts.
- Cheap fix inside the budget: replace the final sentence with "Without one it is a note unless it is a trust-boundary security finding." and drop "A trust-boundary security finding always blocks." (net about 0 words), or cut the 12-word new sentence in rule 1 to "Standards lines add checks; rules 3 and 5 decide what blocks." and restore the clause.
- Mutant: removing the new rule 1 sentence from charters/_gate.md and agents/*.md fails test_a_standards_line_adds_checks_and_the_gate_rules_alone_decide_what_blocks (4 parametrized cases); removing "Call code" wording is not pinned beyond the existing test_equivalence_needs_a_differential_probe_with_0_differences, which still passes (the phrase it asserts is intact). Mutants not run beyond this; the diff is prose, and the one test is a prose assertion, which is this repository's convention for charters.
- Rule 3 trim judged: no meaning lost for a gate (code in the copy includes a mutant; the sentence after it names mutants explicitly).
- Steward addition: consistent with the gate rules and does not contradict rules 3 and 5.

Simplicity: none to delete; the generated .claude/ and agents/ copies are required by the drift test. The rule 1 sentence could be 2 words shorter ("rules 3 and 5 decide what blocks") to free budget.

## Residual risk
Only the rule 5 exception matters; once restored in some form, the rest holds. Charter prose is not exercised by a running consumer, so how gates read the wording is unmeasured.
