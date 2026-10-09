# Tasks: promote keeps owner-set keys, an answer promotes only its keys, and an empty list is written empty

Test first: each test task runs and fails for the expected reason before its implementation
task. Run only the touched test files (never the full suite). Tests use the `'"ask"'` TOML
form for `config set`.

## Phase 1: an empty list is written empty (US3, FR-005)

- [X] T001 Test in `tests/test_setup.py`: `test_empty_list_set_writes_empty`:
  `config set docs.publish '[]'` prints `+publish = []` and writes `publish = []`. Run:
  fails (`["report", "retro"]` written).
- [X] T002 Test in `tests/test_doctor.py`: `test_docs_publish_fix_runs_as_printed`: the
  markdown docs row is `warn`; its fix run as printed exits 0; the row is then `ok`. Run:
  fails (still `warn`).
- [X] T003 Implement FR-005 in `cli/wuwei/commands/setup.py` `merged`. Run T001, T002 and
  `tests/test_setup.py tests/test_config_writer.py`: green.

## Phase 2: promote skips a present key changed from its default (US1, FR-001, FR-002)

- [X] T004 Unit test in `tests/test_interview.py` for `calibrate.kept` next to the `settle`
  tests: a present `"ask"` with the setting `"send"` is skipped as
  `('outbound.default_tier', 'ask')`; an absent key, a key already equal and a deploy list
  holding every item are kept and not listed. Run: fails (`kept` missing).
- [X] T005 Implement `calibrate.kept`. Run T004: green.
- [X] T006 Tests in `tests/test_interview.py`:
  `test_promote_keeps_a_key_the_owner_set_after_the_answer` (item acceptance 1 and the
  `--keys` apply); update `test_interview_answers_apply_through_config_promote` for the
  present keys it now skips. Run: fails (overwrites `ask`; `--keys` unknown).
- [X] T007 Implement `proposal(keys=...)` and `promote --keys` in
  `cli/wuwei/commands/config.py`. Run T006, `tests/test_interview.py`,
  `tests/test_calibrate.py`, `tests/test_setup.py`, `tests/test_doctor.py`: green.

## Phase 3: `--keys` details and the Next line (US2, FR-003, FR-004)

- [X] T008 Tests in `tests/test_interview.py` (`offline` fixture, so any survey or port call
  fails): `test_answer_next_line_names_its_keys` (item acceptance 2, the promote it prints
  changes only those keys and writes no `calibration.json`);
  `test_charter_only_answer_names_only_promote`; `test_mixed_answers_name_both_steps`;
  `test_carded_answer_has_no_next_line`; `test_promote_keys_reports_unknown_and_nothing`
  (`Not in today's answers` exits 1; `No config.toml changes`, exit 0, never asks; `--keys` with
  `--measure` is `SystemExit` 2). Run: fails (old Next line).
- [X] T009 Implement the Next line in `cli/wuwei/commands/calibrate.py` `_interview`. Run
  T008, `tests/test_interview.py`, `tests/test_calibrate.py`: green.

## Phase 4: invariant row (FR-006)

- [X] T010 `i28`, `'I28'` in `INVARIANTS` and `READS`, the `BROKEN` entry in
  `tests/test_invariants.py`, and the I28 row in design 9.2. Run with `kept` broken to see
  I28 fail, then the whole file: green.

## Phase 5: docs and close (FR-007)

- [X] T011 `docs/site/configuration.md` where `config set` and `config promote` are
  described. Run `tests/test_docs.py` if it pins those paragraphs.
- [X] T012 Run the touched test files. Check no written file holds an em-dash, an emoji or
  an absolute local path, and that `git diff` touches nothing in `setup._from_card`,
  `configtext.py` or `doctor.py`.

## Phase 6: review fixes

- [X] T013 F1: test `test_answer_applies_over_a_shipped_default` (fresh-init
  `owner.verbosity.default = "brief"`, `verbosity=Full`, plain promote applies `full`) and
  `test_interview_answers_apply_through_config_promote` asserts no `Skipped` line; run:
  fails. `calibrate.kept` skips only a value other than the schema default
  (`configtext.declared`, `workspace._default`). Texts in the `kept` docstring, design I28
  and `docs/site/configuration.md`. Green.
- [X] T014 F2: `test_promote_keys_reports_unknown_and_nothing` expects exit 1 and the line
  with `bin/wuwei calibrate --questions`; run: fails. `promote --keys` prints the summary,
  writes nothing and exits 1 when a named key is missing. Green.
