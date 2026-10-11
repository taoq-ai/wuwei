# Tasks: delete the undo door, undo rehearsal and novelty

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at ac5403f.
Part 9 (#814) is done on this branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, naming only the
files listed. Run each test task red before its code task. Pure deletions delete their tests
with the code. "Skip if already gone" marks code that batches 1 and 2 delete.

## Phase 1: The written door stands (US1, P1)

- [X] T001 [US1] Delete the autouse `rehearsed_undo` fixture (`tests/conftest.py:37-44`).
  Add two tests:
  - `tests/test_decision_classes.py::test_the_written_door_stands`: with no ledger, a two-way
    `approach` record routes `(0, 'mandate')`. The record text keeps `Reversibility:
    two-way` and has no `Reversibility corrected`.
  - `tests/test_decision.py::test_lint_prints_no_door_correction`: a two-way `message`
    record linted with a workspace root prints exactly one line, starting `OK:`.

  Run: red. The correction lowers the door, and the lint prints a second line.
- [X] T002 [US1] `cli/wuwei/commands/decision.py`: delete the `undo.correct` call in
  `decide` and the `said` suffixes. `cli/wuwei/decision.py`: delete the #557 block in
  `lint`, and `lint(text, lenses=LENSES)` drops `root` (update `lint_file`).
- [X] T003 [US1] Run `tests/test_decision.py tests/test_decision_classes.py` in full. Any test
  that expected `owner` only because of the correction was a test of the deleted rule:
  delete it, or change its record to one-way where its subject is another rule. Record each
  such change in the PR body. Expect green.

## Phase 2: A new target asks nothing extra (US2, P1)

- [X] T004 [US2] Add `tests/test_decision_classes.py::test_a_new_target_routes_like_a_known_one`:
  a Routine record whose Context names `repo:acme/new` routes `(0, 'mandate')`, prints no
  `first time for` line, and leaves `.wuwei/memory/targets.json` unwritten. Run: red.
- [X] T005 [US2] Remove every novelty caller per plan.md:
  - `commands/decision.py`: `mandate`, `show`, `owner_outcome`, `template`, the import;
  - `decision.route_owner`;
  - `grants.gate` and `active`;
  - `outward.py:804-815`;
  - `drafts.py:331-335`;
  - `commands/why.py`;
  - `report.py`;
  - `commands/init.py` seed.

  Then delete `cli/wuwei/novelty.py` and `tests/test_novelty.py`. Edit `tests/test_outward.py`
  (`familiar` and its calls) and `tests/test_hooks.py:1090`.
- [X] T006 [US2] Run `tests/test_decision_classes.py tests/test_decision.py tests/test_outward.py
  tests/test_drafts.py tests/test_why.py tests/test_hooks.py tests/test_grants.py`: green.

## Phase 3: Nothing names undo, rehearsal or novelty (US3, P2)

- [X] T007 [US3] Tests first:
  - `tests/test_next.py`: delete `test_unrehearsed_undos_are_run_rows_before_the_cards`
    (778-797) and add `test_no_rehearse_row`.
  - `tests/test_workspace.py`: add `test_upgrade_removes_retired_memory_files` (plan.md), and
    drop the `Undo not rehearsed` filters (1321, 1338).
  - `tests/test_cli.py`: add a case where `main(['undo', 'D-1'])` and
    `main(['decision', 'undo', 'D-1'])` raise `SystemExit` with code 2.

  Run: red.
- [X] T008 [US3] Code:
  - `commands/next.py:214-222`;
  - `commands/init.py`: delete `Undo not rehearsed`, add `RETIRED_FILES` and the removal;
  - `commands/doctor.py`: `_undo` and the `_unrecorded` exclusion;
  - `commands/decision.py`: the `undo` subparser, function and `run` branch;
  - `merge.py`: the journal `undo` and its two calls, and the docstring;
  - `report.py`: the undo sections;
  - `event.py:102`, `signal.py:27`, `registry.py:63`;
  - `adapters/vcs/git.py`: the rehearsal case, `_scratch` and `rehearse_revert`;
  - `guards/protect_state.py`: 402, 404, 435-440.

  Then delete `cli/wuwei/undo.py`, `cli/wuwei/commands/undo.py` and `tests/test_undo.py`.
  Skip if already gone: `commands/__init__.py`, `__main__.py`, `remote.py`.
- [X] T009 [US3] Test edits that follow the deletions:
  - `test_doctor.py` (315, 616-625, 1424-1437);
  - `test_protect_state.py` (1109-1120, 1135-1146);
  - `test_report_retro.py` (318, 482-507);
  - `test_merge.py` (420-431, 578, 718-720, 842-844, 996);
  - `test_vcs.py` (494-505);
  - `test_adapters.py:83`;
  - `test_signal_status.py:388`;
  - `test_calibrate.py` (1320, 1328).

  Skip if already gone: `test_invariants.py` (I22, I23, I33) and `test_remote.py`.
- [X] T010 [US3] Run `tests/test_next.py tests/test_workspace.py tests/test_cli.py
  tests/test_doctor.py tests/test_protect_state.py tests/test_report_retro.py tests/test_merge.py
  tests/test_vcs.py tests/test_adapters.py tests/test_signal_status.py tests/test_calibrate.py
  tests/test_state_allowlist.py`: green.

## Phase 4: Docs

- [X] T011 Edit the design spec (4.6 journal wording, 5.8 measured reversibility, the Novelty
  paragraph; 9.2 rows skip if gone) and `docs/site/concepts.md`, `daily.md`, `reference.md`
  and `agent.md`, per plan.md. In `tests/test_docs.py`, edit 30 and 148 (skip if gone). Run
  `tests/test_docs.py tests/test_tone.py`: green.

## Phase 5: Close

- [X] T012 Run the SC-002 grep. The only hits allowed are the release rehearsal files and
  `RETIRED_FILES`.
- [X] T013 Drop imports the deletions left unused (`re` in `drafts.py`, `sys` in
  `commands/decision.py` if unused). Run every test file touched in T001 to T011 once more.
  Leave the changes in the working tree.

## Dependencies

- T001 and T002 come before T005, because `decision.py` and `commands/decision.py` lose
  their undo import first.
- T005 comes before T008, because `undo.measured` imports novelty and both modules go.
- T011 comes after T008.
