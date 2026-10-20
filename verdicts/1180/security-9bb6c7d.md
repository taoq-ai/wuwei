Verdict: PASS
Gate: security
Item: 1180
PR: taoq-ai/wuwei#1189
Head: 9bb6c7d4998ef224449f57aac0f24e0958e02369
Confidence: high

## Findings
- [low] cli/wuwei/board.py:107 blocks: no. `wuwei status` reads the session from CLAUDE_CODE_SESSION_ID, which the calling shell controls (`CLAUDE_CODE_SESSION_ID=<other> wuwei status` passes the guards at main and head). That only changes what the caller's own status output shows: status computes fresh and writes no `board` cache, and the Stop and session start read the harness payload and the hook's own environment. CWE-807 class, but it feeds a nudge, not a decision.
- [low] cli/wuwei/board.py:107 blocks: no. The `board` cache (60 s) is shared by every session in the workspace, so one session's Stop or session start can show the team row another session computed. In practice that row was computed with no seat running in that session (the Stop guard runs first), so the lines lean toward showing. Duties only, never a hold.
- [low] cli/wuwei/evidence.py:52 blocks: no. Any gap text that starts with `orchestration:` is now a duty. The only variable-start text that can begin that way is the board-only `{repo} unreadable: ...`, for a plan item whose repo field starts with `orchestration:`. That gap is already `[waiting]` and has no PR, so no merge path reads it. No PR gap template can start that way (all 30 gap call sites enumerated).

## Probes
- Read once: `gh pr view 1189 --json headRefOid,statusCheckRollup` showed head 9bb6c7d and 8 checks SUCCESS: Tests 3.11/3.12/3.13, CodeQL Analyze (python), Analyze (actions), CodeQL, ziran-audit, ZIRAN. `git ls-remote` before writing showed the head unchanged. `wuwei evidence taoq-ai/wuwei#1189` listed the gates missing at 9bb6c7d and owner review [waiting].
- Scanners: CodeQL (static analysis) and ZIRAN (agent role-grant audit) passed in CI at the head. The repository has no secret scanner, so secrets are unmeasured. A manual grep of the added lines found no token patterns, private keys, emails or machine paths. No workflow, pyproject, lockfile, hooks/ or bin/ change, so the supply chain is unchanged. agents/ is unchanged, and the charter and skill text grant no new tool.
- Route differential (my own script, scratch sentinel-security-1180/scripts/diff.py), main 8a92be7 vs head, corpus tests/fixtures/routes.json sha256 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49, 263 routes, 745 cases, 162 moved. Results by surface:
  - guards.bash (263), PreToolUse Bash through hook.handle (263) and fixture payloads (10): 0 moved.
  - Merge door (guards.merge_door plus gap kinds for PRs 5, 7 and 9, with the team row in the board cache; 9 seat states x 4 env session values = 36 cases): 0 moved.
  - SessionStart 40 items: moved (team row appended). SessionStart 0 items: unchanged.
  - status (36): 35 moved. Main has no team row. The lines clear only when the env names the session holding the shepherd and sentinel seats.
  - Stop (135 cases: 9 seat states x 5 payload sessions (s1, missing, empty, null, other) x 3 env values, two Stops each): 126 moved. None moved from block to silent. 66 moved from silent to a reminder: a seat from a dead or other session, seats recorded with no or empty session, and a payload session that is missing, empty, null or not the seat's. 60 kept blocking and gained the team lines. The second Stop was silent in every case at both trees. A seat running in the payload's own session stayed silent at both (the known-positive case).
- Forged session paths: hand-running the hook (`printf ... | bin/wuwei hook Stop` and `CLAUDE_CODE_SESSION_ID=gone bin/wuwei hook Stop < p.json`) is denied at main and head. Writes to .wuwei/cache/board.json, .wuwei/cache/stop-s1.json and .wuwei/ledger/ are denied at both. seat.started takes its session from the harness payload (hook.py:262, and Codex spawn_agent through codex()), never from tool_input. A missing payload session gives the empty set, so the reminder shows (fail closed).
- Duty classification differential, evidence.gap kind at main vs head over 22 texts (case, whitespace, newline, BOM, fullwidth colon, U+2028, wrapped prefixes): 3 moved. Two are the team lines themselves (`orchestration: x`, `orchestration:x`); the third is the board-only repo case in Findings.
- Mutants (scratch scripts/mutants.py): each in a fresh `git archive` copy, applied to cli/wuwei and .claude/wuwei/cli/wuwei, run one at a time. 10 of 10 killed by behavioural tests:
  - session-less seats count: test_a_dead_stopped_or_unconfirmed_seat_never_counts_as_running
  - any session counts: test_a_seat_another_session_left_running_never_silences_the_stop
  - stopped seats count: test_running_counts_seats_by_agent_id_not_rows
  - unconfirmed seats count: test_an_unconfirmed_seat_no_longer_counts_as_running
  - yesterday's seats count: test_a_dead_stopped_or_unconfirmed_seat_never_counts_as_running
  - non-string agent counts: test_running_skips_rows_without_a_string_agent_id
  - Stop never silenced: test_stop_stays_quiet_while_a_seat_is_running
  - Stop silenced by any session's seat: test_a_seat_another_session_left_running_never_silences_the_stop
  - orchestration line becomes a safety gap: test_a_team_line_is_a_duty_that_never_holds_a_merge
  - status ignores the env session: test_a_running_seat_in_this_session_clears_its_line
- Full suite (`uvx --python 3.13 --from pytest pytest -q`, offline gh stub on PATH): head 4 failed, 2746 passed; main 4 failed, 2737 passed. The same 4 bash-3.2 tests fail at both (test_the_hook_commands_run_under_either_harness_shell and three test_bash_runs_the_push_in_each_refused_shape cases).
- hook.running has no caller left in cli, tests, bin, hooks, skills, charters or docs. The vendored .claude copy of cli/ is byte-identical to cli/.
- Confidence high because every surface the brief named was exercised at main and head with a known positive and negative, and none moved toward silence or a merge pass. One thing is unmeasured: whether a Claude Code hook process carries CLAUDE_CODE_SESSION_ID. Without it the lines show while seats run, which is a false nudge, never a hold.

## Residual risk
The Stop guard's fail-closed behaviour depends on the harness putting session_id on both PostToolUse and Stop payloads. A harness that drops it gets more reminders, never fewer.
