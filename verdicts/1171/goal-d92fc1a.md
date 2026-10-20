Verdict: PASS
Gate: goal
Item: 1171
PR: taoq-ai/wuwei#1184
Head: d92fc1a50d41c2308d3864c05ec464c11e36c8b2
Confidence: medium

## Findings
- [low] blocks: no. Issue #1171 scenario 1 asks the note to "name that location" for a repo whose ADRs sit under specs/<feature>/. The note names "where the repository keeps its ADRs", docs/adr/, docs/decisions/ and "the item's spec folder", so a specs/<feature>/ home is reached only through the generic clause. The approved plan item (not the issue) scopes the wording this way and the hook cannot see the repository, so this is a limit, not a drift.
- [low] blocks: no. The issue's scenario 2 says "amend ADR-003" by name. The PR follows the plan item ("that ADR") and records why under Assumptions (the hook sees only the question and answer). The gap is named, as the goal gate requires.
- [low] blocks: no. `wuwei evidence` at this head still lists the gates (arch, quality, security, goal) and owner review on cli/wuwei/hook.py as waiting. They are process state, not a goal defect.

## Probes
- Trace: G-2 (bugs found running WUWEI on itself get fixed) -> issue #1171 (labelled bug, found on 4.2.2) -> plan item 1171 (3 acceptance lines) -> delivered diff. Source text: plan promise "record the decision as an ADR where the repository keeps them ... amend that ADR rather than add a file". Output: cli/wuwei/hook.py:385-387 note, charters/planner.md:77-80, charters/sentinel-arch.md:4 ("the repository's ADRs").
- Acceptance 1 met: note names docs/adr/, docs/decisions/ and the item's spec folder; test asserts "repository's docs/adr/" is gone. Acceptance 2 met: note and planner say "amend that ADR instead of adding a file". Acceptance 3 met: planner and arch say the same rule; `wc -w agents/*.md` at the head gives a maximum of 2249 (sentinel-arch), next 2106, so all are at or under 2250.
- Explain-back in the PR body matches the plan item and the goal. It claims nothing the item did not ask for, except the two docs/site/concepts pages, which it names as an assumption (user copy of the same rule; without them the docs would contradict the charter).
- Complement check: `grep -rn "docs/adr"` over charters, agents, .claude/agents, cli and docs/site leaves only the three "an existing docs/adr/ or docs/decisions/" mentions; no text still names docs/adr/ as the one home. Vendored copies are byte-identical (`diff -r cli/wuwei .claude/wuwei/cli/wuwei`, `diff charters .claude/wuwei/charters`).
- PR body counts read at the head: runtime `cat cli/wuwei/*.py | wc -l` = 3318 (as stated, 3317 on main, inside the 1-line budget); `sha256sum tests/fixtures/routes.json` = 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49 with 263 routes (as stated); `pytest tests/test_guards.py -k route` = 362 passed (as stated); `pytest tests/test_hook.py tests/test_charters.py` = 609 passed on Python 3.13 (as stated). The merge of main at 1877565 is in the history. I did not rerun the full suite or the 4 macOS bash 3.2 failures the body names.
- Mutant: in a copy at the head, changing "amend that ADR instead" to "add a file instead" in cli/wuwei/hook.py fails test_a_one_way_answer_asks_for_an_adr_where_the_repository_keeps_them. The mutant is killed (the vendored copy was not mutated; the agents-drift test is not part of this check).
- CI at the head, read with `gh pr checks 1184 -R taoq-ai/wuwei` after test 3.12 and 3.13 finished: CodeQL, ZIRAN, test (3.11), test (3.12), test (3.13), Analyze (actions), Analyze (python), ziran-audit all pass. At my first read 3.12 and 3.13 were pending; the second read showed them passing.
- Confidence reason: acceptance mapping is direct and counts reproduce; medium because the guard-route differential at main versus head was reproduced only as the 362-pass count at the head, not rerun against main (the diff changes note text only).

## Residual risk
The note stays generic: a repo with ADRs under specs/<feature>/ of another feature gets "amend that ADR" only if the planner finds it. The planner reads the repository, which the item puts out of scope for WUWEI itself.
