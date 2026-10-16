Verdict: PASS
Gate: goal
Item: draft-raise
PR: taoq-ai/wuwei
Head: d485ba8e186600331d864dccf7e37db02fb3e210
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:163 blocks: no. gh pr ready and gh pr edit --add-reviewer with a fullwidth digit (for example gh pr ready followed by a fullwidth 5) passed at 02be6b9 when the PR was ready, and are now refused because no PR is named. gh reads that word as a branch name, so the refusal is a false hold at worst. The spec's Phase 6 and T023 record it.
- [low] blocks: no. The runtime stays at exactly 3,000 of 3,000 lines (main 034d067 is 2,962). The scope notes from earlier rounds still stand, and each change only makes a door stricter.

## Probes
- Acceptance 1 to 7: the named tests and test_every_route_reads_as_recorded pass at d485ba8: 254 passed in that selection.
- Acceptance 8: in a git archive of d485ba8, pytest -q gave 930 passed, 2 skipped; cat cli/wuwei/*.py | wc -l gave 3000; bin/wuwei agents build printed "agents match the charters" with a clean status; cli/wuwei and skills match their .claude vendored copies (only __pycache__ differs).
- Merge f74efec1 (origin/main 034d067, #1101 rename): this branch's skill lines follow the rename into skills/wuwei-rules/SKILL.md (the draft text is at lines 28 and 41), and no skills/wuwei/ remains. charters/planner.md and _way.md carry both the draft order and /wuwei-run. The routes.json sources are re-cited to wuwei-rules.
- Corpus: sha256 of routes.json at d485ba8 is 93d26ddc..., which matches compare/corpus.sha256.
- Compare: I ran the builder's harness on git archives of 034d067, 02be6b9 and d485ba8. The outputs are byte-identical to compare/main.txt, prev4.txt and head.txt.
- 02be6b9 to d485ba8: exactly 6 lines changed, all ASCII-digit fixes. pulls/7%D9%A3/requested_reviewers and pulls/7%EF%BC%97/ccr/ready_for_review now check PR 7 instead of 73 or 77, and pulls/5%D9%A3/merge now checks PR 5 instead of 53. Three gh pr commands with a fullwidth digit now give the no-number refusal: edit with a fullwidth 5 and --add-reviewer, ready with a fullwidth 5, and merge with a fullwidth 7. Nothing else changed.
- 034d067 (main) to d485ba8, by count: 26 refused to passing (all draft creates, none outside the draft spellings); 44 passing to the ready door; 5 passing to the merge door; 4 newly refused; gh pr merge with a fullwidth 7 moved from a check of PR 7 to the no-number refusal; 2 GraphQL rewordings; 51 wording-only create refusals; 4 merge refusals that now name the PR or repository gh reads. This matches the revised T023 line item for item, over 274 commands.
- Phase 6 against the code: [0-9] replaces \d in the ready, reviewer and merge routes and the PR URL; isascii() and isdigit() guard the gh pr and MCP numbers. This matches T033 to T035, spec Clarifications and Breaking, analysis S8 (no open HIGH) and the checklist.
- Confidence high: every differential reproduced exactly and the only moves are the routes the builder lists.

## Residual risk
GitHub's and gh's reading of non-ASCII digits is as the security gate recorded it; I made no live call here. The runtime has no headroom.
