Verdict: PASS
Gate: quality
Item: models-record
PR: taoq-ai/wuwei#1146
Head: 78429d90b1129e421e733b58fb9dc66c4b28278b
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:92 blocks: no. Untested branch of the floor (US4): mutant Y2 makes `named` read only the role row (`for k in (role,)`) and it survives the full suite, re-run alone in a fresh copy (1989 passed). Input: `models = {"sentinel-quality standard" = ["haiku", "low"]}` or `= "haiku low"`, with a sentinel-quality launch on claude-sonnet-5-5 high at standard. The head gives the floor note (scratch probe test_probe_tier.py, 2 passed). Under Y2 the note is missing (2 failed). Every new floor test uses a role row only. The harm is low because the hook only advises; the missing test is a note.
- [low] cli/wuwei/hook.py:90 blocks: no. X7 (`fam` with no fallback) still survives. Re-run alone at this head in a fresh copy: 1989 passed. Unchanged since 8607b51.
- [low] cli/wuwei/hook.py:76 blocks: no. X8 (the reason not cut at 200 characters) still survives. Re-run alone at this head in a fresh copy: 1989 passed. Unchanged since 8607b51.
- [low] blocks: no. A claim the data at the reviewed commit does not support. The PR body's Tests section says `pytest -q tests/test_models.py -k non_string gave 4 failed`. At the head that selection matches 0 tests (63 deselected), because the test is named test_a_malformed_models_row_cannot_silence_the_haiku_floor. The count itself holds: the head's tests/test_models.py on the 2c4e806 code fails exactly 8 tests, the 4 floor cases and the 4 doctor cases.
- [low] blocks: no. Stale numbers in the spec artifacts: specs/models-record/plan.md:62-68 still says the runtime is 3,045 with 355 lines of headroom, and spec.md FR-007 says the item lands at 59. At the head `wc -l cli/wuwei/*.py` gives 3,086 (main 5fe8347 is at 3,026), so the item adds +60 and the headroom is 314. The PR body has the right numbers (3,026 to 3,086, +60).
- [low] blocks: no. Existing gap outside this diff: the timing tests in tests/test_guards.py (test_segments_and_redirects_stay_linear_at_125_and_500_kb, test_the_git_option_loop_stays_linear_at_125_kb, test_git_clean_joins_its_directories_once_however_many_pathspecs_follow) depend on wall-clock time. With 2 to 5 suites running at once they failed in 12 of 15 mutant copies, and they pass when a suite runs alone. Under load they make surviving mutants look killed (Y2, X7 and X8 each read as "killed" until re-run alone).

## Probes
- Suite at the head, in a fresh `git archive 78429d9` copy (`pytest -q`): 1989 passed, 2 skipped. This matches the builder's figure.
- Delta read with `git diff 2c4e806 78429d9` and `git show 2c4e806 --cc -- cli/`. The merge resolution is the import line only. Code changes are setup.py:140 (`note`) and hook.py:92-93 (`named`, `floor`).
- Doctor test reaches the real consumer: test_the_doctor_prints_the_variable_and_keeps_its_exit_code calls `__main__.main(['doctor'])` through cmd_doctor (__main__.py:156-160). It is parametrised over ok, warn and fail x both variables, and asserts the exit code with the variable unset and set, plus the printed `<VAR>: set to low` line. With a note counted as a warning (Y1), the ok cases fail. With the rows dropped (Y4), all 6 cases fail. With `note` changed to `warn` (M42), the ok cases and the row-status test fail.
- `note` elsewhere in cli/: grep shows that only cmd_doctor reads doctor statuses. It counts `fail` and `warn` only. setup.doctor has no other caller. Other `note` uses in cli/ (guards.py decision 'note', hook.py:61/66, report.py:48) are the guard note decision, not doctor statuses. The exit codes are documented with the note rule in README.md:76 and docs/site/concepts/models.md:121-122. README.md:50/86 and the cloud.md/codex.md mentions are about `warn` rows and stay true.
- Floor tests reach hook.handle: launch() in tests/test_models.py:28-31 calls hook.handle PreToolUse with an Agent tool_input.
- Mutants touching the doctor and the floor, each in its own fresh `git archive` copy, applied to cli/ and .claude/wuwei/cli/, full suite (tools/one.py). Killed, with the deterministic tests/test_models.py failure named:
  - M3 and M31: the haiku-gate test and 4 malformed cases.
  - M32: the haiku-gate test and 4 malformed cases.
  - M7: test_an_owner_row_for_the_role_alone_replaces_the_table_at_every_tier.
  - M39: test_the_haiku_floor_is_for_gates_only.
  - M42: 2 doctor row tests and 2 exit-code ok cases.
  - M43: the malformed "Haiku" case.
  - M44: 4 malformed cases.
  - M45: test_a_haiku_gate_is_advised_even_with_a_reason_or_a_models_row.
  - Y1 (a note counts as a warning): 2 exit-code ok cases.
  - Y3 (the floor reads the tier row only): the haiku-gate test and 4 malformed cases.
  - Y4 (the doctor rows dropped): 8 doctor cases.
  - Survived, each re-run alone in a fresh copy: Y2, X7 and X8 (1989 passed each).
- Red check: the head's tests/test_models.py on the 2c4e806 code gives 8 failed, 55 passed: 4 malformed floor cases, 2 row-status tests and 2 exit-code ok cases.
- Equivalence of the dropped `fam(allowed[0][0])`: ws.config (ws.py:68) keeps only a dict of string rows, and `named` reads the same raw dict for `<role> <tier>` and `<role>`. So every row that config keeps is in `named`. The TABLE setting for a sentinel never names Haiku (agents.py:19-23).
- Generated floor differential, 8607b51 against 78429d9 (tools/floor_diff.py through hook.handle): 9 row shapes x 4 call models x 3 roles = 108 cases, 24 moved. Every move is to the floor note, only for the two sentinels, and only where a raw row for that role names Haiku: a list, a table, the one word HAIKU, or a tier row of opus beside a role row of Haiku. Builder rows, a `lead` Haiku row and the no-row cases do not move. The tier-opus-plus-role-Haiku over-note is the PR's recorded assumption, which is advice only.
- Main-versus-head differential (specs/models-record/route_diff.py under the pytest venv python, main 5fe8347 against head 78429d9, one corpus). Corpus sha256 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0 is the same at main and head (sha256sum). Results:
  - Bash routes: 257, 0 moved.
  - Payloads: 8, 3 moved, the seat.started fields only.
  - Agent launches: 486, 290 moved, from none to additionalContext.
  - Permission decisions or updatedInput: 0.
  - 8607b51 against 78429d9: 751 cases, 0 moved.
- closed: the PR count of 40 mutants at 8607b51. It is now 44 of 44 claimed. Every doctor and floor mutant in that set was killed in my run above.
- Simplicity: none. The `named` line replaces `fam(allowed[0][0])` at the same length and is fail-closed validation of untrusted config, so it is not deletable. The `note` status is one word and reuses cmd_doctor's existing exit rule.
- Confidence high: I re-ran every kill and survivor at this head in fresh copies against the full suite. The survivors were re-run alone, so the timing tests could not mask them. The red check and both differentials reproduce.

## Residual risk
The floor's tier-row key, X7 and X8 are untested branches of an advice-only path. Timing-sensitive guard tests can hide survivors when mutant runs share a CPU.
