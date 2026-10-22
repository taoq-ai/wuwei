Verdict: PASS
Gate: quality
Item: 1223
PR: taoq-ai/wuwei#1228
Head: 08dc011b6621fa4f459658921a38c3d674f0aa05
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:408 blocks: no. The `': |' in tail` test reads the whole tail, question words included. A non-row gap whose question carries `: |` after the gap is still recorded long and waives nothing: `exception: o/r#1 at abc1234: no test in the diff. Options: | yes | no |` is right at 6828776 and wrong here. It fails closed, and the shape is a table-like tail no charter question form uses. Testing for `': |'` only in the part before the first break would close it. docs/design.md says "when the gap holds a finding row", which is narrower than the code.
- [low] blocks: no. A finding-row gap followed by a tail that has its own row-end `|` (`. Accept? | yes | no |`, `. Accept? |.`, ` | Accept?`) is recorded long and waives nothing (fails closed). This ambiguity is inherent to reading a row out of free text.
- [low] blocks: no. A malformed row with no trailing `|` (`| A11 | HIGH | Spec says X. Plan says Y`) cannot be accepted when it holds a break (fails closed). The builder's probe already lists this class.

## Probes
- closed: cli/wuwei/hook.py:407 `(yes|no)` tail regression at b6d0635. At 08dc011, `gates missing at head abc1234: quality. Accept (yes|no)?` and `no test in the diff. Accept (yes|no)?` read as at 6828776.
- exception_refs differential (generated, scratch scripts/diff_refs2.py): 2 prefixes x 2 ref chains x 15 gaps (6 non-row, 9 finding rows including `| .env`, `| x?|`, no trailing bar) x 19 tails (my round-1 classes plus `. Options: | yes | no |`, `. Accept? | yes | no |`, `. Accept? |.`, `.\nAccept (yes|no)?`, `. Reply yes|no.`, a trailing space). 1140 questions. Right at 6828776: 612, at b6d0635: 504, at 08dc011: 832. Right at b6d0635 and wrong at 08dc011: 0. Right at 6828776 and wrong at 08dc011: 60. These fall in 15 shapes (x4 prefixes and refs), all `. Options: | yes | no |` on non-row gaps or a row-end `|` in the tail after a row. They are the notes above.
- Question probe (the builder's, plus kind 'row with dot cell' and 5 tails: `. Options: | yes | no |`, `. Accept? | yes | no |`, `. Accept? |.`, `.\nAccept (yes|no)?`, `. Reply yes|no.`): 22 kinds x 3 tiers x 16 tails = 1056 questions per tree. At 6828776: 48 owner, 1008 sent back, 867 holes. At b6d0635: 912, 144, 248. At 08dc011: 912, 144, 84. Holes at 08dc011 that are not holes at 6828776: 3 (no test x `. Options: | yes | no |` x 3 tiers). Not holes at b6d0635: 0. Every hole at 08dc011 waives nothing (fails closed): the `|` tail classes, plus 'row without trailing bar'.
- Real rows: every non-separator row in specs/*/analysis.md at 08dc011 went through the new cell-edge cut and exception_refs with 6 tails: 718 rows, 4308 questions, 4308 read whole.
- Mutants on exception_refs (the builder's 17 hook.py mutants, applied to both copies, run one at a time, tests/test_hook.py and test_guards.py): 16 killed, each by a behavioural test. Survivor 18 (`m.end()` to `m.start()`): its differential against the head shows 0 differences over the 1140 generated questions and 200000 random questions (seed 1223, alphabet of `|`, `. `, `? `, `: |`, letters and newline), so it is equivalent.
- Suite at 08dc011 (git archive copy, run before the coordinator narrowed the scope): 3259 passed, 2 skipped.
- Commits 2ceaf42..08dc011 are authored by Leone.
- Simplicity: none. The cut condition and the row-end regex are both needed; the m.start form is equivalent, but no shorter.
- Confidence high: every count is from my own runs at 6828776, b6d0635 and 08dc011. The evidence.py delta was outside the narrowed scope, apart from the real-row read and the suite.

## Residual risk
Exception questions whose own words hold `: |` or a row-end `|` are recorded long and waive nothing, so the owner's yes is lost and the hook still says the exception was recorded. Real usage is unmeasured: the ledger holds no exception questions.
