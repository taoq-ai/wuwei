Verdict: PASS
Gate: security
Item: 1179
PR: taoq-ai/wuwei#1187
Head: 72b78c88e22bc31b52c5d0ef1f81038f30049509
Confidence: high

## Findings
- [low] cli/wuwei/evidence.py:350 blocks: no. Carried from security-1088243, unchanged by this merge (CWE-223, omission of security-relevant information): a refused, never-attested FIX next to a counted PASS of the same gate (setup B1), or a refused FIX for a gate whose earlier pass carries over a delta (C3), does not show at the merge door. The backstops are the hand-back denial and the verdict.missing row.

## Probes
- Head 72b78c8 is a two-parent merge: 1088243 (the PR head I passed) and main 17ff289 (#1184, #1193, #1194). git diff --stat 1088243..72b78c8 gives 17 files, +220 -18. That is the same stat as git diff --stat 8a92be7..17ff289, so the merge brought in main's change and nothing else.
- git diff origin/main(17ff289) 72b78c8 lists the PR's 19 files, +401 -128. I diffed it against git diff 8a92be7 1088243 (the diff at the earlier head). They differ only in blob index lines and hunk offsets, in two files main also touched (tests/test_charters.py, tests/test_hook.py) and in one other index line. Every added or removed line is identical. The cmp check passes: cli/wuwei/evidence.py and .claude/wuwei/cli/wuwei/evidence.py are byte-identical at the head.
- Main's own delta changes hook.py (both copies), the planner and sentinel-arch charters, docs and specs/adr-home. None of it touches evidence.py, verdict.py or guards.py. This PR's diff does not touch hook.py, and the merge needed no hand-resolved conflict.
- Route differential, my script (scratch probe/route_diff_sec.py): runtime at main 17ff289 vs runtime at head 72b78c8, both with the head's test helpers. routes.json sha256 is 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49 at both (263 routes). It ran the same 19 setups as before. I compared the moves with probe/cmp_moves.py and they match the 1088243 run exactly in every setup. 22 verdict moves (merge to pass, the same 22 routes) in A1, A4, A5, A8, A10, B4 and C1 with 57 reason moves, and in B1 and C3 with 54 reason moves. A3 has 0 verdict moves and 57 reason moves, C2 has 0 and 3. A0, A2, A6, A7, A9, B2, B3 and C0 have 0 and 0. No route moves differently from the 1088243 run.
- I ran the PR's own specs/verdict-shape-examples/route_diff.py (uv run --with pytest) with the main 17ff289 tree and the head tree, both with sha 4f6e25d0. Results: none 0/0, arch-bad 22 verdict and 57 reason moves, quality-bad 0/0, both 0 verdict and 57 reason moves. These match my A0 to A3.
- Full suite in a git archive copy of the head (uvx --python 3.13 --from pytest pytest -q, offline gh stub on PATH, CLAUDE_CODE_SESSION_ID unset): 2742 passed, 4 failed, 1 skipped. The 4 failures are the known bash 3.2 ones: test_codex hook shell and three test_bash_runs_the_push_in_each_refused_shape cases. Passes rose from 2741 to 2742 because main added a test.
- bin/wuwei agents check at the head: agents match the charters. cli/wuwei/*.py totals 3325 lines.
- CI at 72b78c8 (gh pr view once): 8 of 8 checks SUCCESS (test 3.11, 3.12, 3.13, CodeQL, Analyze actions and python, ZIRAN, ziran-audit). mergeStateStatus is CLEAN and the PR is still a draft.
- No dependency, lockfile or workflow change in the PR diff.
- Confidence is high: the PR's own diff lines are byte-for-byte unchanged, main's delta does not touch the changed function, and both differentials reproduce the earlier moves exactly.

## Residual risk
Same as at 1088243. A refused FIX for a gate that already passed is silent at the merge door, and the protection relies on the hand-back denial making the seat rewrite the file.
