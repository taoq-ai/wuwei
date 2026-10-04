# Tasks: config set writes list and table keys in any config.toml layout

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the task names. Signatures, texts and placement rules are in plan.md.
Fixtures: `TEMPLATE` and `REPO` from `tests/test_setup.py` (the interview template is
`TEMPLATE + REPO`), its `workspace` fixture, `Confirm` and `config_set` helpers. Neutral
fixture names only (`acme/widget`, `C1`, `U1`, `example.test`); no absolute local path in any
file; no em-dash, no emoji.

A shared oracle for the corpus tests, written once at the top of
`tests/test_config_writer.py`: `check(raw, text, path, key, value)` asserts
`tomllib.loads(text)` parses, the target equals `value`, `_preserves_values` holds for every
other value (target popped from the parsed `raw`), and every line of `raw` outside the written
span is still present in `text` in order.

## Serializer (FR-002)

- [X] T001 In `tests/test_config_writer.py` (new), add failing tests for `configtext.dumps`: for
  `"x"`, `'a "q" \\ b'`, a string with `\t`, `\x7f` and a non-BMP character, `True`, `0`, `-3`,
  `0.5`, `[]`, `["a", "b"]`, `[1, 2]`, `{}`, `{"login": "x"}`, `{"slack:U1": {"email":
  "a@example.test"}}`, `[{"pattern": "x", "channel": "slack"}]` and `[["a"], ["b"]]`,
  `tomllib.loads("v = " + dumps(value))["v"] == value`; a list of tables spans several lines and
  a list of strings is one line; `dumps(object())` raises `ValueError`. Fails today:
  `ModuleNotFoundError: wuwei.configtext`.
- [X] T002 Create `cli/wuwei/configtext.py` with `dumps` and `_key` (plan.md).

## Line model (FR-001)

- [X] T003 In `tests/test_config_writer.py`, add failing tests for `configtext.entries`: on
  `TEMPLATE + REPO` every header's path equals the path `tomllib` gives it (`[[repos]]` is
  `('repos', 0)`); `[ outward.max_length ]`, `[owner."verbosity"]` and `[boundary."release/*"]`
  resolve to their parts; a key spanning three lines has `end - start == 3`; a line `  [1, 2],`
  inside a multi-line array and a `[x]` inside a multi-line string are not headers; a CRLF
  file gives the same items as its LF twin; `[[repos]]` twice then `[repos.merge]` gives
  `('repos', 1, 'merge')`. Fails: `AttributeError: entries`.
- [X] T004 In `cli/wuwei/configtext.py`, add `PART`, `KEYS`, `_parts` and `entries` (plan.md).

## Placement: the owner's case and missing tables (FR-003, FR-004, FR-005; US1)

