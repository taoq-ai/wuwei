Verdict: PASS
Gate: security
Item: seat-count
PR: taoq-ai/wuwei
Head: 7cddff31c12e1fbbb4ad17a61f3cdda1f1ebd465
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:195 blocks: no. Every launch whose tool_response has no usable agentId (missing, a string response, None) is stored as agent None. Those seats merge into one set entry, and one SubagentStop without an agent_id removes all of them. A foreground launch with no agentId stays "running" for the rest of the day, so the Stop hook stays quiet. tool_response and agent_id come from the harness, not from the session, so this is a fidelity limit, not a trust-boundary defect. Nobody has checked whether a live Claude Code foreground Agent response carries agentId.
- [low] cli/wuwei/hook.py:55 blocks: no. If a seat.started or seat.stopped row has an unhashable agent (for example a list, from a harness that sends agentId as a list or from a planted ledger row), running() raises TypeError. handle() then fails open, so the Stop hook stays quiet for the whole day and records hook.error. Before this change, len() could not raise here. Wrapping the id in str() at record time and filtering out None would close this and the note above.
- [low] cli/wuwei/hook.py:191 blocks: no. Two mutants survive the suite. Replacing the tool check with `if True` makes every PostToolUse record a seat with agent None, which pins running() at 1 or more and silences Stop. Dropping the isinstance(response, dict) guard turns a string response into an AttributeError, so the seat is not recorded. Missing tests: a non-Agent PostToolUse records no seat, and a string Agent tool_response is handled.
- [low] cli/wuwei/hook.py:332 blocks: no. The Codex regex picks the first `"agent_id": "..."` anywhere in the response after removing one level of escaping. A response that quotes that text earlier (inside a message field) gives a wrong id, and a string escaped twice gives None. The captured id has no length cap. Nobody has checked whether Codex's SubagentStop agent_id matches the spawn_agent agent_id. If it does not, Codex seats never close, which already happened under row counting before this change.

## Probes
- Checked out a copy of 7cddff3 into the scratch directory. The full suite passed with /root/.local/bin/pytest -q (452 passed).
- Ran setup.vendor() into an empty directory and compared it with `diff -r` against the .claude/wuwei of the copy: identical. `cmp` of the two hook.py files at the head also matched.
- PreToolUse Agent/Task: the removed block only recorded seat.started. guards.pre_tool and the sentinel handback check still run unchanged. guards.py and ws.py have no read of seat.* rows (git grep), so no door path depended on the record. Probe: PreToolUse Agent returns None and writes no row.
- Shaped tool_response with probe.py. Two missing agentIds: running 1. String or None response: 1 (agent None). Two colliding 'a1' ids: 1. Integer id: 1. List id: running() raises TypeError and Stop returns None with hook.error. Two id-less seats plus one id-less stop: 0. Foreground stop before PostToolUse with the same id: 0. Foreground with no agentId: 1.
- Codex shapes. dict and JSON string give c1. A string escaped twice gives None. A non-string id gives None. A quoted echo before the real field still gave c2 in my shape.
- None of the outcomes is reachable from session-controlled text alone. tool_response and agent_id are set by the harness, so the session cannot shape running() without the ledger write the guards already deny.
- Mutants (tests/test_hook.py, tests/test_codex.py). Row counting restored: killed by test_running_counts_seats_by_agent_id_not_rows. Codex id dropped: killed by test_a_spawned_codex_agent_is_a_running_seat. Tool check replaced with `if True`: SURVIVED. isinstance guard removed: SURVIVED.
- Confidence is medium because the live harness response shapes (a foreground Agent's agentId, Codex SubagentStop ids) were not observed.

## Residual risk
running() now depends on the harness supplying matching ids at launch and at stop. A missing or odd id either pins Stop quiet for the day or merges seats, and nothing reports it except the ledger rows.
