Verdict: PASS
Gate: security
Item: 1212
PR: taoq-ai/wuwei#1216
Head: 425434936c612b7bb6dfcc28f809dd2236627cb8
Confidence: high

## Findings
- [low] cli/wuwei/board.py:130 blocks: no. A job file that never parses now costs up to 0.6 s of sleep per cold board compute (board.rows runs from the Stop hook, cached for TTL); the read itself is unchanged, so a planted FIFO or /dev/zero job path blocks or exhausts memory exactly as on main, three times at most, never newly (CWE-400, existing gap; the path comes only from the planner's plan run --job).

## Probes
- Head: git rev-parse HEAD in the builder worktree gives 425434936c612b7bb6dfcc28f809dd2236627cb8, parents 37a44d7 (branch) and c0fea45 (origin/main, read with git fetch then git rev-parse origin/main, matches).
- Merge resolution: git show --remerge-diff on the head shows one conflicted file, tests/test_plan.py, resolved by keeping #1214's test_the_plan_list_shows_an_item_with_no_goal first and this PR's test second; no other file differs from the automatic merge.
- PR diff against main (git diff c0fea45 4254349): cli/wuwei/board.py and .claude/wuwei/cli/wuwei/board.py +3/-1 each, tests/test_plan.py +17; byte-identical to the previous PR diff (merge-base c2fafc7 to 37a44d7) apart from the hunk context lines in test_plan.py.
- guards.py and hook.py: git diff c0fea45 4254349 on both copies is 0 lines; the head's hook.py is main's, carrying #1217 (gated by security and owner-approved), base c2fafc7 to head differs only by that change.
- Route corpus: tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at main and head. Differential: all 288 routes read through guards.bash (door verdict and reason) and through hook.pre_tool (Bash payload, permission_mode auto) in git archive copies of c2fafc7 (base), c0fea45 (main) and the head; 0 routes move base to head, 0 move main to head, 0 hook errors. Head verdicts: refusal 109, pass 75, push 45, merge 25, ready 21, create 13.
- Vendored copy: diff of cli/wuwei/board.py and .claude/wuwei/cli/wuwei/board.py at the head is empty. Runtime budget: wc -l cli/wuwei/*.py gives 3396 of 3400.
- Full suite in a git archive copy of the head: pytest -q gives 3209 passed, 2 skipped.
- Mutants, each applied to both board.py copies in a fresh archive copy, tests/test_plan.py -k job: range(3) to range(1) killed by test_a_job_file_read_while_the_companion_writes_it_is_read_again; isinstance(dict) guard replaced by "is not None" killed by test_an_unreadable_codex_job_file_never_reads_done[[1]] (a JSON list job file would otherwise crash the board); sleep removed killed by the new test. All three fail behaviourally.
- Trust paths: the job path is joined to root exactly as before and read through ws.read_json, which fails closed to None; the fallback stays {} so a never-parsing file still reads "state unreadable", never done. No new dependency, workflow, secret, network call or log output in the PR's diff.
- Confidence high: the PR's own diff is unchanged and small, the merge resolution is test-only, the guard and hook files equal main's, and the differential shows no move.

## Residual risk
Board latency on a persistently unreadable job grows by up to 0.6 s per cold compute; the job-file read path keeps main's existing trust in the planner-registered path.
