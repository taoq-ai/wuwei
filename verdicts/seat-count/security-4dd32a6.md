Verdict: PASS
Gate: security
Item: seat-count
PR: taoq-ai/wuwei
Head: 4dd32a6b837fa90dbea546e01a57f6094ec81b27
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:193 blocks: no. A launch whose response has no non-empty str agentId is no longer counted at all. While such a seat runs, the Stop hook can remind the session about open work. That errs toward more reminders, never toward a quiet Stop. agentId comes from the harness, and nobody has checked against a live Claude Code foreground Agent response that it always carries a str agentId.
- [low] cli/wuwei/hook.py:54 blocks: no. If a seat row's data is not a dict, running() still raises AttributeError and Stop fails open quiet. That needs a planted ledger row, which the guards deny. This was already true at 7cddff3.
- [low] cli/wuwei/hook.py:333 blocks: no. Carried over from 7cddff3, outside this delta: the Codex regex takes the first `"agent_id"` match, has no length cap, and nobody has checked that Codex SubagentStop ids match spawn_agent ids.

## Probes
- Copied 4dd32a6 into scratch tree2. The full suite passed with /root/.local/bin/pytest -q (462 passed).
- Ran setup.vendor() into an empty directory and compared with `diff -r` against tree2/.claude/wuwei: identical. `cmp` of the two hook.py files at the head also matched.
- Read the delta with git diff 7cddff3..4dd32a6 -- cli tests. pre_tool is unchanged, so the door-path conclusion from 7cddff3 stands.
- probe.py at the head. Missing, string, None, list, int or empty agentId (Claude) give no row and running 0. Codex non-str, missing, None or double-escaped ids give no row and running 0. Codex dict or JSON string gives c1 and running 1. Colliding 'a1' gives running 1. Foreground stop before PostToolUse gives 0. A planted list agent gives running 0 and Stop records no hook.error. PreToolUse Agent returns None and writes no row.
- Undercount check: started ids are only strs, and set difference removes only equal elements. A non-str stopped id (None, a list, the int 7) can never equal a started str, so the str filter on stopped rows cannot change running(). It cannot undercount a real seat.
- mutate2.py, 7 mutants, all killed. Tool check made always true: killed by test_only_an_agent_launch_with_a_string_id_records_a_seat[Bash]. Dict check removed: killed by test_post_tool_tells_what_a_new_pr_still_needs and others. Str check removed: killed by [Agent-response0/1]. Empty check removed: killed by [Task-response2]. Str filter in running removed: killed by test_running_skips_rows_without_a_string_agent_id. Stops ignored: killed by test_running_counts_seats_by_agent_id_not_rows. Codex id dropped: killed by test_a_spawned_codex_agent_is_a_running_seat.
- My 7cddff3 notes 1-3 are closed by this delta. Confidence is medium because the live harness response shapes were not observed.

## Residual risk
running() trusts the harness ids at launch and at stop. A harness that leaves out agentId makes Stop remind the session during a live seat rather than go silent.
