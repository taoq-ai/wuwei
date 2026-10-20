Verdict: PASS
Gate: quality
Item: 1180
PR: taoq-ai/wuwei#1189
Head: 9bb6c7d4998ef224449f57aac0f24e0958e02369
Confidence: medium
Breaking: no
Supersedes: none

## Findings
- [low] cli/wuwei/board.py:108 blocks: no. The owed-gates line reads "green" as "no gap starting `CI ` or `required check`". A head whose only unsettled or red check is a review-triggered workflow status shows as `waiting on review:` or `change request outstanding:` (evidence.ci_gaps), which neither prefix matches. The gate line can show on such a head while CI is not green. The harm is a false duty nudge, never a merge hold. No test covers it.
- [low] cli/wuwei/board.py:58 blocks: no. `running` reads only today's rows (ws.today()), as hook.running did. A seat of this session started before midnight and still running no longer counts after midnight. Existing limit, not new.
- [low] blocks: no. The plan promise says "Out of scope: hook.py (hook.running stays)", but the head edits Stop in hook.py and deletes hook.running. specs/orchestration-gap/spec.md:78-89 records why (the brief put the Stop guard in scope; #1172 left hook.running no caller). The Stop acceptance in the brief is met. Process fit only.
- [low] blocks: no. Acceptance 5 ("the merge door reads any PR, nothing new holds the merge") is tested at evidence.gap/blocking/visible (test_a_team_line_is_a_duty_that_never_holds_a_merge), not through the merge door on a PR. The team row has no PR and DUTY is the only classifier, and the mutant that removes `orchestration:` from DUTY is killed, so the coverage holds. Acceptance 6 (charter and skill text) is docs and has no test, which is exempt.

## Probes
- Head confirmed at 9bb6c7d4 (gh pr view: headRefOid, MERGEABLE); CI at the head: 8 of 8 checks SUCCESS (test 3.11/3.12/3.13, CodeQL, Analyze python and actions, ZIRAN, ziran-audit). The PR is a draft.
- Full suite in a git archive copy at the head (uvx python 3.13, offline gh stub): 2746 passed, 1 skipped, 4 failed, both with and without CLAUDE_CODE_SESSION_ID in the environment. The 4 failures are the known main-only macOS bash 3.2 ones (test_hook_commands_run_under_either_harness_shell and 3 test_bash_runs_the_push_in_each_refused_shape cases).
- PR mutants (specs/orchestration-gap/mutants.py, applied to cli/wuwei and .claude/wuwei/cli/wuwei alike, one at a time, board, hook and status-perf tests): 16 of 16 killed, each by a behavioural test failure (1 to 8 failures; no syntax or collection error).
- My own mutants on board.py, both copies, board, hook, status-perf and codex tests: owed over all PRs (any to all) killed; distinct-PR count to row count killed; drop the string-agent check on seat.started killed (2 failures); `sentinel-` prefix loosened to `sentinel` killed; any seat clears the gate line killed (3 failures); any seat clears the shepherd line killed. 6 of 6 killed, 0 survived.
- Acceptance map: (1) test_open_prs_and_owed_gates_with_no_seat_running_show_one_team_row; (2) same test plus test_owed_gates_on_a_head_whose_ci_runs_or_fails_owe_no_gate_seat and ..._missing_a_required_check_...; (3) test_a_running_seat_in_this_session_clears_its_line and test_two_open_prs_need_no_shepherd_line; (4) test_the_same_orchestration_state_reminds_once_while_the_pr_count_moves (a Stop with the PR count moving 4 to 3 adds no reminder); dead session: test_a_seat_another_session_left_running_never_silences_the_stop, test_a_dead_stopped_or_unconfirmed_seat_never_counts_as_running; (5) the DUTY test above.
- hook.running: removed from both copies. grep for `hook.running` and `.running(` across cli, tests, .claude, docs and skills finds no live caller; the only mentions are historic specs and this item's own spec. Its former tests (test_hook.py, test_codex.py) now call board.running(root, 's1') and are not dead: the unconfirmed, no-string-agent and by-agent-id tests all kill a board.running mutant.
- Main-versus-head route differential (specs/orchestration-gap/route_diff.py, 8a92be70 against the head, CLAUDE_CODE_SESSION_ID unset, corpus sha256 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49 on both): 263 routes, 544 cases, 5 moved. guards 263 cases and bash 263 cases moved 0; payload 10 moved 0. Moved rows: session start with 40 items (team row added), and Stop "no seat" (team line added), "builder stopped in this session" (team line added), "seat a dead session left running" (null at main, block at head: the intended change), "seat this session left unconfirmed" (team line added). No refusal or PR-naming route moved.
- Copies: cli/wuwei and .claude/wuwei/cli/wuwei are identical; charters/planner.md equals its .claude copy; skills/wuwei-run/SKILL.md equals its .claude copy. Runtime lines 3321 at main, 3326 at the head (+5 net, item budget 12, cap 3400).
- Session id: this environment's CLAUDE_CODE_SESSION_ID equals the id the hook payloads carry (the scratchpad path and the ledger seat rows use the same uuid form), so the status path and the Stop path read one id. A harness that does not set it shows both lines with seats running (spec "How this fails" 1): a false nudge only.
- Test quality: no wall-clock or ordering dependence except the monkeypatched ws.now in one test; assertions are on the duty lines (decision records), not free prose. Not run: parallel-load flake check beyond the one suite pass.
- Confidence reason: medium, because every changed guard has a killing test and the differential is clean, but the 60-second board cache can carry another session's team row into a Stop (spec "How this fails" 2), and I did not probe that across two live sessions.
- Simplicity: none deletable. The `[line] * bool` idiom matches the repository's own `left()` in hook.py; `running` replaces hook.running rather than adding a second helper. The two-copy duplication is the repository's vendoring rule.

## Residual risk
The gate line's "green" is the absence of `CI ` and `required check` gaps, so a head with only a pending review-triggered status can show a false gate nudge. A cached board can carry one session's team row to another for up to the board TTL.
