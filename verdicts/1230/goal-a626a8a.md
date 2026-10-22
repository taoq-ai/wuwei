Verdict: PASS
Gate: goal
Item: 1230
PR: taoq-ai/wuwei#1234
Head: a626a8aa68f9feece50525a9d245ae1caa4c9e06
Confidence: medium
Breaking: no
Supersedes: none

## Findings
- [low] blocks: no. A moved file counts all its head-to-head lines, main's lines in that file included, so a small conflict resolution in a file main also changed by over 20 lines can still owe quality. The spec and the PR review notes say so; it fails safe and the issue does not forbid it.
- [low] blocks: no. Main's edit within three context lines of a PR hunk makes the file count as moved (probe row adjacent/risky owes security). This is the safe direction and is stated in the spec; it may leave some ai-stacks renumber merges still owing a re-read.
- [low] blocks: no. The PR body figures "18 failed, 8 passed" at fbf187b and "3237 passed, 2 skipped" for the full suite were not re-measured here (full suite not run by instruction); they are unmeasured, not contradicted.

## Probes
- Trace: issue #1230 Problem and Proposal 1-3 map to the plan promise and three acceptance scenarios. The spec restates all three in the builder's words and they match the item (own-diff delta, 30-line conflict resolution owes the named gate, declared generated files carry).
- Acceptance 1: `wuwei evidence taoq-ai/wuwei#1234` itself shows only this PR's own owed gates, which is expected before review. The code path: `gaps` passes `baseRefOid` into `gate_gaps`, the merge door reads `gaps`, and `create_door` passes the compare's `merge_base_commit`, so all four routes (evidence, merge, ready, create) read one delta (FR-005).
- Re-ran `specs/1230-own-diff-delta/probe.py` at the head: main tree from `git archive fbf187b`, head tree from `git archive a626a8a`, scratch under /tmp/claude-0/-home-user-wuwei/3c3b5210-f1f3-5623-83c3-a701461b643a/scratchpad/sentinel-goal-1230/. Output: "generated 26, ran gate_gaps at both trees 26 and 26, holes 0". Table identical to the committed `probe.txt` (only the timing lines differ). The PR body's "26 generated, 26 read through gate_gaps at both trees, 0 holes" and "13 kinds x 2 path classes" match the output I read. Main owes security on far, above, adjacent, conflict and update-branch rows; the head carries those on plain and far/above/update-branch rows on risky paths; conflict-add30/plain owes quality and risky owes security (acceptance 2); fix-1 and fix-25 and main-only rows read the same at both trees.
- `pytest -q tests/test_evidence.py tests/test_guards.py -k "base_merge or 300_file_cap"` in the head archive: 26 passed, matching the PR body's "green: 26 passed". Vendored-plugin and agents tests: 12 passed.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` gives 3373 at fbf187b and 3381 at the head, matching "3,381 against 3,373 (+8)" and under the 3,400 cap.
- Acceptance 3: the `Generated (<repo>, <date>):` standards line is a declared-per-workspace mechanism as the issue asked ("declared per workspace"). Tests cover 8 spellings per the PR body; the diff shows the filter applied to the moved set. The spec states the choice over `.gitattributes` as an assumption with its overturn condition.
- Drift: no claim beyond the issue except the Generated line syntax, which is the issue's own point 2 and is documented in design.md, concepts/evidence.md and reference.md. No required outcome is missing; the 300-file cap, the missing-patch case and the no-base case are stated in the spec and PR body.
- Route differential: the PR body says 0 of 288 moved on the gap and fix hosts and 54 moved on the merge host, all from a delta-review refusal to pass. Not re-run here (the brief asked for the probe only); the committed `route_diff.txt` is the source.
- Confidence is medium: probe and targeted tests were re-run; the full suite and route differential were not.

## Residual risk
A hunk moved between identical three-line contexts carries unread (stated in the spec). Whether GitHub's `base.sha` stays at or after the merge base was read on four PRs by the builder and fails safe if wrong.
