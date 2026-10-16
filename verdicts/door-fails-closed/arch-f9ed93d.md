Verdict: PASS
Gate: arch
Item: door-fails-closed
PR: taoq-ai/wuwei
Head: f9ed93dae01a13b440b6c36f8375cd74e81b82fb
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/hook.py:372 blocks: no. Two lists that can drift: door() reuses guards.DOOR_WORDS for Bash, which is good, but it copies the edit-tool tuple (Write, Edit, MultiEdit, NotebookEdit) and the MCP door suffixes (merge_pull_request, enable_pr_auto_merge, create_pull_request) from guards.pre_tool (guards.py:272, 297, 302) as literals. Today the two sets match. If someone adds a door tool to guards.pre_tool later and not to door(), that tool fails open on a hook error. The spec says "no parallel list is added", and that is true only for Bash. Follow-up: give guards named constants (EDITS, MCP_DOORS) and use them in both places.
- [low] cli/wuwei/hook.py:25 blocks: no. Because there is now one reader, every row's message is read for usage, so a non-assistant row whose message is not a dict now stops last_text early. Probe: transcript rows [assistant 'early', {'type':'progress','message':'a string'}, assistant 'Verdict file: x'] give ('early', 2). On main, last_text returned 'Verdict file: x'. I know of no harness transcript with this shape, and last_assistant_message comes first anyway. The spec's Clarifications record the malformed-row trade.
- [low] cli/wuwei/hook.py:362 blocks: no. The promise lists the doors. Other guard paths keep failing open on an error: the leak check on other mcp__ tools and on network Bash programs outside DOOR_WORDS (curl, wget), the terraform/kubectl ask, and the AskUserQuestion send-back. This matches the promise. It is still a limit worth a review note.
- [low] cli/wuwei/hook.py:372 blocks: no. Operational change: a hook error that persists in PreToolUse (for example a broken guard or workspace read on every call) now refuses every Write, Edit, git push and gh pr/api/repo call until the operator fixes the workspace. Before, those calls went through. This is the trade the owner chose (spec "How this fails" 1), and the deny names the error.

## Probes
- Diff origin/main...f9ed93d --stat: hook.py (both the source and the .claude vendored copy, which are identical according to diff), test_hook.py, design.md, specs/door-fails-closed/*.
- Callers: git grep at the head finds no caller of the removed tokens() in cli, .claude/wuwei/cli or tests. last_text callers at hook.py:115, 121, 129, 149 keep the same signature and semantics. transcript()[1] replaces tokens() in subagent_stop.
- Door set compared with guards.pre_tool: Bash uses the shared guards.DOOR_WORDS. The edit and MCP door names are copied literals that match guards.py:272/297/302. Codex apply_patch is mapped to Edit by codex() before handle, so it is covered.
- The contract matches the constitution (.specify/memory/constitution.md:22) and the old design.md, which already said "a door that cannot read its evidence stays shut". The change brings the code in line with that published rule. deny is an existing permissionDecision value. No CLI flag, exit code, config key or ledger kind changes; main() still returns 0. So Breaking: no.
- Suite in a scratch copy (pytest from the uv tool): 397 passed.
- Mutants (scratch copy), each killed. Removing the door deny in handle: test_a_merge_door_... and test_an_error_inside_a_door_refuses_the_call[*] fail. Narrowing the record guard in pre_tool to KeyError: test_a_refusal_reaches_the_harness_when_its_record_fails[*] fails. Dropping Edit from the door set: [Edit] fails. Dropping create_pull_request: [mcp__..create_pull_request] fails. Deny on any event: test_an_error_after_a_door_call_ran_still_fails_open fails. Disabling the token sum: test_seat_tokens_are_counted_from_the_transcript fails.
- Confidence is high: the change is small, every new guard has a killing test, and it matches the written rule. A harness transcript with non-dict message rows would lower it.

## Residual risk
door() and guards.pre_tool hold copied tool-name lists that can drift. An error raised before handle (stdin parse, ws.find) still fails open on a door call, which is outside this item.
