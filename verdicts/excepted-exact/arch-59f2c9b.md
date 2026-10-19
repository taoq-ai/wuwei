Verdict: PASS
Gate: arch
Item: excepted-exact
PR: taoq-ai/wuwei#1150
Head: 59f2c9bf2ea4d6d8ca5a4934a6860b49a5f83d30
Confidence: high
Breaking: yes: an approved exception: ruling whose gap is a part or superstring of the printed gap, one gate name for a multi-gate gap, or a gap the hook recorded with a newline tail ("<gap>\nAccept") waived its gap on main and waives nothing at this head, so `wuwei evidence`, the board and the merge door now hold PRs that read mergeable on main (declared: `fix(evidence)!:` title, BREAKING CHANGE footer, Announcement line; the owner's `breaking:` confirmation is still owed)

## Findings
- [low] blocks: no. specs/excepted-exact/probe.py:37 still hand-copies the announcement gap text that open #1148 (head a1052b4) rewrites; after #1148 lands the probe's printed-gap list is stale. Harmless to the suite (the test never compares the list to the producers); refresh it in whichever PR lands second if the probe is re-run.
- [low] blocks: no. The announcement names what newly holds but not the other direction the probe measured: 832 pairs (spacing, tab and ` [waiting]` variants of the printed gap) waive at the head and did not on main. No existing client fails from that widening, so it is not part of the break; a note for the release text only.

## Probes
- Delta read: `git diff 95e956c 59f2c9b` touches charters/planner.md (and its .claude copy) and adds one test in tests/test_evidence.py; `git diff 24062fd 95e956c -- cli/wuwei/evidence.py` is empty, so the merge of dc39cae leaves the reviewed code unchanged.
- closed: [medium] evidence.py:441 undeclared break at 59f2c9b. REST read of /pulls/1150: title `fix(evidence)!: ...`; body has `BREAKING CHANGE:` naming the same three groups my previous Breaking line named (part or superstring, one gate of a multi-gate gap, `<gap>\nAccept?` newline tail), what newly holds (evidence, board and merge door hold PRs that read mergeable before) and the migration (re-ask with the gap as `wuwei evidence` prints it, or a gate gap's whole gate list, on one line); Assumptions now say breaking and wait for `breaking:`. Comment 6259418454 (REST read of /issues/comments/6259418454, by the owner's account, on #1150) states the change, the three affected groups, migration and rollback.
- closed: [low] charters/planner.md:72 at 59f2c9b. The line now reads "accept a gap, as `wuwei evidence` prints it"; it matches the guard's refusal text (guards.py:396) and docs/site/concepts/decisions.md:57. Word count of lines 72-74 is 33 at 24062fd and at the head (`sed -n 72,74p | wc -w`). planner has no generated agent; `.claude/wuwei/charters/planner.md` equals the charter (`diff`), and test_charters passes in the suite.
- closed: [low] newline residual owner at 59f2c9b. PR body Assumptions and Residual risk now say no planned item closes it; the caller will amend the plan.
- The new test pins existing filters (no head, `kind` other than exception, `[waiting]` only as a suffix); it goes through evidence.gaps, consistent with the earlier tests.
- Fitness: `cat cli/wuwei/*.py | wc -l` 3,013 at the head (3,011 at main dc39cae per the PR, +2 as before; ceiling 3,400). `diff -r -x __pycache__ cli/wuwei .claude/wuwei/cli/wuwei`: identical.
- Suite: `/root/.local/bin/pytest -q` in a git archive copy of 59f2c9b: 1883 passed, 2 skipped.
- Landing order with #1148 (REST read of /pulls/1148: open, head a1052b4, base dc39cae; /pulls/1148/files): `git merge-tree --write-tree 59f2c9b a1052b4` is clean (tree b5e960d); suite on a git archive of that tree: 1917 passed, 2 skipped; runtime 3,013. This PR's `Announcement:` line matches #1148's new regex `^Announcement:[ \t]*https?://[^\s/?#]\S*[ \t\r]*$` (python3 -I check: True), so its announcement still counts if #1148 lands first. Both PRs are breaking and both declare it; the end state is the same in either order (exact match against #1148's new announcement gap text). Landing order does not matter; the only follow-on is the stale probe list above.
- Confidence high: the delta is small, every previous finding is closed on read evidence, and the combined tree is green.

## Residual risk
The break still waits for the owner's `breaking:` confirmation at the head. Fail-closed residuals (newline-tail questions, printed gaps holding '. ' or '?') stay unowned until the plan is amended.
