Verdict: PASS
Gate: arch
Item: session-context-cap
PR: taoq-ai/wuwei#1149
Head: 3fab3cb650f206a9bf7834fd2dcb83cb8722778d
Confidence: high
Breaking: no

## Findings
- [low] skills/wuwei-run/SKILL.md:13 blocks: no. G-3 says the planner follows the model table. Before this change the table reached the planner inline. Now it reaches the planner only if it follows the pointer line "Read before the first plan pass: your charter <path>". The /wuwei-run procedure the planner runs each pass reads goals.md, standards.md, plan and status at step 2, but not planner.md, and step 3 starts approved builders before the lead runs. The runtime backstop is PR #1146 (agent files carry the table's model and effort frontmatter, and a PreToolUse note on a departure names the table's setting). That backstop is not on main. Until #1146 lands, a planner that skips the pointer launches seats off-table and nothing advises it. Cheapest strengthening: add `planner.md` to the step 2 read list. The alternative is to inline the table rows only: 645 characters, and the 40-item board would still show about 24 items. The spec's How this fails 3 names this risk, but the reliance on #1146 is not under Assumptions.
- [low] cli/wuwei/hook.py:303 blocks: no. The trim drops the last board lines in board.compute's order: owed replies, then each repository in name order with scores high to low inside it. In a multi-repository workspace the last repository's top items are dropped before the first repository's lowest. The left-out line and /wuwei-run step 2 (`wuwei status`) cover this, and the spec records it as residual risk.
- [low] cli/wuwei/hook.py:298 blocks: no. The hook now depends on the `## Decisions` and `## Done` headings in charters/_common.md (coupling to charter structure). The new test (test_charters.py, the Decisions and Done sections must appear verbatim) and the existing test_decisions_and_done_are_stated_once_in_common work as the fitness function: renaming a heading fails a test, so the coupling never fails silently.
- [low] blocks: no. Codex shares this handler (hooks/hooks.json, hook.handle, with no Codex-specific SessionStart path in hook.py). The output only shrinks, so a Codex session loses nothing it cannot read through the pointer. The spec records the Codex cap as an assumption, not a measurement (unmeasured).

## Probes
- Conformance: design.md section Hooks (SessionStart row), docs/site/concepts/hooks.md and getting-started.md now match the code. The promise allows "a short pointer that names the charter files to read, with the board kept", and the head does exactly that. Constitution VI: no config key added.
- Route differential (AGENTS.md), builder's route_diff.py run from my scratch copy on git archive trees of main b28a3dc and head 3fab3cb: corpus sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 on both, 251 routes, 511 cases. guards 251/0 moved; PreToolUse Bash 251/0 moved; payloads 7/0 moved; SessionStart 2/2 moved as intended (0 items 15,987 to 4,877 chars; 40 items 20,456 to 9,346 chars, paths normalised). No refusal names a different PR or repository. Guard parsing is untouched, so no combinatorial probe applies.
- measure.py on the head tree: 0 items 5,332 chars; 40 items 9,949 (28 shown, 12 left out); 40 items with 3,000-char goals and standards 9,949; 200 items 9,950 (28 shown, 172 left out).
- Composition with #1146 (head e0351a1, based on 3d2eb29): `git merge-tree --write-tree 3fab3cb e0351a1` is clean (tree e601ab3). On that merged tree from git archive: suite 1824 passed, 2 skipped. Session context 5,338 / 9,955 / 9,955 / 9,956 chars, so the growth in planner.md no longer reaches the context. Vendored hook.py and planner.md are identical to the sources in both the head and merged trees.
- Suite at head (git archive copy, /root/.local/bin/pytest -q): 1780 passed, 2 skipped.
- CI at head, read once through REST check-runs: CodeQL, ZIRAN, Analyze (actions, python), test 3.11/3.12/3.13 and ziran-audit all completed and succeeded.
- Fitness: runtime lines (`cat cli/wuwei/*.py | wc -l`) 2,992 main, 2,995 head (+3, item budget 6), 3,055 merged with #1146, under the 3,400 limit.
- Mutants: the builder's mutants.py at 3fab3cb in fresh archive copies killed 8 of 8. My extra mutant, dropping `lines[-1].startswith('- ')` from the trim guard, is killed by test_the_session_start_context_holds_the_cap_when_the_board_has_no_item_line_to_drop.
- Confidence is high because the differential, the merge with #1146, the suite and CI all agree, and the change sits in one function. The open question is planner behaviour (G-3), and the pointer plus #1146's advice cover it.

## Residual risk
The planner reading planner.md before launching seats depends on the pointer line, and at runtime on #1146 once it lands. The 10,000 cap and the Codex behaviour are taken from the harness docs, not from a live run.
