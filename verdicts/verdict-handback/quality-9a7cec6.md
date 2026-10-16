Verdict: PASS
Gate: quality
Item: verdict-handback
PR: taoq-ai/wuwei
Head: 9a7cec600c3e89192b872d23b8714a26d654504b
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:32 blocks: no. Mutant: not resetting `ended` when a later plain text part follows a hand-back survives. A run cannot continue after SubagentHandback, so no bad input reaches it; a test with text after the hand-back would pin it.
- [low] tests/test_hook.py:331 blocks: no. Acceptance 3 is tested with a transcript holding only the hand-back; the stop_hook_active branch of the same condition is covered by existing tests.

## Probes
Suite at the head in a scratch checkout: 403 passed. Runtime lines 2997 (cap 3,000). `bin/wuwei agents check`: agents match the charters. `diff -r cli/wuwei .claude/wuwei/cli/wuwei` differs only by __pycache__; charters identical; the vendored-plugin test fails under each mutant, so it guards the copy.
Mutants, with the test that failed: removing the hand-back lint, test_a_malformed_verdict_denies_the_handback_with_its_shape_errors; dropping the sentinel role check, test_only_the_gates_own_seat_attests_at_the_handback[builder] and [empty]; `ended` always false and removing `or ended` in subagent_stop, test_a_problem_found_after_the_handback_ended_the_run_is_recorded; making file:line mandatory again and dropping the file check from the blocking rule, test_a_note_needs_no_file_line_but_a_blocking_finding_does. One mutant survived (the note above).
Acceptance: scenarios 1 to 5 each map to a test (deny with shape errors and FORMAT; one attest across PreToolUse and SubagentStop; verdict.missing after ended; note accepted and blocking finding without file:line rejected; size at 2997).
The old post_tool hand-back test was replaced by the pre_tool tests; the post_tool re-read is removed as the plan says.
Confidence is medium: I did not run the real harness hook, only the unit paths and the transcript shape the tests build.
Simplicity: none. The `ended` flag adds one return value to transcript() and replaces 7 deleted post_tool lines; no new abstraction.

## Residual risk
The `ended` detection relies on the transcript's tool_use name being exactly SubagentHandback; a harness rename would fall back to the old block-after-end behavior without a test failing.
