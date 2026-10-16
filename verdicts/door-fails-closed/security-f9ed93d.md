Verdict: PASS
Gate: security
Item: door-fails-closed
PR: taoq-ai/wuwei
Head: f9ed93dae01a13b440b6c36f8375cd74e81b82fb
Confidence: medium

## Findings
- [medium] cli/wuwei/hook.py:374 blocks: no. door() matches DOOR_WORDS against the raw command, but the guard normalizes quotes with shlex first. So a quote-split spelling the guard does treat as a door (g''it push origin main, a gh command with "p"r merge 5) is still let through when the guard raises. Probe: with guards.pre_tool raising, all four spellings returned PASS, and segments() parses them to ['git','push',...] and ['gh','pr','merge','5']. To exploit this an agent must first cause the error itself (for example mkdir .wuwei/cache/default-<repo>.json, then the obfuscated push). This blocks: no for three reasons: the promise defines a door as a DOOR_WORDS match, the guards are a mistake-catcher rather than an adversary boundary (bash script.sh or python3 -c subprocess bypass them without any error), and branch protection holds pushes to the default branch. Suggested follow-up: also treat a call as a door when guards.segments(command) yields argv starting git push, gh pr/api/repo or wuwei hook.
- [low] cli/wuwei/hook.py:327 blocks: no. codex() runs before handle's try, so an apply_patch payload with a non-dict tool_input raises AttributeError out of handle (probed), the hook exits non-zero and the edit passes. This predates the item, and Codex sends a dict.
- [low] cli/wuwei/guards.py:244 blocks: no. Outside the item's scope: leak() on network Bash programs (curl, wget, ssh) and on other MCP tools (guards.py:305, including mcp__github__push_files) is a guard whose error still fails open. Probe: curl -d ghp_<36> with a guard error returned PASS. The egress check is skipped exactly when the hook is broken.
- [low] tests/test_hook.py:413 blocks: no. The test pins that a string tool_input fails open for a merge command. The harness never sends that shape, so there is no reachable input, but the test makes a non-dict door payload a pass by contract.
- [low] cli/wuwei/hook.py:357 blocks: no. In handle's except, print to stderr is unguarded. If it raises (a closed stderr), the door branch is never reached and the hook crashes open. Contrived.
- [low] cli/wuwei/hook.py:25 blocks: no. Not security, but a behavior change from merging the two readers: a malformed usage row (input_tokens null) now aborts the read, and last_text loses the report. Probe: old code returned 'Verdict file: x.md', new code returns ''. A sentinel's verdict line would then go unread on SubagentStop, which fails closed (the gate looks missing).
- [low] cli/wuwei/hook.py:374 blocks: no. Mutant any() for all() in door() survives. It is over-inclusive, so it only fails closed more often (equivalent for safety); no test pins it.

## Probes
- /root/.local/bin/pytest -q in a copy at f9ed93d: 397 passed.
- Vendor check: setup.vendor() into a scratch dir, then diff -r against .claude/wuwei, .claude/skills and .claude/agents at the head: identical.
- Mutants on hook.py, run with tests/test_hook.py: removing the record try is killed by test_a_refusal_reaches_the_harness_when_its_record_fails; removing the door branch is killed by test_a_merge_door_that_cannot_write_its_cache...; dropping the event check is killed by test_an_error_after_a_door_call_ran_still_fails_open; dropping Edit, MCP, create-PR or Bash from door() and making every call a door are each killed; any() for all() survives (equivalent, see the last finding).
- With guards.pre_tool raising: plain git push, the gh merge command, $GIT push, MultiEdit, NotebookEdit, mcp__plugin_github_github__merge_pull_request and codex apply_patch (mapped to Edit) all deny. Quote-split spellings, curl with a secret, mcp__github__push_files, a string tool_input and a None tool_input pass.
- Secret exposure: the deny reason is type plus str(exc), capped at 300 characters. The possible sources are paths (OSError), gh stderr last line (GhError, already shown in the create_door deny), KeyError names and JSON position messages. No path puts env tokens or Authorization headers into exception text (gh is a subprocess, and the token never sits in argv). The same text was already in the hook.error ledger row and on stderr.
- Availability: on Write/Edit, the only code before the decision is the LEDGER path regex in guards.pre_tool, and ws.record failures are now caught. A broken workspace therefore does not block ordinary writes; only a code bug in that small branch would. Accepted as the spec's stated trade (How this fails 1).
- Confidence is medium: the diff matches the promise and is well mutation-tested. The residual fail-open spellings are outside the promise's literal door definition.

## Residual risk
door() and the guard disagree on what names a door (raw regex vs shlex-normalized argv), and the egress leak checks still fail open on errors. A follow-up should derive door() from the parsed segments.
