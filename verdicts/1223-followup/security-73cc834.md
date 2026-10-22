Verdict: PASS
Gate: security
Item: 1223-followup
PR: taoq-ai/wuwei#1235
Head: 73cc834ca1be610b92c4deacc26e1c6688464256
Confidence: high

## Findings
- [low] cli/wuwei/evidence.py:228 blocks: no. Place numbers follow the order the host lists a checklists folder; with the listing reversed, 401 of 1000 generated PRs print in another order and twins swap numbers (`(1 of 2) checklists/A.md` becomes `(1 of 2) checklists/a.md`), so a yes recorded on one twin may later waive the other. Twins' texts are equal except for case, every printed set stayed distinct, and each yes still waives one gap.
- [low] cli/wuwei/hook.py:408 blocks: no. Carried from 10038fb and now in design.md: a row whose feature folder holds `. ` or `?` cannot be waived (fails closed).
- [low] cli/wuwei/evidence.py:225 blocks: no. Carried from round 2: rows that print whole carry no length cap into the merge-door reason, and the pr-wide rule prints whole more often.

## Probes
Copies: `git archive` of 73cc834 (scratch d2), 10038fb, main d141928 and 6828776. Pytest imports `wuwei` from each tree's own `cli/` (conftest inserts it first). The vendored copy matches `cli/wuwei` at 73cc834 (`diff -r`). Head re-read with `git ls-remote origin refs/heads/leone/1223-followup`: 73cc834ca1be.
closed: [medium] evidence.py:209 cut meeting another row's whole print at 73cc834 (r3 cut-vs-whole-spaces and cut-vs-whole-casefold: 3 gaps take 3 yeses, held after the first two; a yes on E alone leaves 2 gaps, and D's hidden text is printed. At 10038fb: 2 yeses, D hidden).
closed: [medium] evidence.py:224 case-twin feature folders at 73cc834 (r3 case-features: held after 1 yes, 1 left; at 10038fb, open after 1 yes).
closed: [low] evidence.py:195 case-twin checklists at 73cc834 (held after 1 yes, 1 left).
closed: [low] evidence.py:209 untested lower() for casefold at 73cc834 (killed by the U+00DF and U+212A parametrize cases, per the builder's mutants and my seen/keys mutants).
closed: [low] evidence.py:436 marker needs a change with the fix (now ` rows pr-wide`). Stale probe: cut-vs-whole rows cached by 10038fb code and read by 73cc834 code in one root at version 5.1.1: 3 gaps printed with D's hidden text, held after a yes on E with 2 left. Control (10038fb wrote and read): D hidden, 1 left.
r2 and r3 probes at 73cc834 (test_zz_sec_r2.py and test_zz_sec_r3.py, 108 cases): case, spacing, short-vs-cut and exact-same-cut each held after 1 yes. All r3 collision shapes (U+00DF, U+212A, tab, U+00A0, inner and trailing spaces, row equals cut) take 2 yeses. Identical rows: 1 gap. The 10 row shapes x 10 tails and two-rows/two-checklists read the same as at 10038fb and main (7 of 10 open, 3 hold fail closed; long-one-cell and no-trailing-pipe hold 10 of 10).
Place-number forgery, generated (test_zz_sec_r4.py, 1000 full-tier PRs, seeds 0-999). The pool holds 12 folder names, among them `(1 of 2) 7-x`, `7-x (1 of 2)`, `(2 of 2) 7-x`, `7-x(1 of 2)` and case and casefold twins. It also holds 7 checklist names, among them `(1 of 2) a.md` and `a (1 of 2).md`, and 14 rows, among them `(1 of 2)` cells and a row holding a whole forged gap text. Results at 73cc834:
- 981 PRs had gaps, 5948 gaps in all, 667 PRs with place numbers.
- 0 PRs with two printed gaps equal under evidence.norm (10038fb: 213).
- 0 of 5948 gaps misread by hook.exception_refs, and 0 read as another gap.
- 0 unstable between two reads of one head.
- With the host listing reversed: 0 PRs lose distinctness, 401 change order.
- End to end, 100 PRs (seeds 10000-10099), one yes per printed gap through guard and hook: 97 of 97 with gaps open exactly at the last yes (10038fb: 75 of 97, 22 open early).
Why a forged number cannot match: the number is inserted right after the feature folder's closing `/`, and every other gap continues after its folder with a fixed artifact name (spec.md, plan.md, tasks.md, analysis.md, checklists/, or openspec's proposal.md, specs/). Folder names cannot hold `/`.
Print order at one head: features are sorted, rows keep file order, checklists follow the host's listing (git tree order), and the cache holds the result for 24 hours. A reorder only swaps numbers between texts that are equal under norm (see the first note).
Route differential with approved exceptions (corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, 288 routes):
- plain, excepted, spec-first, spec-all: 0 door moves and 0 reason moves against main and against 10038fb.
- collide (case rows, first row's gap accepted): against main, 22 merge routes move from pass to deny, plus 1 reason-only move on other/x#5; against 10038fb, 0 moves.
Mutants on the delta (both copies, one at a time, -x, 255 selected tests), 6 of 6 killed:
- seen holds cuts only: KILLED by test_rows_whose_cuts_are_the_same_are_printed_whole[rows8].
- seen holds wholes only: KILLED by test_a_long_finding_row_is_printed_to_its_last_cell_edge_within_100_characters.
- place always 1, place without `of n`, alike by exact text: KILLED by test_gaps_that_still_read_alike_carry_their_place_after_the_feature_folder.
- cache marker of 10038fb: KILLED by test_a_spec_gap_result_cached_by_older_code_at_the_same_version_is_not_read[ rows].
No scanner run: no agent tooling or dependency changed. Full suite not run, on the brief's instruction.
Confidence high: every earlier blocking case holds end to end at 73cc834 against 10038fb controls that fail, and the generated forgery probe found 0 matching pairs in 5948 gaps.

## Residual risk
The rule now holds across the whole PR. A future change to what spec_gaps prints at the same version needs a new cache marker again.
