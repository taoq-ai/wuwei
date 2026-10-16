Verdict: PASS
Gate: arch
Item: seat-count
PR: taoq-ai/wuwei
Head: 4dd32a6b837fa90dbea546e01a57f6094ec81b27
Confidence: medium
Breaking: no

## Findings
- [low] specs/seat-count/spec.md:52 blocks: no. The second assumption says a Codex response without `"agent_id"` makes the seat "record with no agent". FR-004, the third assumption and the code (hook.py:193 needs a non-empty str agentId) all say no seat is recorded. Fix the wording so the spec does not contradict itself.
- [low] cli/wuwei/hook.py:333 blocks: no. Codex seats are now counted only if Codex fires PostToolUse for spawn_agent with a response that holds `agent_id`, and only if Codex SubagentStop carries the same id. Neither has been checked against a live Codex payload. If either is false, a Codex seat is not counted, so Stop reminds the session during a live seat; it is never silenced. The spec records this as an assumption.
- [low] blocks: no. On the day of upgrade, a seat started before the upgrade has a legacy start row with no agent id. running() ignores that row, so Stop may remind the session once while that seat still runs (the per-session cache dedupes it). This is transient and errs toward a reminder, and the spec's fourth assumption records it.

## Probes
- Readers of the rows, found with `git grep -n -E "seat\.(started|stopped)|running\(" 4dd32a6 -- cli docs charters`. hook.running is the only reader of seat.started, and its only caller is hook.stop (hook.py:85). report.py:62 and :128 read only seat.stopped, whose writer is unchanged. setup.py:52 (doctor HOOK_ROWS) checks only that a kind is present; seat.started is still written. board.py reads neither row. docs/design.md and docs/site/concepts/hooks.md never said PreToolUse records seats, so no doc drift.
- Callers of codex(): its only caller is hook.handle (hook.py:348), for every event. On PreToolUse, spawn_agent now also carries tool_response {'agentId': None}. guards.py never reads tool_response (git grep). probe.py confirmed that PreToolUse handle returns None with no seat row and no hook.error.
- Hook wiring: .claude/settings.json and hooks/hooks.json register PostToolUse with no matcher, so Agent and Task reach post_tool.
- probe.py on a copy of the tree at 4dd32a6. A legacy start with no agent gives 0. Adding a legacy stop with an agent gives 0, and a stop with agent None gives 0. A foreground stop before PostToolUse gives 0. Codex dict, nested dict and JSON-string responses all yield the id.
- Ran the full suite in the copy with /root/.local/bin/pytest -q: 462 passed. `cat cli/wuwei/*.py | wc -l` gives 2999 of 3000, and the size test is tests/test_setup.py:53.
- `diff` of cli/wuwei/hook.py against .claude/wuwei/cli/wuwei/hook.py at the head: identical.
- Two mutants. With the Agent/Task tool check forced true, test_only_an_agent_launch_with_a_string_id_records_a_seat[Bash-response4] fails. With the stopped ids no longer subtracted, test_running_counts_seats_by_agent_id_not_rows fails.
- Breaking: the change touches no CLI, flag, exit code, config key or file format. seat.started gains an `agent` field and is written later, and no reader outside running() consumes it. Confidence is medium because live harness payload shapes (the Claude foreground agentId, Codex PostToolUse) were not observed.

## Residual risk
Correctness depends on the harness's launch agentId matching the agent_id in SubagentStop. A mismatch keeps the Stop hook quiet for the rest of that day.
