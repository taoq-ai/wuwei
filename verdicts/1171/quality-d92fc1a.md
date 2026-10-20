Verdict: PASS
Gate: quality
Item: 1171
PR: taoq-ai/wuwei#1184
Head: d92fc1a50d41c2308d3864c05ec464c11e36c8b2
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:385 blocks: no. Untested: dropping "the owner's answer" from the note's ADR contents survives (mutant `noanswer`, both runtime copies, test_hook adr test still passes). On main "quoting the owner's answer" was untested as well, and the item's promise does not cover it. A one-word assertion would cover it.
- [low] blocks: no. A limit, not a defect: a repository that keeps ADRs per spec folder, working an item below `full` with no spec folder, has no home the note names except "where the repository keeps its ADRs". The leading clause covers it, and the item puts finding the folder out of scope.

## Probes
- Read `wuwei plan show 1171`, issue #1171, and `git diff origin/main...d92fc1a` (17 files: note text in both hook.py copies, planner and arch charters plus generated and vendored copies, two docs pages, specs/adr-home/, two tests).
- Mutants: each in a fresh `git archive d92fc1a` copy under my scratch folder, applied to both `cli/wuwei/hook.py` and `.claude/wuwei/cli/wuwei/hook.py`, run with `pytest tests/test_hook.py tests/test_setup.py -k "adr or vendored_plugin_matches"`. Killed by `test_a_one_way_answer_asks_for_an_adr_where_the_repository_keeps_them`, with the vendored test passing (so the kill is behavioural): drop the amend sentence; drop `docs/decisions/`; drop "the item's spec folder"; revert the note to main's text; re-add "the repository's docs/adr/". Survived: drop "the owner's answer" (see finding, untested on main too).
- Charter mutants, both charter copies: dropping the planner's amend sentence is killed by `test_an_adr_goes_where_the_repository_keeps_them_and_a_reconfirmed_one_is_amended`. Reverting the arch line to "the ADRs under `docs/adr/`" is killed by the same test and `test_the_generated_agents_match_the_charters`. A mutant on only cli/wuwei/hook.py is killed by the adr test and the vendored-match test.
- Suites at head (uvx --python 3.13): test_hook + test_charters + test_setup: 649 passed. Full suite: 2734 passed, 1 skipped, 4 failed. The 4 are test_codex harness shell and three test_bash_runs_the_push_in_each_refused_shape cases (`{fd}>`, `{a_b}<`, `|&`), the bash 3.2 failures the brief names on main. None are touched by the diff.
- Agent word ceiling: `wc -w agents/*.md` at head, max sentinel-arch.md 2249 (at most 2250). Runtime `cat cli/wuwei/*.py | wc -l` 3318; hook.py 565 to 566 lines, within the 1-line budget. `cmp` shows the two hook.py copies are byte-identical.
- Residual `docs/adr` grep outside specs/: only the new rule text and tests. specs/vendored-drift still mentions docs/adr/ as history (correct: this repo's own ADR home).
- Guard rules: the hook.py change is note text in `_answers`, after the unchanged `one-way:` condition. No guard, door or parser changed, so the route differential and parser probes do not apply. The builder reports route tests 362/362 on main and head.
- Test quality: both tests assert on prose, but here the prose is the behaviour (the instruction text the seat receives). They read the real `hook.handle` PostToolUse output through #1172's transcript helper and the real charter files. No wall-clock, network or ordering dependence.
- CI at d92fc1a (`gh pr checks 1184`, read once after the first read showed 3.12 pending): CodeQL, ZIRAN, test 3.11/3.12/3.13, ziran-audit, Analyze all pass.
- Simplicity: none. The diff is a text swap of three sentences plus tests; nothing can be deleted.
- Confidence high: every phrase the promise names has a killing mutant on both runtime copies and both charters, and the full suite matches main's baseline.

## Residual risk
Text-only change. The note does not locate the ADR itself; it relies on the planner reading the repository, which the item scopes out.
