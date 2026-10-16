Verdict: PASS
Gate: quality
Item: door-fails-closed
PR: taoq-ai/wuwei
Head: f9ed93dae01a13b440b6c36f8375cd74e81b82fb
Confidence: medium
Breaking: no

## Findings
- [low] tests/test_hook.py:392 blocks: no. The door tests never pass a non-door Bash command naming a door word (for example 'git status'); reversing door()'s all() to any() in cli/wuwei/hook.py survives. With the guard reversed, 'git status' plus a hook error would be refused instead of failing open. It errs toward refusal and only while the hook is already broken, so a note. Missing test: parametrize test_an_error_outside_the_doors_fails_open with ('Bash', {'command': 'git status'}).
- [low] tests/test_hook.py:392 blocks: no. The merged transcript() reader has no test for the rows its refactor changed: forcing the assistant-only filter on, dropping the tool_use message branch, and returning 0 instead of None for an unreadable transcript all survive test_hook.py and test_guards.py. They are caught only by the vendored-copy drift test, which compares the copy with the tree and does not check behaviour. Missing tests: a user-typed text row after the last assistant text is not the report, a tool_use input message is read as the report, and tokens is None for a missing file.
- [low] cli/wuwei/hook.py:67 blocks: no. The runtime is exactly 3000 lines (cat cli/wuwei/*.py | wc -l), so the size test passes with no room left. The next runtime line fails it.

## Probes
- Checked out the head with git archive into /tmp/claude-0/-home-user-wuwei/73620501-0677-5211-9719-0231fa72dba4/scratchpad/q-dfc/. The full suite gives 397 passed, none skipped or collected out. test_the_runtime_holds_its_size_budget passes at 3000 lines.
- Vendored copy: diff of cli/wuwei/hook.py against .claude/wuwei/cli/wuwei/hook.py is empty. Mutating only the tree copy makes test_the_vendored_plugin_matches_the_tree_it_was_copied_from fail, so the check is live.
- Acceptance 1 (cache path is a directory, deny names IsADirectoryError, hook.error recorded) is test_a_merge_door_that_cannot_write_its_cache_refuses_and_names_the_error. Acceptance 2 is test_a_refusal_reaches_the_harness_when_its_record_fails (OSError and ValueError, deny, ask). Acceptance 3 is test_an_error_outside_the_doors_fails_open with 'ls'. Acceptance 4 is the size test above. Extras: record failure inside a door, malformed tool_input, and PostToolUse fail-open.
- Mutants, pytest tests/test_hook.py tests/test_guards.py:
  - pre_tool's record guard narrowed to ZeroDivisionError: killed by test_a_refusal_reaches_the_harness_when_its_record_fails[error0-AskUserQuestion].
  - handle's deny branch replaced with `if False`: killed by test_a_merge_door_that_cannot_write_its_cache_refuses_and_names_the_error.
  - door() always true: killed by test_an_error_outside_the_doors_fails_open[Bash-data0]. door() always false: killed by test_an_error_inside_a_door_refuses_the_call[Write].
  - door() with Edit dropped, or Write only: killed by the Edit case.
  - door() with each MCP suffix removed (merge, auto-merge, create-PR): each killed by its own parametrized case.
  - door() with the Bash any() negated: killed by test_post_tool_tells_what_a_new_pr_still_needs, which is not a door test. The merge and push door cases did not catch it first.
  - door() with all() changed to any(): survived (finding 1). door() with the mcp__ prefix test removed: survived. The reversed prefix guard lets only a non-mcp tool named like 'x_merge_pull_request' through, which is not a real input, so it is equivalent for practical purposes.
  - transcript(): killed are dropping the input plus output token sum (test_seat_tokens_are_counted_from_the_transcript), dropping the text branch (test_a_report_written_just_after_the_stop_is_still_read), the running sum, and a narrowed except. last_text always reading the transcript is killed by test_a_malformed_verdict_is_sent_back_with_the_format. The assistant filter, tool_use branch and None-versus-0 default survived (finding 2).
- Simplicity: door()'s `any(all(re.search(w, command) for w in words) for words in guards.DOOR_WORDS)` repeats guards.py:229, so a small guards helper could replace both and free about a line. Nothing else is deletable. The try/except around the record, the door deny and the fail-open default are fail-closed handling and stay. The transcript() walrus condition with a repeated row.get('message', {}) is dense; binding message once would read better at no line cost.
- Confidence is medium: the behaviour tests are real and kill the guard mutants, but the transcript refactor's behaviour is held mainly by the vendoring drift test.

## Residual risk
The door-fails-closed behaviour is well covered. The merged transcript() reader still depends on older tests for row-level behaviour, and the runtime sits exactly at its 3000-line cap.
