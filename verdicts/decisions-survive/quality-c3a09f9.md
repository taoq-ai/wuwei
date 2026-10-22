Verdict: PASS
Gate: quality
Item: decisions-survive
PR: taoq-ai/wuwei#1239
Head: c3a09f9e1b4bc155962f3c297a93b7b52dceac1d
Confidence: medium
Breaking: no

## Findings
none

## Probes
- Delta read: 4850c9c changes only ws.answers (the lines it returns pass through `' '.join(n.split())`) and adds one test. The merge e72bd00 and c3a09f9 (hooks.md cell) add no code of this PR's.
- Merged-result check: `git diff` of the merged cli/wuwei/hook.py, guards.py and ws.py against each parent. Against origin/main the only lines are this PR's own additions (the AskUserQuestion answered-question branch, the session-start answers block, ws.answers). Against my previously reviewed parent, guards.py differs by main's create_door change (6 lines) and hook.py by main's #1238, #1241 and #1236 code. So the guard branches are a pure union and the result matches neither parent in none of them; the route differential is not needed. Corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 is unchanged. `pytest -k "every_route or route_corpus or exception or owner or question"` on tests/test_guards.py in a `git archive` copy of the head: 394 passed.
- The meeting of #1238's held-item check and this PR: the held check in hook.pre_tool runs only for Agent and Task calls (`item` is False otherwise), and is joined as `guards.pre_tool(...) or held`; it never reaches the AskUserQuestion branch. The session-start answers block runs before board.rows in the same try; board.rows and board.text are called as before. The answered-question branch in guards.pre_tool is untouched.
- Vendored copy: `.claude/wuwei/cli/wuwei/{ws,hook,guards}.py` are byte-identical to cli/wuwei at the head.
- Tests at the head in a `git archive` copy: tests/test_hook.py `-k "decisions or answer or scope or plan_question or head or session or line_break or vendored"`: 253 passed (including the vendored-drift test). The planner ran the full suite (3537 passed, 2 skipped).
- Mutant, applied to both cli/wuwei and .claude/wuwei/cli/wuwei: the whitespace collapse removed (`said` returned as is). Killed by test_a_line_break_in_a_question_or_answer_never_adds_an_owner_answer_line. The test checks lines of the real session-start context for a forged dated line, and covers a question, an answer (with `\r\n`) and an unconfirmed reason.
- closed: low notes from 8c332f5 (approved default, board and answers sharing one try, rows reflow) remain notes with blocks: no; the delta does not change them.
- Simplicity: none. The collapse is one expression applied once to the list; truncation first and collapse after is safe, since collapsing only shortens.

## Residual risk
Collapsing happens after the 120-character cut, so a very long run of whitespace can shorten a line; harmless. The 7-day window and exact-text match remain the documented limits.