- [X] T005 In `tests/test_config_writer.py`, add failing tests:
  `test_template_tool_patterns`: `place(TEMPLATE + REPO, ('outward',), 'tool_patterns',
  [{'pattern': 'x', 'channel': 'slack'}])` passes `check`, and the key's line index is after
  `[outward]` and before `[outward.max_length]`;
  `test_missing_table_and_parents`: `telemetry.otlp.endpoint` on `TEMPLATE` writes `[telemetry]`
  then `[telemetry.otlp]` then the key, and passes `check`; `('repos', 0, 'merge')` on two
  repositories lands before the second `[[repos]]`; `('repos', 3)` on one repository raises
  `ValueError` naming `config add-repo`;
  `test_corpus` (parametrized, layouts x kinds): layouts are the template, `[outward]` followed
  by `[outward.max_length]`, a spaced header `[ outward.max_length ]`, a quoted header, an
  inline table, an array of tables, a missing section, trailing comments on every line, CRLF,
  and no trailing newline; kinds are a string (`owner.name` or the layout's string key), a
  list (`outbound.work_channels`) and a table (`outbound.people` with a `slack:U1` key); each
  result passes `check`, and a CRLF input yields no bare `\n` line ending. Fails:
  `AttributeError: place`.
- [X] T006 In `cli/wuwei/configtext.py`, add `place` rules 4 and 5 with table creation, the
  index refusal and line endings (plan.md).

## Placement: spans replaced in place (FR-003; US2)

- [X] T007 In `tests/test_config_writer.py`, add failing `test_span_*` tests: a three-line
  `reviewers = [` in `[shepherd]` is replaced whole (rule 1); `rotate_after = { turns = 200 }`
  becomes `rotate_after = {turns = 100}` for `('sessions', 'rotate_after')`, `turns` (rule 2);
  `repos = [{name = "acme/widget", path = "widget", default_branch = "main"}]` receives
  `merge_deploys = false` for `('repos', 0)` (rule 2); two `[[outward.tool_patterns]]` blocks
  become one block for a one-item list at the first block's place (rule 3); `[outbound.people]`
  with one key is rewritten for a two-key dict (rule 4); `merge.auto = false` under `[[repos]]`
  is replaced for `('repos', 0, 'merge')`, `auto` (rule 1, dotted). Each passes `check`. Fails:
  the rules are not there yet.
- [X] T008 In `cli/wuwei/configtext.py`, add `place` rules 1, 2 and 3 (plan.md).

## Every caller through the new placement (FR-006, FR-011)

- [X] T009 Change the two existing tests named in plan.md ("Tests that change"):
  `tests/test_interview.py::test_settle_turns_other_forms_into_hand_edits` becomes
  `test_settle_replaces_spans_and_dotted_keys` (both forms replaced, `edits == []`, value read
  back equal) and `tests/test_calibrate.py::test_boundary_candidates_and_inline_repos` expects
  the inline repository to receive `fast_checks`. In `tests/test_config_writer.py`, add a failing
  test that `calibrate.apply` of `outward.tool_patterns` on `TEMPLATE` succeeds, and that an
  unplaceable addition (a key under `[outward]` whose table `max_length` exists only as
  `max_length.slack = 1` dotted keys in `[outward]`, set as `('outward', 'max_length')`,
  `teams`) raises `ValueError` whose text starts with `outward.max_length.teams:` and contains
  `edit by hand`. Fails: `apply` still uses `json.dumps` and `settle` still returns edits.
- [X] T010 In `cli/wuwei/calibrate.py`, route `apply` through `configtext.place`, name the key in
  the `LAYOUT` refusal, drop the one-line gate from `settle` and delete `_assignment` (plan.md).
  Run `tests/test_calibrate.py tests/test_interview.py tests/test_setup.py tests/test_telemetry.py`;
  all green.

## One entry point, append mode, idempotence (FR-007, FR-008; US1 scenario 1, US3)

- [X] T011 In `tests/test_config_writer.py`, add failing tests for `setup.write_value`:
  `test_write_value_twice`: `write_value(write_value(t, k, v), k, v) == write_value(t, k, v)`
  for the template and `outward.tool_patterns`, `outbound.people`, `owner.name`; `mode='append'`
  on `outbound.work_channels = ["C1"]` with `["C1", "C2"]` gives `["C1", "C2"]` and a second
  append changes nothing; `mode='append'` on a string key raises naming `replace`; `mode='x'`
  raises; `deploy.deny` with `mode='replace'` still keeps present patterns. Fails:
  `AttributeError: write_value`.
- [X] T012 In `cli/wuwei/commands/setup.py`, add `_parts` and `write_value`, and make
  `set_value.change` call `write_value` (plan.md).

## config set end to end and the not-TOML refusal (FR-009; US1, US3, US4)

- [X] T013 In `tests/test_setup.py`, add failing tests: `test_owner_tool_patterns_on_template`
  (workspace `TEMPLATE + REPO`, `config_set('outward.tool_patterns', '[{pattern = "x", channel
  = "slack"}]', Confirm())` is 0, `load_config` reads the list back, one digest);
  `test_same_value_twice_is_byte_identical` (second run prints `No config.toml changes`, no
  digest, bytes equal); `test_not_toml_names_the_type` parametrized:
  `('outward.tool_patterns', '[{pattern: "x"}]', 'a list of tables', '[{pattern = "text", channel = "text"}]')`,
  `('cap', 'many', 'an integer', '1')`, `('owner.verbosity.default', 'standard', 'a string', '"brief"')`;
  each exits 1, no digest, file unchanged, stderr contains the key, the kind and the example.
  Fails: today's text is the decoder's message.
- [X] T014 In `tests/test_config_writer.py`, add failing tests for `configtext.declared` and
  `configtext.describe` on `cap`, `repos.0.merge_deploys`, `outward.tool_patterns`,
  `outbound.people`, `boundary.api` and an unknown key (`None`).
- [X] T015 In `cli/wuwei/configtext.py`, add `declared` and `describe`; in
  `cli/wuwei/commands/setup.py`, raise the typed refusal in `set_value.change` (plan.md). Run
  `tests/test_reasons.py`; green.

## config check: a key set in two tables (FR-010; US5)

- [X] T016 In `tests/test_config_writer.py`, add failing tests: `test_two_tables`:
  `misplaced` on `[outbound]\nwork_channels = ["C1"]\n[outward]\nwork_channels = ["C1"]\n`
  returns one line naming `work_channels`, `[outbound]`, `[outward]`, `line 2`, `line 4` and
  `remove line 4`; `[tracker]\nauto = []\n` plus a `[[repos]]` with `[repos.merge]\nauto =
  false\n` returns `[]`. In `tests/test_config_transition.py`, add
  `test_config_check_reports_two_tables` beside `test_config_check_prints_the_warning` (same
  `ws` fixture and code host fake): write
  `TEMPLATE.replace('[outward]\n', '[outward]\nwork_channels = ["C1"]\n')`; `config.run` prints
  `wuwei config check: work_channels is set in [outbound]` with both line numbers on stderr and
  returns 1. Fails: `AttributeError: misplaced`.
- [X] T017 In `cli/wuwei/configtext.py`, add `misplaced`; in `cli/wuwei/commands/config.py`,
  report it from `run` (plan.md).

## Docs and finish

- [X] T018 Update `docs/site/configuration.md` lines 3 and 310 (plan.md). Run
  `python -m pytest -q tests/test_docs.py`.
- [X] T019 Run the full suite with `python -m pytest -q`; all green. Grep the files touched for
  em-dashes, emojis and absolute local paths; remove any.
