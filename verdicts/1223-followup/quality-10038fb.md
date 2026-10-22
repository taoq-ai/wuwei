Verdict: PASS
Gate: quality
Item: 1223-followup
PR: taoq-ai/wuwei#1235
Head: 10038fbe4ac7452bcaf298ac735c1bfe0a03f0aa
Confidence: high
Supersedes: none

## Findings
- [low] docs/design.md:84 blocks: no. The new sentence says rows print whole when their printed parts match "case and spacing aside", but `norm` (evidence.py:37) also drops end marks and a printed `[waiting]`, as the earlier design paragraph on exceptions says. The code is the safer, wider rule; the sentence is only narrower than the code.
- [low] cli/wuwei/hook.py:408 blocks: no. A finding-row gap followed by a tail that carries its own row-end `|` (`. Accept? | yes | no |`, `. Accept? |.`, `. Options: | yes | no |`) is still recorded long and waives nothing (fails closed). This is the row-plus-row-end-tail ambiguity noted at 08dc011; it is not a new class.
- [low] blocks: no. PR body or builder report: the red count is 11, my run shows 14 (see Probes). The tests are a superset of what was reported; no action.

## Probes
- Differential, my own run of scratch diff_refs2.py (1140 questions: 2 prefixes x 2 ref chains x 15 gaps x 19 tails) over git archive copies at 6828776, d1419285 and the head 10038fb. Right at 6828776: 612. Right at d1419285: 832. Right at head: 856. Right at d1419285 and wrong at head: 0. Right at 6828776 and wrong at head: 36. These match the builder's numbers.
- The 36: exactly 3 finding rows (A10, A17, A20) x 3 tails (`. Accept? | yes | no |`, `. Accept? |.`, `. Options: | yes | no |`) x 4 prefix/ref combinations. Every one is a finding row followed by a tail whose own `|` sits before `[.?]` or the end, so the row-end regex takes the tail's bar. The 36 are a subset of the 60 listed at 08dc011; the other 24 (non-row gaps with `. Options: | yes | no |`) are fixed. I listed every question wrong at the head (284); the 36 are the only ones that were right at 6828776, and the rest (` Accept?` with no break, ` | Accept?`, rows without a trailing bar) were wrong there too. No new class.
- Red check: head tests run against the d1419285 code in a copy: 14 failed (9 hook `. Options:`, `. Note:`, `? Options:` x 3 gaps; 4 case/spacing row params; the old-cache test), 810 passed. Head tests, tests/test_hook.py plus tests/test_evidence.py: 824 passed. The other new hook tails (`. Accept? |.`, `. Options: | yes | no |` after a row) pass at base as regression pins, which is expected.
- Property probe (scratch prop.py, seed 1235): 14596 random cases of 2 to 4 finding rows (case, tab and space variants, rows over 100 characters) through `evidence._rule` with a stubbed `gh.file`. Row pairs distinct under `norm`: 32289. Pairs whose printed texts are equal under `norm`: 0 at the head, 17 at d1419285. So no yes on one printed gap waives a row the owner did not see, and the probe does catch the bug on main.
- Mutants, applied to both cli/wuwei and .claude/wuwei/cli/wuwei, one at a time, tests/test_hook.py, test_evidence.py and test_guards.py: 8 of 8 killed by a behavioural test. M1 `in first` to `in tail`: test_a_gap_that_holds_no_finding_row_ends_at_its_first_break_whatever_the_tail[. Options...]. M2 drop `\?` from `first`: the `? Options: | yes | no |` param. M3 drop `\.\s` from `first`: the `. Options:` param. M4 exact `cuts.count(cut)`: test_rows_whose_cuts_are_the_same_are_printed_whole[High]. M5 no whitespace collapse in `norm`: test_an_exception_naming_the_printed_gap_waives_that_gap_alone. M6 no casefold: same test. M7 drop ` rows` from the cache key: test_a_spec_gap_result_cached_by_older_code_at_the_same_version_is_not_read. M8 `count(cut)` without `norm`: test_a_long_finding_row_is_printed_to_its_last_cell_edge_within_100_characters.
- Test quality: the new evidence test goes through the real consumer (`evidence.gaps`, then `guards.merge_door` with an exception ruling) and asserts the second row is in the refusal. The cache test seeds the pre-#1228 key shape in the real cache and reads through `gaps`. No wall-clock, network or shared-file dependency in the added tests.
- docs/design.md matches the code: the `: |` before the gap's first `. ` or `?` rule and "whatever `|` the question's own words hold" read as hook.py:408-409 does; the printed-cut rule reads as evidence.py:209, apart from the low note above.
- Process: vendored copy cli/wuwei and .claude/wuwei/cli/wuwei differ only by __pycache__. Runtime code is 3374 lines in cli/wuwei/*.py (limit 3400). Commits are authored by Leone.
- Not run: the full suite (CI does), per the brief.
- Simplicity: none. `norm` moved to module level so the print and the match use one function; it is needed by both `_rule` and `excepted`. The `first` split and the ` rows` key suffix are each pinned by a mutant that fails. Nothing here is trust-boundary validation I would list as deletable.

## Residual risk
Exception questions whose own words hold a row-end `|` after a finding row are recorded long and waive nothing, so the owner's yes is lost (fails closed). The key suffix ` rows` is a one-time constant: a later change to the cached row shape needs its own key bump.
