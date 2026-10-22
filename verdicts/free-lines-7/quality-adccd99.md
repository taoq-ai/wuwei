Verdict: PASS
Gate: quality
Item: free-lines-7
PR: taoq-ai/wuwei#1237
Head: adccd9904380aa59882ef4f58617ec6498df4422
Confidence: medium
Breaking: no

## Findings
- [low] tests/test_setup.py:121 blocks: no. The size test pins the 3600 literal only against the live runtime (3,390 lines); no test ties the figure to the constitution, AGENTS.md, CONTRIBUTING.md, SECURITY.md, design.md or the philosophy page, so a doc could drift to another number unseen. A note, not a regression.
- [low] blocks: no. charters/_common.md: the Decisions lead-in changed from "Weigh every open choice on two questions: can it be undone cheaply, and how sure are you?" to "Place every open choice in this table". The table headers carry both axes, so no rule is lost, but the two questions are no longer spelled out.

## Probes
- Read the head with git rev-parse HEAD in the builder's worktree: adccd990. The diff against origin/main touches no file under cli/wuwei/ (cat cli/wuwei/*.py | wc -l gives 3390).
- Re-ran `pytest -q tests/test_charters.py tests/test_setup.py` in the worktree: 233 passed (189 in test_charters.py plus 44 in test_setup.py).
- `wc -w agents/*.md` from my own run: builder 1900, lead 1592, sentinel-arch 2147, sentinel-goal 1878, sentinel-quality 1967, sentinel-security 2004, shepherd 1700, steward 1736. The maximum is 2147, at most 2150, so every agent has at least 100 words of room. This matches the PR body.
- `bin/wuwei agents build` in the worktree prints "agents match the charters" and `git status --short` stays clean, so there is no drift.
- Vendored copy: `cmp` of agents/*.md against .claude/agents/*.md is identical for all 8. `diff -r charters .claude/wuwei/charters` is identical. cli/wuwei differs only by __pycache__. The test_the_vendored_plugin_matches_the_tree_it_was_copied_from test passes at the head. `.claude/wuwei/agents` does not exist, which is the tree layout and not drift.
- Mutants, each in its own `git archive adccd99` copy under the scratch folder:
  - A, sentinel-arch.md +4 words (2151): killed by test_a_generated_agent_leaves_100_words_of_room_under_the_ceiling[sentinel-arch], and also by test_the_generated_agents_match_the_charters. The existing 2250 ceiling test would not have caught it, so the new test is a real pin.
  - B, runtime padded to 3,601 lines: killed by test_the_runtime_holds_its_size_budget.
  - D, runtime padded to exactly 3,600: the size test passes, which is the correct boundary. Together with B this confirms the 3600 literal for the acceptance "passes at 3,500, fails at 3,601". The vendored-copy test fails in B and D only because the padding is in cli/ alone, which is expected.
  - C, the Done phrase reverted to "a delta of docs, generated files or at most" in the charter (agents rebuilt): killed by test_decisions_and_done_are_stated_once_in_common. My first sed attempt did not match because the line wraps, and it surviving was my error; I redid it with a multi-line replace and it was killed.
  - Weakness: the 100 figure is pinned by content only. Changing `- 100` to `- 50` in the test would not fail at the head (2147 <= 2200). That is inherent to a headroom test and is not blocking.
- Cross references: charters/planner.md ("Decisions 2") and charters/_gate.md ("Evidence 4") still resolve. The dropped "(Boundaries 2)" reference was not cited anywhere else (grep over charters, skills and docs).
- Rule-loss read of the _common.md diff: every rule is kept. The lines rewrapped or merged are assumptions, asking the owner, mechanical failures, the Done bullets, gates, process fit, evidence 1 to 4, boundaries 1 to 5 and the report. The "(over at least five merges)" to "(five merges or more)" change keeps the meaning.
- Size and docs: 3,600 appears in AGENTS.md, CONTRIBUTING.md, SECURITY.md, docs/design.md, docs/site/concepts/philosophy.md and the constitution (version 3.3.0). Remaining 3,400 hits are CHANGELOG history only.
- CI was still running at the time of `wuwei evidence` (gates missing: arch and quality, which this verdict covers for quality).
- Simplicity: none. The diff deletes words only, and the single added test (a parametrised ceiling check) is needed. No runtime line is added or freed.

## Residual risk
Low. Content-only change plus two test edits. The wording trim relies on the existing charter fitness tests, and the only unpinned parts are the 3,600 figure in docs and the exact 100-word margin.
