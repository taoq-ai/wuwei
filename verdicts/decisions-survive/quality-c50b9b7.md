Verdict: PASS
Gate: quality
Item: decisions-survive
PR: taoq-ai/wuwei#1239
Head: c50b9b71a7c05a51fc89908c1d00d9fb0f564933
Confidence: medium
Breaking: no

## Findings
none

## Probes
- Delta: since c3a09f9 the head has two merges of origin/main (d93d479 with #1242, c50b9b7 with #1243) and no commit of this PR's own. I read no new code of this PR's.
- Union check, `git diff origin/main(470ab63) c50b9b7` on the three runtime files. guards.py: only the plan import and the already-answered branch in the AskUserQuestion path. hook.py: only the session-start answers block and the widened "Answers or board unreadable" message. ws.py: only the `rows()` reflow and `answers()` (with the whitespace collapse). Nothing of main's is lost: #1242's `ws._cached` (ws.py:217, used at 136, 229, 246, 251) and `hook._confirm` (hook.py:340, with the `ws._cached(root, path.stem) != path` guard at 345) are present and untouched, and #1243 changes nothing in this PR's lines. Added-line counts against the main parent equal the counts at c3a09f9 (guards 7, hook 7, ws 17), so the merge added nothing and dropped nothing of this PR's. The merge result in these files equals main plus this PR, and the guard branches are a pure union, so I did not run the route differential (corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 unchanged by the diff).
- The meeting of #1242 and this PR: `ws.answers` reads through `ws.ledger`, which is unchanged by #1242; the cache functions are not on its path. Tests that cover both pass together (below).
- Vendored copy: `.claude/wuwei/cli/wuwei/{ws,hook,guards}.py` are byte-identical to cli/wuwei at the head.
- Test file merge, by `grep '^def test_'` names: all 166 of main's test_hook.py tests are present at the head (0 missing); all 175 of c3a09f9's are present (0 missing); the head holds 177 with no duplicate name; `git diff origin/main..head -- tests/test_hook.py` has no removed line, only this PR's block and what main already had. So the resolved file loses no test from either side.
- Tests at the head in a `git archive` copy: tests/test_hook.py `-k "decisions or answer or scope or plan_question or head or session or line_break or vendored or cache or confirm or link"`: 286 passed (this PR's tests, #1242's cache and confirm tests, and the vendored-drift test). The planner ran the full suite (3573 passed, 2 skipped) and CI is green.
- No new mutant: no code of this PR's changed since the pass that killed 13 mutants at 8c332f5 and the collapse mutant at c3a09f9.
- Simplicity: none to delete.

## Residual risk
The three low notes from the 8c332f5 pass stand (approved default against board.py, answers sharing the board's try block, the rows reflow); none blocks.
