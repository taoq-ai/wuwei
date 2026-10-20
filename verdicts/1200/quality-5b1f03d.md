Verdict: PASS
Gate: quality
Item: 1200
PR: taoq-ai/wuwei#1203
Head: 5b1f03de2af84eb6e556d9bd6d13dec37a32d5df
Confidence: medium
Breaking: no
Supersedes: 1200/quality-e3cdef2.md

## Findings
none

## Probes
- closed: run-owed note never written on the real `plan run` path at 5b1f03d. The test now builds R through `cli.main(['plan','run','R','--reason','run: head none on production'])`, merges a PR naming R and B, and asserts the board gap reads `run: run: head none on production; code merged as acme/app#9, run owed`, R open, B done, exactly one item.open row carrying "run owed" after a second compute, and `plan done R` closes it.
- closed: `not linked` mutant survived at 5b1f03d. The new test_a_run_item_with_a_merged_and_an_open_pr_keeps_its_run_evidence (run item, one merged and one open PR) now kills it.
- closed: first-writer-wins and restored-reason notes at 5b1f03d. The note is appended to the existing reason, so a restored item reads `restored; code merged as ..., run owed`.
- Ran at 5b1f03d from `git archive`, offline gh on PATH, CLAUDE_CODE_SESSION_ID unset, uvx python 3.13: tests/test_watch.py 25 passed; full `pytest -q` 3000 passed, 1 skipped, 4 failed; the 4 failures (test_codex hook-commands-under-either-shell; test_guards push shapes `{fd}>x`, `{a_b}<x`, `|& sh -s`) are the bash 3.2 failures the brief names, unrelated to board.py.
- Mutants applied to both cli/wuwei/board.py and .claude/wuwei/cli/wuwei/board.py, test_watch.py and test_plan.py run one mutant at a time with the vendored-copy test deselected, 12 of 12 KILLED by behavioural tests: dropping `kind != 'run'`; `!=` to `==`; dropping the `'run owed' not in` guard; inverting it; dropping `not linked` from the note line (killed by the merged-plus-open test); dropping `done` from the note line; status 'open' to 'done'; dropping the prior reason from the join; `'; '` to `' '`; dropping the `item['reason'] =` assignment; note text change; dropping the PR ref from the note. Copies restored and byte-identical to the head afterwards.
- Failed before implementation: with board.py from main (5b5084b) and the new tests, test_a_run_item_stays_open_with_run_owed_when_its_pr_merges_until_plan_done fails; the merged-plus-open test passes on main by design (it guards the open-PR path against regression).
- CI at the head, read with `gh pr checks 1203 --watch` after the run finished: test 3.11/3.12/3.13, Analyze (actions), Analyze (python), CodeQL, ZIRAN, ziran-audit all pass. Head unchanged at 5b1f03d when the verdict was written.
- Vendored copy of board.py is byte-identical to cli/wuwei/board.py (diff clean).
- Simplicity: none to delete; the note is two lines in one existing branch and reuses plan.mark and the existing reason; the two `import os` and `from wuwei import __main__` lines inside the tests follow the file's local-import style.

## Residual risk
A second merged PR for the same run item does not refresh the ref in the note (first merged PR wins); the item stays open and the evidence line is still correct, so the harm is cosmetic.
