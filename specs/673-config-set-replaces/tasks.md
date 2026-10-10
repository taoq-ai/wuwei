# Tasks: config set on a list key replaces the list, and says so; adding to a list is the explicit --add

Test first: each test task runs and fails for the expected reason before its implementation
task. Run only the touched test files while building; the full suite at the end.

## Phase 1: replace by default, --add to add (US1, US2, FR-001, FR-002)

- [X] T001 Tests in `tests/test_setup.py`: the `config_set` helper gains `add=False` and
  passes `add` in its `SimpleNamespace`. New `test_list_set_replaces` (issue acceptance 1:
  `TEMPLATE + REPO` with `fast_checks = ["make lint", "make test"]`,
  `config set repos.0.fast_checks '["x"]'` writes `["x"]`, and with `replace=True` the same).
  New `test_list_set_add_once` (issue acceptance 2: `add=True` twice on
  `outbound.work_channels`, `C1` appears once, the second run prints
  `No config.toml changes`; `add=True` with `'[]'` writes nothing). Update
  `test_list_set_appends`, `test_table_set_adds_entries` and `test_config_show_tags` to pass
  `add=True`. Replace `test_replace_refused_on_scalar` with `test_add_refused_on_scalar`
  (`--add` on `owner.verbosity.default` exits 1, names `--add`, writes nothing, asks no
  digest) and assert `replace=True` on that scalar writes it. Run: fails (append default,
  no `add`).
- [X] T002 Test in `tests/test_setup.py`: `main(['config', 'set', 'outbound.work_channels',
  '["C1"]', '--add', '--replace'])` raises `SystemExit` 2. Run: fails (`--add` unknown).
- [X] T003 Implement in `cli/wuwei/commands/config.py` (`register`: `--add` and `--replace`
  in one mutually exclusive group, help texts) and `cli/wuwei/commands/setup.py` (`merged`
  with `add`, `set_value` passes `add`). Run T001, T002, `tests/test_setup.py`,
  `tests/test_config_writer.py`: green.
- [X] T004 Run `tests/test_outbound_learn.py`: fails on learned channels replacing the list
  (`['C1', 'C01']` expected). Implement `add=True` in `cli/wuwei/commands/outbound.py:419`.
  Run: green.

## Phase 2: the replaced or added line (US1, US2, FR-003)

- [X] T005 Tests in `tests/test_setup.py`: `test_list_set_replaces` asserts the line
  `replaced: repos.0.fast_checks = ["x"] (was ["make lint", "make test"])` after
  `Applied the change`; `test_list_set_add_once` asserts a line starting
  `added: outbound.work_channels = ` that ends with the previous value in `(was ...)`;
  `test_one_value_lands_after_its_digest` asserts
  `replaced: owner.verbosity.default = "standard" (was "brief")` and no line on the
  `No config.toml changes` rerun; new `test_deploy_list_line_says_added`
  (`config set deploy.deny '["npm publish*"]'` over `deny = ["make deploy*"]` writes both and
  prints `added: deploy.deny = ["make deploy*", "npm publish*"] (was ["make deploy*"])`).
  Run: fails (no line).
- [X] T006 Implement `calibrate.grows` (extracted from `settle`, which calls it) in
  `cli/wuwei/calibrate.py`; `setup.changed` and the `keys`/`add` parameters of `setup._edit`
  in `cli/wuwei/commands/setup.py`; `set_value` passes `keys=[args.key]` and `add`. Run T005,
  `tests/test_setup.py`, `tests/test_config_writer.py`, `tests/test_calibrate.py`: green.

## Phase 3: the card writers print the same line (US3, FR-004)

- [X] T007 Tests in `tests/test_card_confirms.py`: `test_config_set_from_a_decision_card`
  asserts a `replaced: cap = 5 (was ` line on the first write and none on the
  `No config.toml changes` rerun; `test_calibrate_takes_the_detected_checks_under_mandate`
  asserts `replaced: repos.0.fast_checks = ["make test"] (was [])` in stderr;
  `test_calibrate_answer_writes_the_card_answer` asserts a `replaced: <key> = ` line for its
  key. Run: fails (no line).
- [X] T008 Implement: `card_write` in `cli/wuwei/commands/setup.py` passes `keys=keys` to
  `_edit`. Run T007, `tests/test_card_confirms.py`, `tests/test_interview.py`: green.

## Phase 4: docs and close (FR-005)

- [X] T009 `docs/site/configuration.md` (the `config set` paragraph at line 336 and the
  `outward.tool_patterns` row at line 415) and the `tool_patterns` comment in
  `templates/workspace/config.toml` (line 190). Run `tests/test_docs.py` and any template
  test that pins the file: green.
- [X] T010 Run the full suite. Check the written files for em-dashes, emojis and absolute
  local paths, and that `git diff` leaves `write_value`, `_from_card`, `config.offer` and
  the `settle` behaviour unchanged.
