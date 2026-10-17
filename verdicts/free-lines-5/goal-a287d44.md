Verdict: PASS
Gate: goal
Item: free-lines-5
PR: taoq-ai/wuwei#1123
Head: a287d4458e68ee0cafb94c0e70246718a8892ed0
Confidence: high

## Findings
- [low] blocks: no. The PR body's Timing line names the worst ratio 1.12 as `evidence.verdicts` at 500 KB with 39.5 ms against 44.2 ms, which is a ratio of 0.89, not 1.12. The claim under it (worst at or under 1.20) still holds in my own re-run, but the example cited is wrong.
- [low] blocks: no. The timing of `upgrade.items` at 125 KB is noisy because the plan writes are I/O bound. One base run came in fast (648 ms), and its first two rounds gave a ratio of 1.26. Rounds 3 and 4 gave 1.00, the best of 4 rounds gave 1.18, and the builder's 4 rounds gave 0.97. The only change in that function is a counter replaced by `len(known) - before`, which costs O(1).

## Probes
- Promise and acceptance read from .wuwei/plan.json (free-lines-5). Goal G-2: the freed room is for the bug-fix items that come next.
- Lines (git show of every cli/wuwei/*.py | wc -l): 2996 at d1c3d79, 2975 at the head. 21 freed, and the floor is 12.
- Scope (git diff --stat d1c3d79..head): 10 runtime modules plus a byte-identical vendored copy (diff -r of cli/wuwei and .claude/wuwei/cli/wuwei in the head archive: no difference), plus specs/free-lines-5/. guards.py is byte-identical to main. No added line passes 150 characters and no `;` was added. The message strings are unchanged, including the upgrade import line.
- I read each rewrite by hand. board.rows is the same as the `_cached` body with TTL kept. `mine` equals the inline filter, in the same order. agents.stale, report.learning, the walrus pairs and the inlined path in evidence.verdicts are all equivalent. In upgrade.items both loops add only ids not already in `known`, so `len(known) - before` equals the old counter.
- Differential probe (builder's test_zz_probe.py, re-run on fresh git archive copies of d1c3d79 and the head in scratchpad/goal-free-lines-5/): 29 output keys. Every key is identical, and the base and head JSON files are the same size. guards.bash ran 19,386 commands: the route corpus, the suite literals and 16,932 generated commands. Decisions: deny 11,138, pass 7,060, ask 1,187, note 1. They are identical on both trees, reasons included.
- Probe sensitivity: I made a mutant of the head where evidence.verdicts appends a byte to the verdict body. It changed evidence.verdicts and 4,736 guards.bash rows, so the probe sees the guard path that this item touches.
- Full suite at the head: 1,509 passed and 2 skipped. That count includes 9 tests from my dropped-in probe file; its writer test failed only because PROBE_OUT was unset. That leaves 1,500 suite tests passing, which matches the PR body.
- Timing (builder's timing.py, 4 alternating rounds per tree, best of each): the worst head/base ratio over all 38 shapes was 1.18 (upgrade.items at 125 KB, noise, see the note above). Others: agents.stale 1.11 at 125 KB and 1.07 at 500 KB, board.rows miss 1.06, plan.mark 1.08. Every other shape is at or below 1.05. Nothing exceeds 1.20.
- The spec matches the diff: FR-001 to FR-006 hold. The design table sums to 21, and each "How this fails" scenario is covered by the probe's cache, `mine` and upgrade cases.
- Confidence is high: the probe output is byte-identical, a mutant shows the probe is sensitive, and every rewrite is plainly equivalent when read.

## Residual risk
The timing of I/O-bound shapes (upgrade.items) has noise near the 20 percent line. A future rerun could cross it by chance even though nothing in the algorithm changed.
