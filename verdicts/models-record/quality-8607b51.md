Verdict: PASS
Gate: quality
Item: models-record
PR: taoq-ai/wuwei#1146
Head: 8607b514fc198f5b46d9d28a58a495695dfdbce9
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:90 blocks: no. X7 (`fam` returns '' with no fallback) still survives the full suite, re-run in two fresh copies. Input: an owner row `builder=mythos high` and a launch on model `other`. Under the mutant both names read as '', so the advice is skipped. The head advises (scratch probe test_fam_fallback passes). The harm is low because the hook only advises; the missing test is a note.
- [low] cli/wuwei/hook.py:76 blocks: no. X8 (the reason not cut at 200 characters) still survives, re-run in two fresh copies. At the head a 500-character reason reads back as 200 (probe test_long_reason_capped). No test holds the cap.
- [low] blocks: no. A number the merged head does not support: specs/models-record/plan.md:68 says "Headroom after this item: 355 lines", but after merging main dc39cae the runtime is 3,070 (`wc -l cli/wuwei/*.py`), so the headroom is 330. The +59 delta holds against the named base 3d2eb29 (2,986 to 3,045) and against dc39cae (3,011 to 3,070).
- [low] blocks: no. Size: runtime +59 against the item budget of 40, under the 3,400 cap. Under the common rules this is process fit, and the PR has a `Size:` line and a runtime paragraph that explains the overrun (the advice block, 30 lines). It is recorded for the retro.

## Probes
- Suite at the head (fresh `git archive 8607b51` copy, /root/.local/bin/pytest -q): 1930 passed, 2 skipped. This matches the builder's figure.
- Survivors re-run one at a time, each in its own fresh `git archive 8607b51` copy, with only cli/ mutated and tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from deselected, against the full suite (tools/rerun.py). Killed: X1 (test_the_attest_copies_the_launch_with_its_own_agent_id), X2 (test_the_haiku_floor_is_for_gates_only), X3 (test_learning_shows_each_seat_by_model_and_effort), X4 (test_the_task_tool_name_is_advised_too), X17 (test_learning_shows_each_seat_by_model_and_effort), M13 (test_no_advice_for_a_codex_spawn_or_a_role_outside_the_table), M23 (test_learning_shows_each_seat_by_model_and_effort). Each of these was killed by exactly 1 failure (1928 passed). Survived: X7 and X8 (1929 passed), and both survived again in a second fresh copy.
- I ran the builder's mutants.py myself at 8607b51 in a fresh copy (it re-vendors .claude/ after each mutation). Result: 40 mutants, 0 survived. Every kill names a tests/test_models.py test and none names the drift test, so the PR body's "40 of 40" claim holds.
- Red check: e0351a1's code with the head's tests/test_models.py gave 7 failed, 45 passed, as the PR claims. The failures are the floor row, the three newline/period brief lines, the empty reason line, the empty models key and the doc sentence. The join, count, Task and Codex-row tests pass on e0351a1, because that code was correct. The mutants above show these tests bite.
- Real consumers: `launch` and `started` go through hook.handle (PreToolUse, PostToolUse). The attest-join test drives hook.handle SubagentStop with a verdict file. The learning test calls report.day over seat.started, seat.stopped and attest rows (4 launches over 2 items, a pre-item attest row with no `blocking` key, an unmeasured-model row with effort high).
- Main-versus-head differential (the builder's route_diff.py, run by me under the pytest venv's python, main dc39cae against head 8607b51, the head's corpus for both). Corpus sha256 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0 is the same on main and head, checked with sha256sum. 257 Bash routes, 0 moved. 8 payloads, 3 moved, all only the new seat.started fields; the seat.stopped effort row is gone, so this is 4 last round and 3 now. 486 Agent launches, 290 moved, all from null to additionalContext, ledger rows unchanged. 0 permissionDecision or updatedInput.
- Floor probe: with CLAUDE_CODE_SUBAGENT_MODEL=claude-haiku-5-5 and no model in the call, a sentinel launch gets no note. This is the same as e0351a1 and matches promise (5) (the variable turns model advice off). A `builder=claude-haiku-5-5 low` owner row with a haiku builder launch gets no note (correct, the floor is for gates).
- set_config dict branch (ws.py:107-108): kept is the right call. It is the one CLI path for `wuwei config models` that docs/site/reference.md:45 and the announcement name. Five tests write the key through it, and M18 is killed by test_a_malformed_models_value_is_dropped. It is not speculative, so my earlier simplicity note is withdrawn.
- sentinel-arch trim (8607b51): a word diff of charters/sentinel-arch.md against dc39cae shows three rewordings: "The written architecture is" to "That is", "for each changed module, read what it imports" to "read what each changed module imports", and "to that gate" to "there". No rule, number or clause is removed. agents/sentinel-arch.md has 2248 words (wc -w), under AGENT_WORDS 2250 in tests/test_charters.py. The agent copies under .claude/agents and agents/ carry the same diff.
- closed: mutant count overstated by the vendored drift test at 9dfd2ad/4c28cdd (40 of 40 confirmed by my run).
- closed: attest agent-id join untested at 4c28cdd (X1 and M33 killed).
- closed: two report numbers untested at 4c28cdd (X17, M23, M34 and M41 killed).
- closed: brief regexes crossing lines at 9dfd2ad (hook.py:75 now uses `[ \t]*`, and M35 and M36 are killed).
- closed: upgrade.py "five 1.0 keys" at 9dfd2ad (both copies now say "six keys"; a grep finds no stale config-key statement outside historical specs).
- closed: M13 Codex advice with a models row, X2 floor on every role, X3 blocking fallback, X4 Task tool name at 4c28cdd (all killed above).
- closed: seat.stopped effort speculative at 9dfd2ad (removed, M17 dropped with it).
- Simplicity: none. The unread seat.stopped effort is gone, and the set_config dict branch is the documented CLI path. Nothing else in the delta can be removed without losing a promised behaviour.
- Confidence high: every listed survivor and every claimed kill was re-run by me in fresh copies against the full suite with the drift test excluded. The builder's own 40-mutant run reproduced exactly.

## Residual risk
X7 and X8 remain untested low-harm branches of an advice-only path. The floor applied without path knowledge, and to owner rows, is a spec choice. The resolvedModel rows will show it in the retro.
