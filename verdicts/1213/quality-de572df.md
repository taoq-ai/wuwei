Verdict: PASS
Gate: quality
Item: 1213
PR: taoq-ai/wuwei#1218
Head: de572df78ae4a1ff43dcf28f8425a17bc481a394
Confidence: medium

## Findings
none

## Probes
- closed: rule 5 trust-boundary exception dropped (medium) at de572df. Rule 5 now ends "Without one it is a note; a trust-boundary security finding still blocks." (charters/_gate.md:29-30), the tie-break is restored and the duplicate "always blocks" sentence is gone.
- closed: no test pinned the trust-boundary exception (low) at de572df. tests/test_setup.py now asserts the new sentence in all four sentinel agents.
- Copy: `git archive de572df` in scratch; `pytest -q tests/test_setup.py tests/test_charters.py`: 224 passed; `bin/wuwei agents build`: "agents match the charters".
- Word counts (wc -w agents/sentinel-*.md): arch 2248 (ceiling 2250), goal 1979, quality 2068, security 2105.
- Mutant: removing "; a trust-boundary security finding still blocks" from charters/_gate.md and agents/sentinel-*.md in a copy fails test_a_standards_line_adds_checks_and_the_gate_rules_alone_decide_what_blocks (4 parametrized cases killed, the sentence assertion).
- Delta f329be5..de572df is charters, rebuilt agents, vendored .claude copies and one test line; no code changed. The earlier [low] on "Call code equivalent or deletable" (dropped "a mutant or other") was a note and stays one, unchanged.

Simplicity: none to delete; the generated agents/ and .claude/ copies are required by the drift test.

## Residual risk
Charter prose is not exercised by a running consumer, so how gates read the wording is unmeasured; arch has 2 words of headroom.
