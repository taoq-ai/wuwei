# Implementation Plan: unknown keys only warn, and init --upgrade removes the keys the schema no longer reads

**Branch**: `799-config-unknown-keys` | **Date**: 2026-10-11 | **Spec**: `spec.md`
**Input**: `specs/799-config-unknown-keys/spec.md`; deletion pass #789, PR 2.

## Summary

Delete the posture-dependent raise on unknown keys in `workspace.load_config`, and give
`init --upgrade` one function that removes every key or table `load_config` reports as unknown,
verified on the parsed result. No new module, no new config key, no new dependency.

## Technical Context

Stdlib-only Python 3.11+ (`tomllib`, `re`, `copy`). Tests with pytest, run with the pipeline
interpreter on the touched files only (#789 constraint); CI runs the suite. Every line number
below was read at bfbf6a3; verify before editing.

## Constitution Check

- I Stdlib only: yes (`tomllib`, `re`, `copy`, already imported in `init.py`).
- II Exit codes: an unsafe removal is `ValueError`, which `upgrade` already maps to exit 2
  (`UNRUN`), no writes.
- III One behaviour, one function: `_validate` stays the only judge of what is unknown;
  `init._unread_keys` only consumes its report.
- IV Test first: every behaviour change has a failing test before it (tasks.md).
- V Simplicity: about 50 lines in `init.py`, reusing `_sections` and the parse-and-compare
  check `_retired_mode` and `_migrated_config` already use.
- VII Security: guard refusals under `strict` are unchanged; the #496 `outbound.tiers` refusal
  stays. See spec Assumption 8.
- Workflow, invariant row: not applicable (spec Assumption 7).

## Units removed or changed, and their class

| Unit | Where | Class | Decision |
|---|---|---|---|
| Strict raise on unknown keys | `cli/wuwei/workspace.py:812-815` (`if unknown and posture(config)[0] == 'strict'` with the `integrity.newer_template` exception) | (a) A refusal over a key nothing reads. It stops no process error; it makes every deleted key a wall under `strict` and makes the model reason about config hygiene mid-task. | Delete. Its job (showing a typo) stays as the warning from `config check`, `doctor` and `init --upgrade`, now in every posture. |
| `init --upgrade` refusal on unknown keys | follows from the raise above (`upgrade` gets a `ConfigError`, exit 1) | (a) | Gone with the raise; replaced by removal. |
| `outbound.tiers` unknown-key raise (#496) | `cli/wuwei/workspace.py:733-734` | (b) A typo in a tier row widens it to match every outward send. | Keep in every posture. Its job moves to the exact `outward.allow` list in #789 PR 16. |
| Typo explains a later error | `cli/wuwei/workspace.py:724-727` (`if unknown: raise ConfigError(unknown[0])` inside `except ConfigError`) | Neither: an error message choice, not a refusal over the unknown key. | Keep. |
| `_retired_mode` (`guards.mode`) | `cli/wuwei/commands/init.py:265-289` | Value migration of a key the schema still reads. | Keep until #789 PR 15. |
| Newer-template exception | was inside the strict raise | (b) An older plugin must not delete a newer plugin's keys (data loss). | Moves to `init.upgrade`: no removal when `integrity.newer_template(config)`. |
| `hook.newer_template` event | `cli/wuwei/commands/hook.py:166-183` | Restart notice, not a refusal. | Unchanged. |

Coordinator change: `workspace.RETIRED = ()` next to `SCHEMA`; `_unread_keys` always removes a RETIRED key (or a key under a RETIRED table), near match or not.

Review fix round: `_unread_keys` keeps a dropped section's trailing comments, maps `[repos.merge]` to the latest `[[repos]]` entry and refuses on a TOML decode error; `merge.check` refuses an unknown key in the merge configuration that applies; template line 1 updated.

## Files to delete

None. Tests that pin the deleted raise are rewritten or deleted inside the files below.

## Files to edit

1. `cli/wuwei/workspace.py`
   - Delete lines 812-815 (the strict raise and its local `integrity` import).
   - `load_config` docstring: "Unknown keys refuse only under strict (#353); otherwise their
     texts are appended to warnings" becomes "Unknown keys never refuse (#799); their texts are
     appended to warnings".
2. `cli/wuwei/commands/init.py`
   - New `_unread_keys(raw, warnings)` next to `_retired_mode`, returning `(text, removed,
     kept)`. A warning with a `did you mean <near>?` hint goes to `kept` as `(key, near)` and
     is not removed (lead decision: a likely typo may be the owner's intended setting):
     - Paths: for each warning matching `config\.toml: unknown key (.+?)(?: at line \d+)?; `,
       with no near match, split the key on `.` and walk the parsed TOML from the root, turning a part into `int`
       where the node is a list. A walk that fails (`KeyError`, `ValueError`, `IndexError`)
       raises `ValueError` with the same text as the verification below.
     - Removal over `_sections(raw)`: a section's path is its label split on `.`, and for
       `[[name]]` it is `(*name.split('.'), n)` with `n` the occurrence index of that label.
       Drop a whole section whose path is, or starts with, a removed path. In a kept section,
       a line matching `^\s*([A-Za-z0-9_."' -]+?)\s*=` whose full path (section path plus the
       dotted key with quotes stripped) is, or starts with, a removed path is dropped together
       with the following lines until the dropped chunk parses with `tomllib.loads` (a value
       spanning lines).
     - Verification: `expected = copy.deepcopy(present)` with each path popped;
       `tomllib.loads(result) != expected` raises `ValueError('cannot safely remove <keys> in
       this TOML layout; delete them from config.toml by hand, then run bin/wuwei init
       --upgrade again')`.
     - `removed` is the list of dotted keys in report order.
   - `upgrade()`:
     - Keep the result of `workspace.load_config(destination.parent, raw=text, warnings=found)`
       (today discarded, line 362) as `config`.
     - After the warnings print loop: `pruned, removed, kept = (text, [], []) if
       integrity.newer_template(config) else _unread_keys(text, found)`, then feed `pruned`
       (not `text`) to `_migrated_config`. Do not reassign `text`: the `repos = []` line print
       (`if text != raw`) and `security.load(..., raw=text)` / `_guide(..., raw=text)` keep
       their meaning.
     - Print `for key in removed: print(f'{prefix} config.toml: remove {key} (no longer
       read)')` next to the `add {key}` lines, and for each kept key `config.toml: kept <key>,
       maybe a typo of <near>; fix it by hand` (no prefix, not a change, so `doctor` does not
       read it as template drift).
     - Add `and not removed` to the `No workspace changes needed` condition.
     - `config_changed = migrated != raw` already makes the write happen; nothing else.
3. `cli/wuwei/commands/config.py:64`: comment "#353: unknown keys warn below strict; the exit
   code ignores them." becomes "#799: unknown keys warn in every posture; the exit code
   ignores them."
4. `docs/site/configuration.md:3`: replace "under `security.posture = "strict"` they are
   errors, unless `template_version` is newer than the running plugin." with "in every
   posture. `wuwei init --upgrade` removes an unknown key that has no near documented key and
   keeps a likely typo for you to fix, unless `template_version` is newer than the running
   plugin."
5. `tests/test_workspace.py`
   - `test_unknown_key_line` (line 335 parametrize, 348): load with `warnings=found` under the
     appended `strict` posture and assert `config.toml: unknown key {key} at line {line};` is
     in `found[0]`. The two `repos` cases (`[[repos]]...pth = "b"` and the inline
     `repos = [...]`) still raise, because entry 1 lacks required fields and the typo explains
     it: move them to a separate parametrized `test_unknown_key_explains_a_later_error` that
     keeps the `pytest.raises` assertion. Comment at line 350 becomes "#799: unknown keys warn
     in every posture; appending keeps the line numbers."
   - `test_unknown_key_without_known_line` (357): assert on `found[0]` instead of a raise.
   - `test_owner_verbosity` comment at line 423: "warn below strict" becomes "warn in every
     posture".
   - Replace `test_upgrade_rejects_unknown_key_without_writes` (864) with
     `test_upgrade_removes_an_unread_key`: same fixture; `--dry-run` exits 0, prints
     `Would upgrade config.toml: remove owner.mystery (no longer read)`, every file
     byte-identical; then `init --upgrade` exits 0, prints `Upgraded config.toml: remove
     owner.mystery (no longer read)`, and the parsed `owner` table has no `mystery` and keeps
     `name` and `pronouns`.
   - `test_upgrade_warns_about_unknown_keys` (1287): also assert the `kept host.seatz, maybe a
     typo of host.seats` line and that `seatz = 3` is still in the file.
   - New `test_upgrade_refuses_an_unread_key_in_an_inline_table`: `owner = { ..., mystery = 1 }`
     exits 2, names `owner.mystery` and the hand fix, and changes no file.
6. `tests/test_config_transition.py`
   - `test_strict_refuses_the_unknown_key` (64) becomes `test_strict_warns_about_the_unknown_key`:
     `STRICT` loads and `found == ['config.toml: ' + WARNING.format(typo_line(STRICT))]`.
   - `test_strict_without_a_near_key_says_remove_it` (71): same text asserted in `found[0]`.
   - Delete `test_strict_tool_call_is_refused` (89); add `STRICT` to the parametrize of
     `test_tool_calls_pass_below_strict` (78-83), renamed `test_tool_calls_pass_in_every_posture`.
   - `test_same_version_template_still_refuses_under_strict` (217) becomes
     `test_same_version_template_records_no_event`: code 0, no deny, `newer_events(ws) == []`.
   - New unit tests of `init._unread_keys` (one parametrized test plus one refusal test):
     unknown key with a value over three lines; `foo.bar = 1` dotted at the root; `[gone]` with
     `[gone.sub]`; an unknown key in the second `[[repos]]`; each asserts the parsed result
     equals the old parse minus the reported keys and that `removed` names them (fixture keys
     have no near match). A likely typo (`host.seatz`) is returned in `kept` and the text is
     unchanged. Inline table `owner = { name = "a", mystery = 1 }` raises `ValueError` naming
     `owner.mystery`.
   - New `test_upgrade_keeps_keys_from_a_newer_template`: with the `newest` style fixture
     (`integrity.PLUGIN` at a fake `0.13.0` install) and a workspace whose
     `template_version = "0.14.0"` holds an unknown key, `init.upgrade` with `dry_run=True`
     prints no `remove` line. Build the workspace the way `test_stamp_*` and
     `tests/test_workspace.py::previous_workspace` do; reuse, do not add fixtures elsewhere.
7. `tests/test_config_failure.py::test_other_config_errors_have_no_repos_hint` (61): the input
   `nonsense = 1` under `strict` no longer errors; use `cap = true\n` and assert `cap` is in the
   message and the repos hint is not.
8. `tests/test_records_after_dryrun4.py::test_config_error_names_config_toml` (138): replace
   the parameter `'nonsense = 1\n[security]\nposture = "strict"\n'` with `'cap = true\n'`, an
   error in every posture, so the test still covers a non-repos config error.

## Verified fallout

A scratch copy with the raise deleted and a prototype of `_unread_keys` ran
`test_calibrate, test_config_failure, test_config_transition, test_decision, test_doctor,
test_drafts, test_hooks, test_intraday_intake, test_mcp, test_outbound, test_plan,
test_pr_guards, test_profiles, test_records_after_dryrun4, test_spec_mode, test_tracker,
test_watch, test_workspace, test_setup, test_posture, test_signal_status, test_config_writer,
test_integrity, test_reasons, test_e2e_day, test_docs`. The only failures were the tests named
in items 5 to 8, plus `test_setup.py::test_first_day_on_defaults_without_github_remote`, which
fails in the scratch copy with and without the change (it is not a signed install there) and
passes in the worktree. The prototype handled the multi-line, dotted, table-with-subtable and
`[[repos]]` cases and refused the inline table.

## Not touched

`cli/wuwei/commands/doctor.py` (its template row already reads the `--dry-run` lines),
`cli/wuwei/commands/hook.py`, `cli/wuwei/integrity.py`, charters, skills, `hooks/hooks.json`,
`.github`, `scripts/`, `templates/workspace/config.toml` (the template loads with no warnings),
the design spec (no section states the strict raise).
