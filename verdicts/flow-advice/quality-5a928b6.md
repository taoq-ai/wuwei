Verdict: PASS
Gate: quality
Item: flow-advice
PR: taoq-ai/wuwei#1225
Head: 5a928b64d7f210dafd85cc1f7faf8c6dbed0b98a
Confidence: medium
Breaking: no
Supersedes: none

## Findings
- [low] skills/wuwei-run/SKILL.md:19 blocks: no. Step 3 ("Start it now, as the last step says") and step 10 ("builders in parallel, highest score first") still read as start every approved item; both defer to the planner charter, which now holds the limit, so the chain resolves, but the item's file list did not include this skill and a one-clause "under the WIP limit and the seat ceiling" there would remove the doubt at the day start, when a queue of more than 4 is most likely.
- [low] tests/test_charters.py:473 blocks: no. Two clauses of the promise are not pinned: "Fix rounds, gates, shepherd work and merges on open PRs come before any start" (acceptance 1) and "name a dirty one and leave it" (close step 4). Removing either in a copy left the new test passing. Untested prose clauses, not a guard that lets a concrete input through.
- [low] tests/test_charters.py:483 blocks: no. The test asserts on prose fragments, as the neighbouring charter tests do; it does not pin "dated" lines or the steward's "unmeasured when absent" clause. A note only.

## Probes
Reviewed at 5a928b6 in a git archive copy under the scratch folder sentinel-quality-flow-advice. The diff was taken against 6828776, because the local main ref is stale (c2fafc7): against it the stat shows runtime files that are not in this PR. Against 6828776 the diff is 15 files, 0 under cli/.
- New test at the head: test_the_planner_finishes_before_starting_under_a_wip_limit_and_a_seat_ceiling passes. Run on the 6828776 tree with the new test file, it fails at test_charters.py:478, so it failed before the implementation.
- tests/test_charters.py at the head: 181 passed. `pytest -q tests -k "vendored or agents"`: 14 passed. These counts are from my runs, not the PR body.
- Mutants (each in a fresh copy of the head): "fewer than 4" changed to "fewer than 5" in charters/planner.md killed by the new test. Removing the fix-rounds-first sentence survived (finding 2). Removing "name a dirty one and leave it" survived (finding 2).
- `bin/wuwei agents build` prints "agents match the charters" and leaves git status clean: no drift.
- Vendored copy: cmp shows .claude/wuwei/charters/{_way,planner,steward}.md and .claude/skills/wuwei-{close,watch}/SKILL.md identical to the tree. docs/site is not vendored, so nothing to compare there.
- wuwei-close renumbering: grep across charters, skills, docs, tests and fixtures finds no reference to a numbered close step. Nothing breaks. The summary step now lists housekeeping in its order, and the docs match.
- Consistency with `_common.md`: no new owner question class is added; the owner is told the cost once and the planner then acts, which fits Decisions. planner.md, _way.md and wuwei-watch step 5 agree on 4 items and 8 seats. design.md and docs/site carry no start-every-item text. Only wuwei-run is stale (finding 1).
- `Item: <id>` in the builder brief: cli/wuwei/hook.py:75 parses `\bItem:` from the brief, so the launch does record its item. Steward flow numbers: hook.py:260 writes session, agent and duration_ms to the trace, so the sources exist.
- Emoji and em dash scan of the added lines: none.
- Not run: CI result (not my input). The full test suite was not run; only the charter, vendored and agents tests were.
Simplicity: none to delete. The docs/site watch.md section repeats the charter, but it is the concepts page the item asked for.

## Residual risk
The rule is prose advice. How closely the planner follows it, and whether 4 and 8 are the right numbers, is unmeasured until the steward's first flow retro. wuwei-run step 3 may be read literally at a day start.
