Verdict: FIX
Gate: security
Item: ascii-digits
PR: taoq-ai/wuwei#1107
Head: cda89f41f7dae59165e7dddac94ba50e2a6a6be9
Confidence: high

## Findings
- [medium] cli/wuwei/hook.py:246 blocks: yes. Failure: the merged reader takes the first REF anywhere in an owner review question, where main read only the REF right after "owner review: ". The guard admits any classed question that carries a REF somewhere (guards.py:345). So the owner answering "yes" to "owner review: with acme/lib#3 at 1234567 merged, acme/app#9 at abcdef0 is ready. Approve?" records an approved ruling for acme/lib#3 at 1234567. evidence.owner_approved then returns True for acme/lib#3 and clears its "owner review needed (owner_paths)" merge gap, but the owner approved app#9. On main the same answer records nothing (fails closed). Real hook.handle plus owner_approved runs: main lib#3 False, app#9 False; head lib#3 True, app#9 False. Fix: anchor the REF right after the class prefix (for example re.match(r'\s*(owner review|breaking):\s*' + REF.pattern, question, re.I)), or have the guard refuse owner review and breaking questions that carry more than one REF. Add the two-REF case to test_a_ruling_names_a_pr_in_ascii_digits_only.
- [low] cli/wuwei/hook.py:246 blocks: no. The breaking reader on main already took the first REF ("breaking: see x/y#2 at def5678, o/r#7 at abc1234" records x/y#2 on both trees). The anchored fix above closes it too.
- [low] cli/wuwei/evidence.py:437 blocks: no. This predates the change: owner_approved accepts any approved ruling for the PR at its head, whatever its kind, so breaking and exception rulings also count as owner approval. This makes the finding above, and any breaking answer, count as owner approval.
- [low] blocks: no. This change closes a hole on main: main recorded an owner review ruling from any question that held "owner review: REF", including exception:, plan:, one-way: and scope: questions (e.g. "scope: see owner review: o/r#7 at abc1234" answered yes became an owner approval). Head records nothing for those.
- [low] blocks: no. Rulings head no longer records, all fail closed: text before the class (the guard already refuses these as unclassed), a sha followed by a word character ("abc1234zz", "abc1234" followed by a non-ASCII letter) or with 41+ hex characters, a fullwidth or Arabic-Indic PR number. For a 41-hex sha main recorded a truncated 40-character head. Rulings head newly records: case variants and leading whitespace of the class, "owner review:" with no space after the colon, a REF later in the question, and a REF inside a longer path ("foo/o/r#7" records o/r#7). Each names the PR and sha to the owner.
- [low] cli/wuwei/guards.py:341 blocks: no. "exception: o/r#7 at abc1234: open ３ days. Accept?" now gets past the process-gap refusal (main refused it). The resulting exception gap "open ３ days" never matches the ASCII evidence gap in excepted(), so it bypasses nothing: the owner just gets an extra question.
- [low] blocks: no. Two mutants survive the behavior tests and are caught only by the scan or mirror tests: dropping "and found[1]" (it records pr "None#7", which no reader matches, so the mutant is equivalent) and "\d" in the guard's unparsed pattern (the hook still records nothing for a non-ASCII number, so there is no bad input). The missing tests are notes only.

## Probes
- Suite: head 964 passed 2 skipped; main 952 passed 2 skipped (pytest -q in git archive copies).
- tests/fixtures/routes.json sha256 93d26ddc4551ca97183df579631b05392c0af8edc7cd59d776163e8d16ffa20f, the same on both trees. Route and merge-route tests give 141 passed on main and on head.
- Ruling battery: 33 questions through real hook.handle PostToolUse on both trees, with the rows diffed. The cases cover class case and whitespace, text before the class, two REFs, a sha suffix, non-ASCII sha and PR digits, and exception:, plan:, one-way:, scope: and trust: questions. The differences are as listed above. The answer text is never parsed for a REF.
- The two-REF owner review was run end to end with evidence.owner_approved (gh.login stubbed): the head grants lib#3.
- guards.pre_tool AskUserQuestion: head refuses fullwidth and Arabic-Indic PR numbers in owner review:, breaking: and exception: questions as unparsed; main let them through.
- CLI _ref: head refuses fullwidth, Arabic-Indic and superscript digits with the shape message. Main read o/r#７ and o/r#٧ as PR 7, and o/r#² crashed with a ValueError. evidence.refs and verdict.parse ignore non-ASCII numbers on head.
- Mutants, each in a fresh git archive copy: removing isascii in _ref, \d in hook REF, kind gate removed or narrowed, kind key on owner review, and \d in evidence REF are each killed by a behavior test. The verdict PR \d mutant is killed by test_lint_names_what_is_wrong. found[1] and the guard unparsed \d survive and are caught only by the scan or mirror test (see the notes).
- The .claude/wuwei mirror is identical to cli/wuwei (diff -r).
- Confidence is high because the blocking case reproduces on real code on both trees, and the other differences were run case by case.

## Residual risk
Unicode \w in repository names stays outside, by design. owner_approved accepting rulings of any kind predates this change and widens the impact of any ruling recorded by mistake.
