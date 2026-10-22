Verdict: FIX
Gate: security
Item: 1223
PR: taoq-ai/wuwei#1228
Head: 08dc011b6621fa4f459658921a38c3d674f0aa05
Confidence: high

## Findings
- [medium] cli/wuwei/evidence.py:208 blocks: yes. Failure: the collision rule compares cuts by exact text while evidence.excepted matches by casefolded, whitespace-collapsed text, so in a `| Severity | Location | Summary |` table the rows `| HIGH | spec.md | <90 a> |` and `| High | spec.md | <90 b> |` (or `|  spec.md |` spacing, or a short row `| high | spec.md |`) both print as `...finding: | HIGH | spec.md |` up to case or spacing, and one Yes on the first opens merge_door with both waived and neither summary ever shown (CWE-451, requirement excepted-exact)
- [medium] cli/wuwei/evidence.py:435 blocks: yes. Failure: the spec-gap cache key is `{ws.version()} {engine} {tier}` and the version stays 5.1.1 until the release PR, so an entry written by 6828776 code for a full-tier PR head holds the single-row list for up to 24 hours; read by 08dc011 code it prints only A1, the guard passes the A1 question, and one Yes opens merge_door with the CRITICAL A2 hidden, in a workspace that runs the repository's vendored plugin (this one does: .wuwei/executable names .claude/wuwei/bin/wuwei) right when the deadlocked full-tier PRs this item unblocks get asked (CWE-524, requirement excepted-exact)
- [low] cli/wuwei/evidence.py:208 blocks: no. Rows whose cuts collide print whole with no length cap, so a PR-authored analysis.md with many colliding long rows puts unbounded row text into the merge door reason and wuwei evidence (LLM01/LLM10 note); a row index instead of the whole row would keep the cap.
- [low] cli/wuwei/evidence.py:207 blocks: no. A long row with no cell edge in its first 100 characters and a `. ` inside them (`| <40 x>. y <70 z> | HIGH |`) prints a raw cut the hook reads short: waives nothing on 10 of 10 tails, fail closed.
- [low] cli/wuwei/hook.py:408 blocks: no. Fail closed, as the builder reports: a row with no trailing `|` (10 of 10 tails) and row questions whose own words end in `|` (` | Accept?`, `. Accept? | yes | no |`, ` | forged |. Accept?`).
- [low] blocks: no. Two identical open rows dedupe to one gap and one Yes waives both; their content is the same, so the owner saw it.

## Probes
closed: [high] evidence.py:209 one Yes on the first printed row hides the next at 08dc011 (A1/A2 end to end: first Yes leaves the door held with A2 printed, second opens it, 7 of 10 tails; the other 3 hold both, fail closed; at 6828776 all 10 sent back).
closed: [medium] evidence.py:194 first checklist only at 08dc011 (a.md then security.md: held after the first Yes, open after the second, 8 of 10 tails; 2 hold, fail closed).
Collision probe (rows written by code, Yes through guard and hook.handle, then merge_door): case, spacing and short-vs-cut each print 2 gaps and open the door after 1 Yes (0 left); exact-same-cut prints whole and holds after 1 Yes (the fix's own case works); identical rows print 1 gap.
Stale cache probe: STAGE=write at a 6828776 copy and STAGE=read at an 08dc011 copy sharing one root, both version 5.1.1: read prints 1 gap (A1), guard passes, door open after 1 Yes; control with a fresh root at 08dc011 prints A1 and A2, door held. A format marker in the key (or any change to it) closes it.
Row shapes x 10 tails at 08dc011: break, qmark, long-break-after-pipe (closed round 1 hole: now opens on 7 of 10), accept-inside and pipe-dot-inside open on 7 of 10 and hold on the 3 tails with their own `|`; long-one-cell and no-trailing-pipe hold 10 of 10.
Route differential with approved exceptions (corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, 288 routes, 6828776 vs 08dc011): plain 0 moved; excepted (every blocking gap of o/r#5 accepted) 0 moved, 22 merge routes pass at both; spec-first (A1 and a.md accepted) 22 merge routes on o/r#5 move pass to merge, held on A2 and security.md, plus 1 reason-only move on other/x#5; spec-all 0 door moves, 1 reason-only move on other/x#5. Matches the builder's 22.
Mutants on the changed lines of _rule and spec_gaps (both copies, one at a time, -x): collision rule off KILLED (test_rows_whose_cuts_are_the_same_are_printed_whole); raw 100-character cut KILLED and leading pipe as cell edge KILLED (test_a_long_finding_row_is_printed_to_its_last_cell_edge_within_100_characters); first row only, first checklist only, first problem per rule KILLED (test_each_open_finding_row_and_each_checklist_with_an_unchecked_box_is_its_own_gap). 6 of 6. No mutant of the norm collision: no test covers it.
Full suite not run on the owner's instruction (CI green at 08dc011). PR head re-read: 08dc011.
Confidence high: both blocking findings reproduce through merge_door at 08dc011 against a control that holds.

## Residual risk
Both fixes are small: count the cuts by the norm evidence.excepted uses (or tag a colliding row with its index), and change the spec cache key. A row cut at 100 characters still shows the owner only its leading cells; its ID names it.
