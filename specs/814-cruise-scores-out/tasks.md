# Tasks: delete cruise, calibration scores, budget classes and the shadow report

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at ac5403f.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files
named. Run each test task red before its code task. Pure deletions delete their tests with the
code. "Skip if already gone" marks code batches 1 and 2 delete.

## Phase 1: Routing is fixed in code (US1, P1)

- [X] T001 [US1] In `tests/test_decision_classes.py` add `test_stale_cruise_state_never_changes_a_route`:
  1. write `.wuwei/memory/cruise.json` with
     `{"levels": {"park": 0}, "changed": {}, "calibration": {"classes": [], "roles": ["builder"]}}`;
  2. save a Routine `park` record carrying `Role: builder` and route it: `(0, 'mandate')`;
  3. the `decision.decided` payload has `cisr == 'Routine'` and no `rule`, `level`,
     `undo_until` or `items`, and the record reads `Decided-by: mandate`;
  4. route a one-way record: its `decision_routes` row has no `thin` and no `uncalibrated`.

  Run: red. The stored uncalibrated role makes the payload `Exploratory`, and the route rows
  carry `thin`.
- [X] T002 [US1] In `tests/test_decision.py`:
  - add `test_classes_are_the_fixed_list`, which asserts `decision.CLASSES` is the 14-name
    tuple in order;
  - add `test_cruise_decided_by_is_refused`: `Decided-by: cruise park@L2` makes `evaluate`
    raise `ValueError` naming `Decided-by`;
  - add the Role lint lines of `tests/test_calibration_scores.py:65-72` as
    `test_role_is_an_optional_validated_field`;
  - delete `test_class_levels` (964-976).

  Run: red.
- [X] T003 [US1] `cli/wuwei/decision.py`: local `CLASSES`; `Decided-by` without the cruise
  form; `cisr` without `ambiguous`; delete `uncalibrated`; `route_owner` without `thin` and
  `uncalibrated` (plan.md). `cli/wuwei/commands/decision.py`: `decide`, `mandate`, `show`,
  `owner_outcome`, `undo` and the subparser help, per plan.md. `cli/wuwei/closing.py:194`.
  `cli/wuwei/workspace.py`: delete the `cruise` table and its checks.

## Phase 2: The seat mandate is a fixed rule (US2, P1)

- [X] T004 [US2] In `tests/test_brief.py`:
  - delete `test_mandate_follows_class_levels` (454-459);
  - add `test_the_mandate_is_fixed_by_autonomy`:
    - under `SUPERVISED`, `brief.mandate` holds `Decide and record: none.` and
      `decision records of class approach, retry`, carried from `test_cruise.py:583-591`;
    - under the default config plus `[decisions.cruise.levels]\napproach = 1\n` and a
      `memory/cruise.json` lowering `retry`, the text equals the default text.

  Run: red.
- [X] T005 [US2] `cli/wuwei/brief.py::mandate`: the fixed lists (plan.md). Run
  `tests/test_brief.py`: green, `test_builder_prompt_carries_the_mandate` unchanged.

## Phase 3: Nothing names cruise, scores, budgets or the shadow report (US3, P2)

- [X] T006 [US3] In `tests/test_signal_status.py`:
  - add a case: with `.wuwei/memory/cruise.json` holding `not json`, `wuwei status --line`
    exits 0 with no `cruise` token;
  - 140: drop `cruise` from the snapshot keys.

  Run: red.
- [X] T007 [US3] In `tests/test_workspace.py`:
  - drop the `cruise` dict from the defaults (256-258);
  - delete `test_decisions_config` (1216-1226);
  - add `test_a_cruise_table_only_warns`: a guarded config with `[decisions.cruise]\nmargin = 0.3\n`
    loads and `load_config(root, warnings=found)` names `decisions.cruise`.

  Run: red (the table is still known).
