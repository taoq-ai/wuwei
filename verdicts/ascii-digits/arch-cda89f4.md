Verdict: PASS
Gate: arch
Item: ascii-digits
PR: taoq-ai/wuwei#1107
Head: cda89f41f7dae59165e7dddac94ba50e2a6a6be9
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/hook.py:245 blocks: no. Reading the class with strip().lower() is untested: mutant `kind = question.partition(':')[0]` passes the whole suite (only the vendored-drift test fails). A regression would stop recording a ruling for `Breaking: o/r#7 at abc1234: ...`, which main records (main read breaking: through lower()). Nothing unsafe gets through, the gap just stays open, but the spec's Assumption (any case, after strip) has no test. Add one capitalised or leading-space case to test_a_ruling_names_a_pr_in_ascii_digits_only.
- [low] cli/wuwei/hook.py:246 blocks: no. Contract change, recorded in the spec's Assumptions: owner review now reads the class prefix (any case, after strip) and the first REF match anywhere in the question, where main needed `owner review: ` followed directly by the ref, anywhere in the question, case-sensitive. guards.pre_tool:353 already refuses any question that does not start with a class, so the only questions that stop recording are ones with `owner review: o/r#n at sha` buried after another class (for example `scope: ... owner review: o/r#7 at abc1234`). That is a stray approval main used to record, not a documented form. Every documented shape (docs/design.md:62, skills/wuwei-rules/SKILL.md:55, docs/site/concepts/decisions.md:37, guards.py:351) still records the same row.
- [low] tests/test_setup.py:72 blocks: no. The scan is the right place: it sits next to the size-budget test, checks every runtime module, and names file:line. Its limits: the lookbehind does not check that the isascii() and isdigit() calls are on the same variable (`x.isascii() and y.isdigit()` passes), and it does not see int()/float() on unchecked strings, or isdecimal()/isnumeric(). None of the remaining int() calls reads a PR number from text that was not checked (verified by grep: __main__.py:31 converts plan scores, plan.py:140 converts the `within` duration), so this is a limit to note, not a hole.

## Probes
- git diff origin/main...cda89f4: 6 runtime modules plus their vendored copies (identical, checked with diff -r), 4 test files, specs/ascii-digits.
- Line count (cat cli/wuwei/*.py | wc -l): main 23625f3 has 2992, head has 2988, under the 3,000 budget. FR-005 holds.
- Full suite in a git archive copy: 964 passed, 2 skipped.
- Mutant REF back to \d: the ascii-digits ruling cases fail, and so does the scan test. Killed.
- Mutant _ref with a bare isdigit(): the two non-ASCII CLI cases fail, and so does the scan test. Killed.
- Mutant dropping strip().lower() from kind: survives (first finding).
- Ruling consumers (evidence.py:341 breaking needs kind==breaking; evidence.py:430 exception; evidence.py:438 owner_approved takes any approved ruling at pr+head; report.py:131): the row shapes are unchanged, the owner review row still has no kind key, and the breaking row keeps kind: breaking.
- Fit with the constitution: stdlib only, test first (the spec says the cases ran red at 0104d00), no config key, and the runtime shrinks. Design: the documented question shapes are unchanged.
- Consistency with guards.pre_tool: the hook now reads the class the way the guard does (strip, lower, startswith), and the guard's shape check (an ASCII ref anywhere) matches REF.search anywhere.

## Residual risk
owner_approved accepts any approved ruling (breaking included) as owner approval. That predates this change and is not changed by it. The class-casing behavior rests on code that no test pins.
