Verdict: PASS
Gate: security
Item: verdict-handback
PR: taoq-ai/wuwei
Head: 9a7cec600c3e89192b872d23b8714a26d654504b
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:59 blocks: no. The role comes only from the harness's top-level agent_type, never tool_input (correct), but no suite test pins it: a mutant that reads tool_input['agent_type'] first passes all 403 tests. My scratch probe test_no_attest_from_wrong_seat kills it; worth adding to tests/test_hook.py.
- [low] cli/wuwei/hook.py:32 blocks: no. ended is set by the tool name; a mutant setting it True for any message-carrying tool_use survives the suite. Harm is only that a seat whose last part is some other tool's message gets verdict.missing recorded instead of a block. That fails closed: nothing is attested.
- [low] cli/wuwei/hook.py:198 blocks: no. With the post_tool re-read gone, a seat that ends in plain text (hand-back refused) still relies on the stop reading its message. If that read races (#1039 part 2), the result is block, then verdict.missing, then uncounted. The gate is missing, not forged. The hand-back path itself closes the race because it reads tool_input directly.
- [low] cli/wuwei/hook.py:65 blocks: no. The attest is recorded at PreToolUse even when a later permission check refuses the hand-back. The verdict is still well formed and from the right seat, and evidence.verdicts counts only a file whose current sha matches, so a later rewrite cannot reuse the earlier row.

## Probes
pytest at head in a scratch copy: 403 passed.
Scratch probes, 22 passed: no attest when agent_type is absent, builder, planner, sentinel-arch or sentinel-security for a quality verdict, also with agent_type/subagent_type spoofed inside tool_input.
Scratch probe: a planner PostToolUse(Agent) with a forged tool_response no longer attests (the old forgeable path is removed).
Scratch probe: seat B cannot replace and attest seat A's attested file at the hand-back (denied, one attest row), so #1039 part 1 still holds.
Scratch probe: an absolute outside path, a ../ escape and a symlink planted under verdicts/ are all denied, with no attest.
Finding regex: '- [high] blocks: yes. Failure: x', with BLOCKS/YES case, a double space, 'note blocks: yes' or 'a.py blocks: yes', is rejected. 'blocks: no. blocks: yes ...' is a note by the author's own label. PASS plus an unanchored blocking finding is rejected. Every non-matching line errors rather than being dropped.
Scratch probe: hand-back followed by plain text gives ended=False, so a block and no verdict.missing.
Mutants: dropping the sentinel- check is killed by test_only_the_gates_own_seat_attests_at_the_handback. Dropping the anchor requirement is killed by test_a_note_needs_no_file_line_but_a_blocking_finding_does. Dropping 'or ended' is killed by test_a_problem_found_after_the_handback_ended_the_run_is_recorded. Disabling the gate check is killed by test_a_verdict_for_another_gate_is_refused. role-from-tool_input and ended-always survive (notes above).
Agent tooling: the charters changed only wording, with no tool grants, so no scanner was run.
Confidence is medium rather than high because I could not see a live PreToolUse payload to confirm the harness sends agent_type/agent_id for subagent calls. If it does not, no attest happens at the hand-back (fails closed). PostToolUse traces show agent_id on 517 of 653 rows.

## Residual risk
A sentinel seat can still name a well-formed verdict file of its own gate that a non-seat wrote but no seat had attested yet. That existed before this change at SubagentStop and is unchanged here.