- [X] T008 [US3] Delete `cli/wuwei/cruise.py`, `cli/wuwei/calibration_scores.py`,
  `cli/wuwei/budget_classes.py`, `cli/wuwei/commands/cruise.py` and
  `cli/wuwei/commands/shadow.py`. Delete their tests with them:
  - `tests/test_cruise.py`, once T004 has its supervised assertion;
  - `tests/test_calibration_scores.py`, once T002 has its Role assertion;
  - `tests/test_budget_classes.py`.

  Then edit every importer per plan.md:
  - `promotion.py`, `steward.py`, `plan.py`, `commands/plan.py`, `report.py`, `retro.py`;
  - `commands/status.py`, `commands/why.py`, `watch.py`, `telemetry.py`, `profiles.py`;
  - `signal.py`, `commands/event.py`, `state.py`, `guards/protect_state.py`;
  - `commands/next.py`, `undo.py`.

  Skip if already gone: `commands/nudges.py`, `listen.py`, `commands/__init__.py`,
  `__main__.py`.
- [X] T009 [US3] Test edits that follow the deletions (plan.md, "Files to edit, tests"):
  - `test_plan.py` (delete the cruise card test);
  - `test_why.py`;
  - `test_report_retro.py:318`;
  - `test_signal_status.py:387-389`;
  - `test_state_allowlist.py` (62, 142, 143);
  - `test_telemetry.py` (79, 97);
  - `test_calibrate.py` (751-771);
  - `test_protect_state.py:607`;
  - `test_shadow.py` (delete `test_shadow_report_command`, new observe text);
  - `test_next.py:347`;
  - `test_e2e_day.py:282`;
  - `test_hooks.py` (376, 1090);
  - `test_undo.py` (the `taken` fixture, the seat case, 439).

  Skip if already gone: `test_invariants.py`, `test_remote.py`, `test_cli_known_command.py`,
  `test_nudge_hygiene.py`.
- [X] T010 [US3] Run `tests/test_decision.py tests/test_decision_classes.py tests/test_brief.py
  tests/test_workspace.py tests/test_signal_status.py tests/test_plan.py tests/test_why.py
  tests/test_report_retro.py tests/test_state_allowlist.py tests/test_telemetry.py
  tests/test_calibrate.py tests/test_protect_state.py tests/test_shadow.py tests/test_next.py
  tests/test_e2e_day.py tests/test_hooks.py tests/test_undo.py tests/test_steward.py
  tests/test_close_parked.py`: green. Add `tests/test_invariants.py tests/test_remote.py` if they
  still exist.

## Phase 4: Docs, charters, templates

- [X] T011 Docs per plan.md:
  - `docs/specs/2026-09-24-wuwei-design.md`: 5.2, 5.3, 5.4, 5.8, 5.8.1 replaced by "Decision
    classes", 5.9, telemetry, promote, and 9.2 skip if gone;
  - `docs/site/concepts.md`, `daily.md`, `reference.md`, `configuration.md`, `recovery.md`,
    `agent.md`;
  - `README.md` (39, 77, 115 principle 5, 171, 283-284) and `NOTICE` (110-118);
  - `templates/workspace/config.toml:285-296`.
- [X] T012 `tests/test_docs.py`:
  - delete `test_cruise_mode_ships`;
  - edit 605, 864, 1137, 1188 and 252;
  - principle 5 phrases and link, and the `range(556, 561)` loops (skip if #798 deleted
    them).

  Run `tests/test_docs.py tests/test_tone.py tests/test_charters.py`: green.
- [X] T013 `charters/_common.md:27` (5.8 class, no Role scoring), then `bin/wuwei agents
  build`. Run `tests/test_charters.py tests/test_agents.py`: green.

## Phase 5: Close

- [X] T014 Run the SC-002 grep:
  `grep -rniE 'cruise|calibration_scores|budget_classes|brier|error budget|shadow report|decision_shadows|undo_until|uncalibrated'`
  over `cli charters skills agents hooks templates scripts .github docs/site README.md NOTICE
  docs/specs/2026-09-24-wuwei-design.md`. Expect nothing. Under `tests/`, every hit is a stale
  file or key written to prove it is ignored.
- [X] T015 Remove imports left unused (`datetime` in `commands/status.py`, `re` in `why.py`
  if unused, `uuid4` in `promotion.py`). Run every test file touched in T001 to T013 once
  more. Leave the changes in the working tree, and record the RETIRED-at-rebase table in the
  PR body.

## Dependencies

- T001 to T003 before T008: `decision.py` stops importing cruise first.
- T004 and T005 before T008: `brief.py` stops reading levels.
- T002 and T004 before deleting the test files, since they carry the kept assertions.
- T011 to T013 after T008.
