Verdict: PASS
Gate: arch
Item: verdict-handback
PR: taoq-ai/wuwei
Head: 9a7cec600c3e89192b872d23b8714a26d654504b
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/hook.py:30 blocks: no. Mutant: dropping the `ended = False` reset on a later text part survives the suite. The code is correct; a missing test. Under the mutant, a seat whose hand-back was refused (non-auto mode, or denied by the lint) and that then ends with a plain-text report holding a bad verdict would get a `verdict.missing` row instead of a block it could still act on. Suggested test: a transcript with a SubagentHandback tool_use followed by a text part, then assert the stop blocks.
- [low] cli/wuwei/hook.py:65 blocks: no. The hand-back lint relies on the harness sending `agent_type` on a subagent's PreToolUse (recorded under the spec's Assumptions). If that field is missing and the stop also hits the #1039 transcript read race, the removed post_tool re-read can no longer attest the verdict. It then shows as uncounted in evidence.uncounted, not silently, so "nothing gets worse than today" under How this fails 1 is slightly too strong. Overturned by a live trace showing agent_type on PreToolUse.
- [low] cli/wuwei/hook.py:70 blocks: no. A refused hand-back from the verdict lint is recorded as a `refused` row (tool SubagentHandback), so report.py's "Doors: Refused: N" now counts verdict-shape refusals together with door refusals. This decision is settled without being recorded. It can be undone cheaply, and the reason list keeps the two apart.
- [low] docs/site/reference.md:84 blocks: no. The published verdict format still shows `<file>:<line>` as required on every finding. A writer that follows it is still valid (it is a stricter subset), but the page no longer says that a note may omit the place.

## Probes
Every caller of transcript(): `grep -rn "transcript(" cli/ tests/` finds two, last_text (hook.py:40, takes [0]) and subagent_stop (hook.py:132, unpacks three). Neither is broken.
Consumers of the parsed findings' 'where' (now possibly None): grep over cli/wuwei finds none outside verdict.py.
Old vs new verdict.parse on all 53 files under /home/user/wuwei/.wuwei/verdicts (scratch cmp.py, loose and strict): every non-error field is identical, and the error count and pass/fail status are identical for every file. Only the wording of the error messages changed. Already-attested verdicts are counted from their attest rows and still parse the same, so this is not Breaking.
Format compatibility: FINDING only gains an optional group, and the blocking rule is unchanged for anchored lines. Any verdict a Claude or Codex seat (#1078) writes in the old shape still parses. Codex attestation is unchanged and stays out of scope.
post_tool removal: specs/verdict-handback/analysis.md A3 records that the #1039 fallback moves to the hand-back's tool_input.message, where no transcript race applies.
Trust boundary: the role comes from the harness agent_type and never from the message. The path stays confined under .wuwei/verdicts by the same _verdict_problem, and the check against replacing another seat's verdict still holds.
charters/_gate.md == .claude/wuwei/charters/_gate.md, cli/ == .claude/wuwei/cli/ for hook.py and verdict.py (diff). `bin/wuwei agents build` in a scratch copy produced no drift (diff -rq against a fresh archive).
docs/design.md hook table updated for PreToolUse and SubagentStop.
Suite at the head in a scratch copy: 403 passed. Runtime: 2997 lines (wc -l cli/wuwei/*.py).
Mutants (scratch mut.sh): making file:line required again is killed by test_a_note_needs_no_file_line_but_a_blocking_finding_does. Dropping file:line from the blocking rule is killed by the same test. Dropping `or ended` is killed by test_a_problem_found_after_the_handback_ended_the_run_is_recorded. Removing the sentinel role check in pre_tool is killed by test_only_the_gates_own_seat_attests_at_the_handback[wuwei:builder]. Dropping the ended reset survives (first note).
Confidence is high because the full suite, the mutants and an old-vs-new parse over every real verdict all agree. A live harness trace of PreToolUse carrying agent_type is unmeasured.

## Residual risk
The harness's PreToolUse payload for a subagent is assumed and was not measured live. If agent_type is missing there, the hand-back lint is inert and SubagentStop records the problem instead.
