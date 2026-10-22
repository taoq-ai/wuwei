Verdict: FIX
Gate: quality
Item: 1223
PR: taoq-ai/wuwei#1228
Head: b6d06355cfedbb71a97acb2961e27092c95c00f5
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:407 blocks: yes. Failure: the last-`|` rule now applies to every exception question, not only to finding rows, so `exception: o/r#1 at abc1234: gates missing at head abc1234: quality. Accept (yes|no)?` (or `no test in the diff. Accept (yes|no)?`) is recorded as gap `... quality. Accept (yes|no)`; at 6828776 it was recorded as `gates missing at head abc1234: quality` and waived the gap. At the head the owner's Yes waives nothing, the hook still tells the session "exception recorded", and a follow-up item titled with the wrong gap enters the plan (regression outside the promise, which changes only finding rows; same line at .claude/wuwei/cli/wuwei/hook.py:407). One-line fix: take the last `|` only when the gap holds a row (for example only when `': |'` is in the tail), so a gap without a row reads exactly as on main.
- [low] blocks: no. A finding row that evidence cuts at 100 characters with a `. ` or `?` after its last printed `|` is still recorded short and waives nothing (fails closed). 2 of 702 non-separator rows in this repository's analysis.md files at 6828776 have that shape, as the PR says. The fix belongs in evidence._rule (cut at a cell edge), as the PR's review notes propose.
- [low] blocks: no. Below full tier a spec gap is process fit, yet an exception: question naming one now reaches the owner, who gets asked about process fit; a Yes records a ruling and an X- follow-up item for a gap that never held the merge. This is the item's recorded assumption (evidence.visible and blocking hide process gaps, so seats do not see them). The replaced test covered the only guard case for it. A tier-aware guard (read the PR's plan item tier) would bring the below-full case back, but the runtime budget is 4 lines.

## Probes
- Suite at the head (git archive copy, /root/.local/bin/pytest -q): 3227 passed, 2 skipped.
- Focused tests (-k "sentence_breaks or spec_gap or process_gap or finding_row or accepted_spec_gap"): with head tests on 6828776's cli/ there were 14 failed and 7 passed; at the head 21 passed. Matches the builder.
- Route corpus tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at both trees. The builder's route_probe.py at 6828776 and at the head gave 288 routes each, diff empty: no route moves in verdict or reason.
- Builder's question probe re-run, with classes added: kinds 'long row no break in cut', 'long row break before last bar', 'long row question in cut', 'row break at end of cell'; tails '. Accept (yes|no)?', ' | Accept?', '. Accept? 1. yes 2. no', '.\nAccept?'. Result: 18 kinds x 3 tiers x 10 tails = 540 questions. At 6828776: 30 reached the owner, 510 sent back, 423 holes. At the head: 450 reached the owner, 90 sent back, 60 holes. Hole classes at the head: long row cut and long row question in cut (all tails, full tier); every kind with a `|` in the tail (' | Accept?' and '(yes|no)'). Holes at the head that were not holes at 6828776: 3, all 'no test' x '(yes|no)' tail x light/standard/full, waived at 6828776. That is the blocking finding.
- Direct read of hook.exception_refs at each tree: 'gates missing at head abc1234: quality. Accept (yes|no)?' gives 'gates missing at head abc1234: quality' at 6828776 and 'gates missing at head abc1234: quality. Accept (yes|no)' at the head.
- Differential probe of exception_refs, 6828776 vs head, on generated questions without `|` (4 prefixes x 3 ref chains x 4 separators x 8 gaps x 10 tails): 3840 generated, 0 differences. So the change matters only when a `|` is present.
- Builder's row count reproduced: in specs/*/analysis.md at 6828776, 702 non-separator rows, 51 with a break in the printed part, 49 read whole. At the head, with this item's spec added: 712, 52, 50.
- Mutants (both copies, run one at a time, tests/test_guards.py, test_hook.py, test_evidence.py, -x): the builder's 12 plus 3 of mine (guard regex with openspec/ added; hook rfind('| ') + 1; hook rfind('|') + 2). Result: 15 of 15 killed, each by a behavioural test (spec_gap_reaches_the_owner, process_gap_goes_back, finding_row_waives_only_the_whole_row, accepted_spec_gap_opens_the_merge_door, sentence_breaks_of_a_finding_row). None was killed by the vendored-copy test or a line-count test.
- Replaced contract test: the old case (a spec gap exception is sent back) is now wrong at full tier, which is what the item fixes. Below full it still describes the charter (process fit: nobody is asked), and no test pins that tier any more. See the third note. evidence.visible and blocking keep process gaps away from seats, so a planner asks this only if it reads the retro record.
- Runtime lines: 3396 at both trees (cat cli/wuwei/*.py | wc -l). Commits are authored by Leone with the Co-Authored-By trailer.
- Tests are deterministic (no wall clock, network or shared file). They assert on decisions, ruling rows, plan item titles and merge_door results. The process-gap test's 'never block' check on the reason is the existing style.
- Simplicity: none. The diff is 3 runtime lines per copy, all needed. The fix narrows one condition and adds no code.
- Confidence high: every count above is from my own runs at b6d0635 and 6828776. Realistic use is unmeasured, since the ledger here holds no exception questions.

## Residual risk
Long finding rows cut by evidence at 100 characters still cannot be accepted when their cut part holds a sentence break. Below full tier, the owner can be asked about a spec gap that is process fit.
