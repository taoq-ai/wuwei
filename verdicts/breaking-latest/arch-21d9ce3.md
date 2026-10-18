Verdict: PASS
Gate: arch
Item: breaking-latest
PR: taoq-ai/wuwei#1135
Head: 21d9ce378a078a0364ba418fb17d039904ea5dee
Confidence: medium
Breaking: no

## Findings
- [medium] cli/wuwei/evidence.py:333 blocks: no. Ordering limit the plan recorded (Assumptions: ledger order is the order the gates ran). If an arch verdict at the PR head says Breaking: yes and a stale arch seat at an older ancestor head is attested after it with Breaking: no, breaking_gaps clears, and nothing else holds the merge: with quality and security passed at the head, gate_gaps returns [] (evidence.py:296). Main held this case (probe rows 1 and 2 below). This follows the approved promise word for word ("the last attested arch verdict in ledger order"), and gate_gaps already uses the same ledger-order rule, where an older-head PASS attested later also clears a FIX at the head (pre-existing, main too). So it is a gap shared with an existing design choice, not a new contract violation. Recommend a follow-up plan item that fixes both readers together: a verdict at the PR head outranks one attested later at an older head (for breaking: `at = [v for v in arch if head.startswith(v['head'])]; (at or arch)[-1]`). That still meets all three acceptance scenarios. Note: `ref` in verdicts() is the PR ref (owner/repo#n), not a git ref, so "latest at the current head" needs a head filter in breaking_gaps, not a verdicts() argument.
- [low] specs/breaking-latest/spec.md:54 blocks: no. The bound in "How this fails 1" says "the arch gate still owes a pass at the head". It does not when another gate passed at the head (gate_gaps returns [] at evidence.py:296); probe row 1 shows no gap at all. Correct the claim, so the full-tier safety case does not overstate the bound.
- [low] docs/design.md:108 blocks: no. The design still says "found by the arch gate's required Breaking: line" and does not name the latest-verdict rule. Not a contradiction, but the refinement now lives only in the code docstring and the spec.

## Probes
- Conformance: design.md:108-110 (breaking needs Announcement, then a breaking: ruling at the head); the change only narrows which arch verdict counts as "found by the arch gate". The declared path (! / BREAKING CHANGE:) is untouched. No ADR applies (docs/adr has 0001 only, about a release cut).
- Dependencies: no new import; breaking_gaps has one caller (evidence.gaps, evidence.py:393); it reads verdicts() and ws.rows('ruling') as before. Vendored .claude/wuwei/cli/wuwei/evidence.py is byte-identical to cli/wuwei/evidence.py at the head (git diff --no-index on git show of both: no output).
- Contract: gap texts, kinds and owner flag unchanged; only fewer false breaking gaps. Breaking: no.
- Fitness: runtime lines `cat cli/wuwei/*.py | wc -l` main 2976, head 2977 (+1, promise budget 2, constitution cap 3000); stdlib only.
- Suite at the head in a git archive copy: `pytest -q` 1693 passed, 2 skipped.
- Mutants (each in a fresh git archive copy, tests/test_evidence.py): arch[-1] -> arch[0] killed (latest[said0]); drop gate == 'arch' filter killed (latest[said1]); drop 'breaking' in v filter killed (edited-verdict test); any-ever over arch killed (latest[said0]); drop declared killed (declared[fix(x)!]). 5 of 5 killed.
- Ordering probe (pytest fixture, arch rows attested in order, quality and security PASS at HEAD, OLD ancestor of HEAD): [HEAD yes PASS, OLD no PASS] head: no gap, main: announcement gap; [HEAD yes FIX, OLD no PASS] head: no gap, main: announcement gap; [OLD yes FIX, HEAD no PASS] head and main as acceptance expects (head clears, main held).
- Ledger scan for real out-of-order arch attests: not run, the hook refused a read of .wuwei/ledger by script; the assumption's frequency is unmeasured.
- Route corpus differential (tests/fixtures/routes.json): N.A., the diff does not touch guards.py or hook.py.
- Confidence medium: the code is correct against the promise and well tested; the open part is how often the stale-seat order happens, which I could not measure.

## Residual risk
A stale arch seat at an older head that hands back after a re-read at the PR head can clear a Breaking: yes found at the head; the same ledger-order rule already lets an older PASS clear a FIX in gate_gaps. Both want one follow-up that ranks a verdict at the PR head first.
