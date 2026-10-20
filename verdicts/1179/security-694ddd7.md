Verdict: PASS
Gate: security
Item: 1179
PR: taoq-ai/wuwei#1187
Head: 694ddd78d90fa2292f3e3fd03fceb179a7c32be8
Confidence: high

## Findings
- [low] cli/wuwei/evidence.py:362 blocks: no. Carried from security-1088243 (CWE-223, omission of security-relevant information). A refused, never-attested FIX for a gate outside the missing set does not show at the door. Cases: one next to a counted PASS of the same gate (setup B1), or a refused FIX for a gate whose earlier pass carries over a delta (C3). On main e5b9416, #1190 already hides these lines whenever the owner excepts the gate gap. The backstops are the hand-back denial and the verdict.missing row.

## Probes
- Head 694ddd7 is a two-parent merge of 72b78c8 (the head I passed) and main e5b9416 (#1186, the 5.0.0 release, #1189, #1185, #1190). git diff 72b78c8 694ddd78 and git diff 17ff289 e5b9416 have the same added and removed lines (diff of the +/- lines is empty), 57 files, +1579 -143. The merge brought in main and nothing else.
- The PR diff at the new head (git diff e5b9416 694ddd78) has 19 files, +401 -128. Its +/- lines match git diff 17ff289 72b78c8 exactly, apart from two blank lines that moved in tests/test_charters.py. That is the builder's conflict resolution: the PR's test_the_gate_charter_shows_finding_lines... sits before main's #1186 test_the_planner_keeps_gates_off_codex..., and both are kept whole. cli/wuwei/evidence.py and .claude/wuwei/cli/wuwei/evidence.py are byte-identical (cmp).
- How the change composes with #1190 (read in evidence.py at the head): uncounted() is called only after a gate gap, at lines 336 and 344. The PR narrows the lines to the gates named in that gap. A file whose Gate: is not one of the four gates still shows. excepted() at line 501 drops every "verdict ... not counted" line once an approved exception removes the gate gap. So if the gap stays, main and head both deny. If the gap is excepted, both drop every not-counted line. The head's set of lines is always a subset of main's, and the PR cannot move a door verdict on top of #1190. board.py:101 still calls uncounted with the default (all four gates), same as at 72b78c8. The create door (guards.py:293-294) gets excepted only through the ready door's PR reference.
- Route differential (my script probe/route_diff_sec.py, runtime at main e5b9416 vs runtime at head 694ddd7, both with the head's test helpers): routes.json sha256 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49 at both, 263 routes, 19 setups, each with an approved owner exception on o/r#5. 0 verdict moves in all 19 setups. The reason moves only remove lines, and no line is added. A1, A3, A4, A5, A8, A10, B4 and C1 have 35 each, B1 and C3 have 32, and C2 has 3. In each case the dropped line is the not-counted line of a gate outside the gap. Two examples: gh pr create in B1 drops the security-<h7>-2.md line, and gh pr ready on other/x#7 in C2 drops the security line while the gap names quality. A0, A2, A6, A7, A9, B2, B3 and C0 have 0 and 0.
- Compared with the 72b78c8 run: the 22 merge-to-pass verdict moves are gone because main e5b9416 (#1190) now passes those routes itself. Main 17ff289 to e5b9416 moves the same 22 merge routes to pass in 16 setups. B2 (security missing, only quality excepted) stays denied at main and head.
- The PR's own specs/verdict-shape-examples/route_diff.py (main e5b9416 tree vs head tree, sha 4f6e25d0): none 0/0, arch-bad 0 verdict and 35 reason moves, quality-bad 0/0, both 0 and 35. This matches the builder's report.
- Full suite in a git archive copy of the head (uvx --python 3.13 --from pytest pytest -q, offline gh stub on PATH, CLAUDE_CODE_SESSION_ID unset): 2830 passed, 4 failed, 1 skipped. The 4 failures are the known local bash 3.2 ones: test_codex hook shell and three test_bash_runs_the_push_in_each_refused_shape cases.
- bin/wuwei agents check at the head: agents match the charters. cli/wuwei/*.py totals 3346 lines.
- CI at 694ddd7 (gh pr view once): 8 of 8 checks COMPLETED SUCCESS (test 3.11, 3.12, 3.13, CodeQL, Analyze actions and python, ZIRAN, ziran-audit). mergeStateStatus is CLEAN and the PR is still a draft.
- No dependency, lockfile or workflow file is in the PR diff.
- Confidence is high for three reasons. The PR's own lines are unchanged. The merge needed one test-file resolution only. Both differentials show 0 verdict moves against main e5b9416, and in every setup the reason moves only drop lines.

## Residual risk
Same as at 1088243: a refused FIX for a gate that already passed is silent at the door. Since #1190, main hides it too whenever the gate gap is excepted. Protection relies on the hand-back denial making the seat rewrite the file.
