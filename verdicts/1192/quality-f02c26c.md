Verdict: PASS
Gate: quality
Item: 1192
PR: taoq-ai/wuwei#1194
Head: f02c26ca9aaa4199d1d9032e5d70ca87cf2728d5
Confidence: high

## Findings
none

## Probes
- Exact revert: `git rev-parse HEAD^{tree} 36afe729^^{tree}` both give eab5395f; `git diff --stat 36afe729^ HEAD` is empty; the diff 36afe729..HEAD is byte-identical to 36afe729..36afe729^ (14 files, 32 deletions, the same 14 files #1193 touched, nothing else moves).
- No taoq-wuwei left: `git grep -i taoq-wuwei` is empty at the head and in the merge of the head into origin/main 2226d907 (`git merge-tree --write-tree`, clean, tree 73692365). origin/main itself still holds the trailer in 12 places, which this PR removes.
- Charter drift: in a `git archive` copy of the head, `bin/wuwei agents build` exits 0 and `diff -r` shows agents/ and .claude/ unchanged.
- Suite: `uvx --python 3.12 pytest -q` in the archive copy gives 4 failed, 2737 passed, 1 skipped (no /usr/lib/git-core/git-clean). The 4 failures are test_the_hook_commands_run_under_either_harness_shell and three test_bash_runs_the_push_in_each_refused_shape cases, the main failures named in the brief. The head tree is identical to main at 8a92be70, so they come from main and are not counted.
- Mutants: not run. The diff changes no guard or validation; it removes a prose line and the test that checked it. A test-only removal of a dropped requirement leaves nothing to mutate.
- No test: a revert of a docs-only requirement the owner dropped; the removed test checked the dropped line.
- Simplicity: none to delete; the change is pure deletion.
- Confidence high: tree identity with the pre-change commit and a clean merge with current main are mechanical proofs.

## Residual risk
Main moved one commit (#1184, touching tests/test_charters.py) since the base; the merge is clean but the suite was run at the head, not on the merged tree.
