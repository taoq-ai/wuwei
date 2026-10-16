Verdict: FIX
Gate: security
Item: ascii-digits
PR: taoq-ai/wuwei#1107
Head: e82601e2cf58e439b468eb495e584efc0f285926
Confidence: high

## Findings
- [medium] cli/wuwei/hook.py:245 blocks: yes. Failure: a surviving mutant reopens the owner authority hole main had, and no test catches it. Reversing the anchor (re.match to re.search on the class-prefix pattern) passes the whole suite (970 passed; test_hook and test_guards 712 passed, re-run in a fresh git archive copy). With that mutant, "exception: o/r#7 at abc1234: CI failing. owner review: x/y#2 at def5678. Accept?" gets past the guard (exception keeps REF-anywhere). Answered yes, it records an owner review ruling for x/y#2, and evidence.owner_approved returns True for x/y#2 at def5678, though the owner answered an exception question. Main does exactly this today (probe: main True, this head False, mutant True). The code at this head is correct. The fix is test-only: add that question, and "scope: see owner review: o/r#7 at abc1234", to test_a_ruling_names_a_pr_in_ascii_digits_only, expecting no owner review row.
- [low] cli/wuwei/hook.py:246 blocks: no. Dropping "and found[2]" survives. It records pr "None#7" for "owner review: #7 at abc1234", which the guard already refuses and no reader matches, so the mutant is equivalent.
- [low] cli/wuwei/guards.py:346 blocks: no. Two guard mutants survive, re.match to re.search and dropping the trailing \b. Each only admits questions the recorder then does not record ("owner review: o/r#7 at abc1234zz", or a second "owner review:" later in the text). That fails closed: an owner question gets asked and nothing is recorded. The missing test is a note.
- [low] cli/wuwei/evidence.py:437 blocks: no. This predates the change: owner_approved counts an approved ruling of any kind (breaking, exception) as owner approval.
- [low] blocks: no. Closed from the previous verdict (security-cda89f4): the two-REF owner review now records nothing. Real hook.handle plus owner_approved: lib#3 False, app#9 False on main and on this head.

## Probes
- Delta cda89f4..e82601e read: hook._answers uses one anchored re.match, guards.pre_tool anchors owner review and breaking (exception keeps REF-anywhere), and new tests were added. The .claude/wuwei mirror is identical to cli/wuwei.
- Suite at this head: 971 passed, 2 skipped. tests/fixtures/routes.json sha256 93d26ddc4551ca97183df579631b05392c0af8edc7cd59d776163e8d16ffa20f, the same as main. Route and merge-route tests give 141 passed.
- rulings.py battery (33 questions, real hook.handle) on main and this head. This head records nothing main did not, except class case and whitespace variants and "owner review:" with no space, each with the REF right after the class. Dropped versus main (all fail closed): text before the class, a REF after other text, a 41-hex sha or a sha followed by a word character, non-ASCII digits, and owner review text inside exception:, plan:, one-way: and scope: questions.
- e2e.py on main and this head: lib#3 False, app#9 False on both.
- Fuzz of guard admit against recorder ruling: 1680 owner review and breaking questions (7 prefixes, 8 middles, 6 REF forms, 5 suffixes). 0 mismatches.
- Documented shapes run through the head guard and recorder: design.md:62-63, skills/wuwei-rules/SKILL.md:55, docs/site/concepts/decisions.md:37-40, charters/shepherd.md:43, charters/planner.md:74, the evidence.py:344 breaking ask line, and the guards.py:351 template. All are admitted and recorded, including the 40-hex head form and the exception "and #m at <sha>" form. Found with grep -rni "owner review:\|breaking:\|exception:" on those paths. The anchored guard refuses no documented shape. "owner review: owner/repo#n at <sha7>: x" now passes where it newly fails only for a sha followed by a word character, uppercase hex or a URL ref, which main's recorder also could not record correctly.
- Mutants, each in a fresh git archive copy: the hook pattern widened to "[\s\S]*?" after the class, and the guard pattern widened the same way, are killed by the new two-REF tests. hook re.search, found[2] removed, guard re.search and guard \b removed survive (see findings).
- Confidence is high because every claim comes from runs on real code on both trees, and the fuzz agrees with the probes.

## Residual risk
The authority hole main has is closed by code at this head but held by no test until the finding is fixed. owner_approved accepting rulings of any kind predates this change.
