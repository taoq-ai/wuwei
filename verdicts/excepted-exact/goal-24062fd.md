Verdict: PASS
Gate: goal
Item: excepted-exact
PR: taoq-ai/wuwei#1150
Head: 24062fd084105a6ecae29badfb55bd636540fe55
Confidence: medium
Breaking: no

## Findings
- [low] blblocks: no. The promise says "a waived gap is listed in the report as waived by the ruling". The report line (cli/wuwei/report.py:127) still reads `- exception: <pr> at <head>: <gap>` for every approved exception, and does not say "waived". The PR body records this as an assumption ("The report line keeps its wording") and a test reads the line after a waiver. Note for the PR's review notes; the owner can ask for "waived" wording later.
- [low] blocks: no. A ruling recorded before this change with a loose gap stops waiving at an open PR. This is recorded as an assumption in the PR body. It is the intended fail-closed direction of G-2, not drift.

## Probes
- Trace: goal G-2 (bugs found running WUWEI on itself are fixed before features) -> plan item excepted-exact (security gate on #1136 at 353b6f7: substring match in both directions, so gap 'e' waives all gaps) -> promise (waive only on accepted text equal to the gap text after whitespace normalisation, or naming its gate exactly) -> `evidence.excepted` in cli/wuwei/evidence.py. Read with `git diff origin/main...HEAD` at 24062fd.
- Promise vs diff: `excepted` now builds a set of normalised accepted gaps (string, kind exception, approved, same PR, head prefix) and waives a gap only when the normalised gap text, or the normalised gate list captured by `GATES`, is in that set. Substring matching is gone, and an empty accepted text is removed from the set. The normalisation is casefold, whitespace collapse, trailing end marks and a printed `[waiting]`. The PR body, design.md and the two site docs state the same normalisation.
- Acceptance 1 (accepted gap 'e', security gap and owner review gap both still show): `test_a_short_or_partial_exception_waives_nothing` asserts both gaps remain with 'e' and about 20 partial or non-string texts.
- Acceptance 2 (accepted text equal to the printed gap waives that gap alone): `test_an_exception_naming_the_printed_gap_waives_that_gap_alone` waives the security gap only, and another head, another PR and an unapproved ruling waive nothing.
- Gate-name form: `test_an_exception_naming_its_gate_list_exactly_waives_that_gate_gap` and `test_a_delta_review_exception_names_its_gate`.
- Drift, missing outcome: none found. All promise files are touched (evidence.py, tests/test_evidence.py, the vendored copy, docs). Drift, unrequested claim: the non-string ruling skip and the `[waiting]` / end-mark normalisation are small additions. They are stated in the PR body and fit "the printed gap text".
- Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` at the head shows no difference.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` gives 2988, matching the PR body's 2,988. The promise budget was an estimate of +1 and a budget of 3; the PR reports 2,986 to 2,988 (+2), within budget.
- `pytest -q tests/test_evidence.py` at the head gives 182 passed. I did not re-run the full suite (1779 passed per the PR body) or the probe and mutants; their counts are the builder's, unmeasured by me.
- PR body: names `WUWEI-Item: excepted-exact` on the first line. It states the promise (the What section), Assumptions (five, each with what would overturn it), the residual (newline-tail questions now fail closed: 68 of 568 built questions stay standing, all with the `\nAccept?` tail; the exception-parser follow-up owns the hook's cut), Rollback, a Size line, and a main-versus-head table. The probe is as AGENTS.md asks for guard-adjacent code, with the route corpus unchanged (251 passed at both).
- Counts in the PR body read against the head: the runtime line count was re-derived (2988). The probe table figures (26,826 changed pairs, 9,183 accepted gaps, 71 printed gaps) were not re-derived; unmeasured by me.
- Not escalated: no goal change, no one-way choice (Rollback: revert the commit), no trust-boundary question. The change tightens the owner-exception trust boundary.

## Residual risk
Newline-tail exception questions no longer waive their gap until the exception-parser follow-up lands. The owner must restate such a gap exactly. The follow-up item exists per the PR body. The report wording does not yet say "waived".
