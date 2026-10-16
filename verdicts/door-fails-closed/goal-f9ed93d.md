Verdict: PASS
Gate: goal
Item: door-fails-closed
PR: taoq-ai/wuwei
Head: f9ed93dae01a13b440b6c36f8375cd74e81b82fb
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:27 blocks: no. Merging the two transcript readers changes one case. A row that parses as JSON but has a malformed content part (for example a string in content) now also stops the token sum, so seat.stopped tokens undercounts the rows after it (probe: 13 against 20 on main). A row that is not JSON already stopped both readers on main, so the builder's assumption mostly restates existing behaviour. Tokens is a telemetry field and no door depends on it, so this fits G-2.
- [low] cli/wuwei/hook.py:374 blocks: no. The promise names guards.DOORS, but the code uses guards.DOOR_WORDS, the only such tuple in guards.py (guards.py:21, the one #1068 uses at guards.py:229). It is the same set under its real name, so this is not drift.
- [low] cli/wuwei/hook.py:368 blocks: no. Counting MultiEdit and NotebookEdit as edits matches guards.py:272, which guards all four edit tools the same way. Leaving two of them failing open would leave a gap the promise is meant to close, so the assumption fits the goal.
- [low] cli/wuwei/hook.py:371 blocks: no. When tool_input is not a dict, a Bash door command fails open (a test pins this). The harness always sends a dict and the agent does not control its shape, so this is a limit, not a hole.
- [low] cli/wuwei/hook.py:19 blocks: no. Runtime lines went from 2996 on main to exactly 3000 at head. The promise estimated a net saving, but the change adds 4 lines. Acceptance 4 still passes, with no headroom left for the next item.

## Probes
Acceptance 1, end to end: ran the real entry point bin/wuwei hook PreToolUse from a scratch clone at f9ed93d. The workspace was a scratch git repo (origin taoq-ai/wuwei) with .wuwei/cache/template-taoq-ai__wuwei.json as a directory and the payload Bash "gh pr merge 1080", using real gh REST reads. At head the hook printed permissionDecision deny with a reason naming IsADirectoryError, and the ledger got a hook.error row. On main (f42f58b) the same run printed nothing, so it failed open, with the same hook.error row.
Acceptance 2: a guard-refused Write to the ledger, with a truncated last ledger line, ran end to end and was denied at both head and main. ws.record tolerated that line, so this did not reproduce the raise end to end. The raise is covered by test_a_refusal_reaches_the_harness_when_its_record_fails (OSError and ValueError over deny, deny and ask).
Acceptance 3: covered by test_an_error_outside_the_doors_fails_open (ls, Read, an MCP read and Agent all return None and record hook.error).
Acceptance 4: test_setup size test passes; cat cli/wuwei/*.py | wc -l gives 3000.
Suite: 397 passed at head (pytest in a scratch venv). The vendored .claude/wuwei/cli/wuwei/hook.py is byte-identical to cli/wuwei/hook.py.
Mutants on test_hook.py: narrowing the pre_tool record except gives 4 failed; disabling the door deny in handle gives 10 failed; dropping the edit tools from door() gives 2 failed.
Explain-back: the spec's assumptions and design.md wording match the promise. Outside scope: cache_put is left alone, and the deny names the cause.
Confidence is high: acceptance 1 was reproduced through the real hook and compared against main, and every guard change is killed by a test.

## Residual risk
The door classifier lists doors separately from guards.pre_tool. A door added to guards later will fail open on error until door() learns it. The runtime line budget is now at its limit.
