Verdict: PASS
Gate: goal
Item: draft-raise
PR: taoq-ai/wuwei
Head: 02be6b9d05864d882c0e21f0c7a5b5fbef2e0bed
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:32 blocks: no. The new PR segment pattern [^/\d]*(\d+)[^/]* takes the first run of digits anywhere in the segment. So pulls/x7/... also meets the door as PR 7, which goes beyond the spec's "leading digits". This holds more than GitHub would route and never less, so it can only cause a false hold.
- [low] cli/wuwei/guards.py:209 blocks: no. The plain-word allowlist also holds an --input draft whose command has any quoted word with a space (for example -f title="feat: x"). It is a false hold that falls back to the create door and its draft guidance; the spec records the redirect case as a false hold.
- [low] blocks: no. The runtime stays at exactly 3,000 of 3,000 lines. The scope notes from earlier rounds still stand, and each change only makes a door stricter.

## Probes
- Acceptance 1 to 7: the named tests (draft create, non-draft create, MCP create, ready door with gate then attest, undo and already-ready, ready door shut, MCP update and copilot, GraphQL mutations) and test_every_route_reads_as_recorded pass at 02be6b9: 250 passed in that selection.
- Acceptance 8: in a git archive of 02be6b9, pytest -q gave 918 passed, 2 skipped; cat cli/wuwei/*.py | wc -l gave 3000; bin/wuwei agents build printed "agents match the charters" with a clean status; diff -r against .claude/wuwei/cli/wuwei shows only __pycache__.
- Corpus: sha256 of routes.json at 02be6b9 is 19dbc791..., which matches compare/corpus.sha256.
- Compare: I ran the builder's harness on git archives of 7f31a51, f1ca82b and 02be6b9. The outputs are byte-identical to compare/main.txt, prev3.txt and head.txt.
- f1ca82b to 02be6b9: exactly 5 lines changed, all from the lenient PR segment. pulls/%207 and 7%20 requested_reviewers, pulls/7.0 ccr/ready_for_review and pulls/7abc requested_reviewers moved from pass to the ready door; pulls/5x/merge moved from pass to the merge door. No other line changed verdict or text. The allowlist cases are not in the harness corpus; T030 tests cover them in tests/test_guards.py (around lines 756 and 777) and pass.
- 7f31a51 (main) to 02be6b9: 26 moved from refused to passing, all draft creates (none outside the draft spellings and d.json); 40 moved from passing to the ready door; 4 moved from passing to the merge door (//, %6D, ., 5x); 4 newly refused; 2 GraphQL merge refusals reworded; 51 create refusals changed wording only; 4 merge refusals now name the PR or repository gh reads. This matches the revised T023 count for count, with the split I asked for last round.
- Spec Phase 5 against the code: the allowlist [\w./=@:-]+ replaces the denylist; the PR segment on the ready, reviewer and merge routes is read from its digits; T030 to T032, spec Clarifications and Breaking, SECURITY.md, analysis S6 and S7 (no open HIGH) and the checklist all agree.
- Confidence high: every differential reproduced exactly and the only moves are the intended routes.

## Residual risk
The behaviour of gh, the shell and GitHub path handling is as the builder and the security gate recorded it; I made no live gh or GitHub call here. The runtime has no headroom.
