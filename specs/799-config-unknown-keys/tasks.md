# Tasks: unknown keys only warn, and init --upgrade removes the keys the schema no longer reads

Test first: write each test task, run its file, see it fail for the expected reason, then do
the implementation task. Run only the touched test files with the pipeline interpreter
(`python -m pytest -q <files>`); CI runs the suite. Neutral fixtures only. Line numbers are
from bfbf6a3; verify before editing.

## Phase 1: unknown keys warn in every posture (FR-001, FR-002, US1)

- [X] T001 Rewrite the strict tests in `tests/test_config_transition.py`:
  `test_strict_refuses_the_unknown_key` becomes `test_strict_warns_about_the_unknown_key`
  (`STRICT` loads, `found == ['config.toml: ' + WARNING.format(typo_line(STRICT))]`);
  `test_strict_without_a_near_key_says_remove_it` asserts the same text in `found[0]`; add
  `STRICT` to the parametrize of `test_tool_calls_pass_below_strict`, renamed
  `test_tool_calls_pass_in_every_posture`, and delete `test_strict_tool_call_is_refused`;
  `test_same_version_template_still_refuses_under_strict` becomes
  `test_same_version_template_records_no_event` (code 0, no deny, no event).
- [X] T002 In `tests/test_workspace.py`: `test_unknown_key_line` asserts on the warnings under
  `strict`; move its two `repos` cases to `test_unknown_key_explains_a_later_error` (still a
  raise); `test_unknown_key_without_known_line` asserts on `found[0]`; update the comments at
  lines 350 and 423.
- [X] T003 Swap the inputs that relied on the strict raise for an error in every posture
  (`cap = true\n`): `tests/test_config_failure.py::test_other_config_errors_have_no_repos_hint`
  and the second parameter of
  `tests/test_records_after_dryrun4.py::test_config_error_names_config_toml`.
- [X] T004 Run `tests/test_config_transition.py tests/test_workspace.py` and see T001 and T002
  fail on the raise; T003 passes before and after (its inputs no longer depend on the raise).
- [X] T005 Delete the strict raise at `cli/wuwei/workspace.py:812-815` and update the
  `load_config` docstring. Keep the `outbound.tiers` raise (lines 733-734) and the
  typo-explains-the-error raise (724-727). Update the comment at
  `cli/wuwei/commands/config.py:64`.
- [X] T006 Run `tests/test_config_transition.py tests/test_workspace.py
  tests/test_config_failure.py tests/test_records_after_dryrun4.py`: T001 to T003 pass except
  `test_upgrade_rejects_unknown_key_without_writes`, which Phase 2 replaces.

## Phase 2: init --upgrade removes unread keys (FR-003 to FR-007, US2)

- [X] T007 Unit tests in `tests/test_config_transition.py` for `init._unread_keys(raw,
  warnings)`, with `warnings` from `workspace.load_config(root, raw=raw, warnings=found)`:
  parametrized over a key whose value spans three lines, `foo.bar = 1` at the root, `[gone]`
  with `[gone.sub]`, and `pth` in the second `[[repos]]` (each asserts
  `tomllib.loads(result)` equals the old parse minus the reported keys, and `removed` names
  them); a likely typo (`host.seatz`) is kept and returned in `kept`; `owner = { name = "a",
  mystery = 1 }` raises `ValueError` naming `owner.mystery`. An input with no unknown key
  returns the text unchanged and `[]`.
- [X] T008 In `tests/test_workspace.py`, replace `test_upgrade_rejects_unknown_key_without_writes`
  with `test_upgrade_removes_an_unread_key` (dry run prints `Would upgrade config.toml: remove
  owner.mystery (no longer read)` and changes no file; the upgrade prints `Upgraded
  config.toml: remove owner.mystery (no longer read)`, exits 0, and keeps `owner.name` and
  `owner.pronouns`); extend `test_upgrade_warns_about_unknown_keys` with the `kept
  host.seatz, maybe a typo of host.seats` line and the key still in the file; add
  `test_upgrade_refuses_an_unread_key_in_an_inline_table` (exit 2, no writes).
- [X] T009 In `tests/test_config_transition.py`, `test_upgrade_keeps_keys_from_a_newer_template`:
  plugin faked at `0.13.0`, workspace `template_version = "0.14.0"` with an unknown key,
  `init.upgrade(dry_run=True)` prints no `remove` line.
- [X] T010 Run `tests/test_config_transition.py tests/test_workspace.py` and see T007 to T009
  fail (no `_unread_keys`, no `remove` line).
- [X] T011 Add `_unread_keys` to `cli/wuwei/commands/init.py` and wire it into `upgrade()` as
  `plan.md` item 2 says (keep the `load_config` result as `config`, `pruned` not `text`, skip
  under `integrity.newer_template(config)`, the print line, `and not removed` in the no-change
  condition).
- [X] T012 Run `tests/test_config_transition.py tests/test_workspace.py tests/test_doctor.py
  tests/test_posture.py tests/test_hooks.py`: all pass.

- [X] T012a Add `workspace.RETIRED` and `test_a_retired_key_is_removed_despite_a_near_match`; `test_a_likely_typo_is_kept` covers the non-retired case.

- [X] T012b Review fixes F1 to F4: tests in `tests/test_config_transition.py` and `tests/test_merge.py` first, then `init._unread_keys`, `merge.check` and the template line.

## Phase 3: docs and close

- [X] T013 Correct the unknown-key sentence in `docs/site/configuration.md:3` as `plan.md`
  item 4 says; run `tests/test_docs.py`.
- [X] T014 Read the diff for emojis, em-dashes, absolute local paths and names; run every
  touched test file once more.
