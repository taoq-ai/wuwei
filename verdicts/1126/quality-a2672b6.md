Verdict: PASS
Gate: quality
Item: 1126
PR: taoq-ai/wuwei#1127
Head: a2672b6e87bf8eacb9aa25a2c745f3fd3dd4ce5b
Confidence: medium

## Findings
- [low] tests/test_setup.py:334 blocks: no. The test asserts `'no pull request'` inside the step text, but that phrase also appears in the backticked board label `no pull request yet`. Mutant: rewrite the step to read "An approved item with no running seat" (drop the "no pull request" condition) and the test still passes. The condition (start only items with no PR) is untested; a fix is to assert on the "no pull request and no running seat" pair together.
- [low] blocks: no. The test reads only `skills/wuwei-run/SKILL.md`; the installed `.claude/` copy is byte-identical (cmp) and the existing drift test at tests/test_setup.py:235 covers it.

## Probes
- Copy of the tree at the head via git archive; `pytest -q tests/test_setup.py`: 40 passed, none skipped or deselected.
- Mutant "step 3 no longer says 'already approved' before the launch" (text changed to "Start what is approved."): the new test fails (ValueError from index). Killed.
- Mutant "drop 'no running seat'": the new test fails. Killed.
- Mutant "drop 'no pull request' condition": the new test passes. Survived (see the low note; not a concrete harm, the text is guidance).
- Renumbering: grep for step references in skills, .claude skills and charters finds none that point at a changed number. "as the last step says" resolves to step 10 (start the approved work), which is still last.
- The board label `no pull request yet` is emitted by cli/wuwei/board.py:79 for approved items, so the step's wording matches the real board.
- Guard and parser probes (routes corpus, combinatorial): not run, no guards.py or hook.py change.
- Simplicity: none to delete; the step is one short paragraph and the test is one assertion block. The mirrored `.claude/` copy is required by the drift test.

## Residual risk
Documentation-only behaviour change; the test checks wording and order, not that a lead actually starts approved items. The "no pull request" half of the condition is only weakly pinned.
