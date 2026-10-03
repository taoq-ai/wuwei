# Tasks: First-day docs after the fix wave (#340)

Test first: run each test task, see it fail for the stated reason, then do the page task
that follows it. Run tests with `python -m pytest -q tests/test_docs.py` from the repository
root using the interpreter the task names. Exact test code, wording and placement are in
plan.md. Humanizer checklist on every new sentence; no em-dashes, no emojis.

## Setup

- [X] T001 Run `python -m pytest -q tests/test_docs.py` in the worktree: 42 passed. Read the owner's trial report (path in the orchestrator notes) for the nine symptoms; write none of its client, repository or host names into the repository.

## US1: the first day reads as one path

- [X] T002 [US1] In `tests/test_docs.py`, extend `test_readme_first_day_and_shipped_areas` (plan.md test 1): steps `('setup --shadow', 'bin/wuwei doctor', '/wuwei plan')`, plus the three new What ships today links. Run it: fails, `'bin/wuwei doctor'` not in the README Quick start.
- [X] T003 [US1] In `README.md`, add the doctor step to Quick start after the `--shadow` paragraph and the setup, doctor and security posture bullets to What ships today (plan.md). In `docs/site/index.md`, add the doctor step to Start here before `/wuwei plan` and update the Recovery line in the page list. Run T002: passes.
- [X] T004 [US1] In `tests/test_docs.py`, add `'setup --shadow'` and `'observe'` to the Limits phrases of `test_readme_lead_and_limits` (plan.md test 2). Run it: fails, Limits has neither.
- [X] T005 [US1] In `README.md` Limits, add the first-week observe bullet linking `docs/site/security.md#security-posture`. Run T004: passes. Run `test_readme_compares_with_other_tools`, `test_release_asset_ships_every_linked_doc` and `test_entry_guides_install_signed_release_and_explain_development_checkout`: still pass.

## US2: troubleshooting maps each trial failure to its fix

- [X] T006 [US2] In `tests/test_docs.py`, add the `TROUBLESHOOTING` tuple and `test_troubleshooting_covers_the_first_run_findings` (plan.md test 3). Run it: fails with IndexError, no `## Troubleshooting` in `recovery.md`.
- [X] T007 [US2] In `docs/site/recovery.md`, replace the doctor paragraph (lines 14-16) with `## Troubleshooting` and its nine `###` entries in plan.md order. Run T006: passes. Run `test_daily_path_and_recovery_pages` and `test_security_integrity_and_cross_links`: still pass (the section contains the word "recovery").

## US3: the daily path and config page use config set

- [X] T008 [US3] In `tests/test_docs.py`, extend `test_doctor_is_the_first_stop` (plan.md test 4). Run it: fails, `bin/wuwei doctor` is not in daily.md section 1.
- [X] T009 [US3] In `docs/site/daily.md`, move the doctor sentence from section 2 to the end of section 1 with a link to `recovery.html#troubleshooting`; replace the posture switch (lines 73-75) and the Long sessions closing sentence (lines 184-185) with the `bin/wuwei config set` lines. In `docs/site/configuration.md` line 9, replace "Edit it in the workspace root." with the `config set` / `config add-repo` sentence. Run T008: passes. Run `test_daily_long_sessions_section`, `test_calibration_is_documented_between_configure_and_plan` and `test_daily_path_and_recovery_pages`: still pass.

## US4: the posture table cannot drift from the code

- [X] T010 [US4] In `tests/test_docs.py`, add `test_security_posture_table_matches_the_code` (plan.md test 5). Run it: passes (a pin over correct text). In `docs/site/security.md`, change the `seats` guarded cell to `block` locally, run it, see it fail on the table comparison, and restore the cell. No committed change to `security.md`.

## Finish

- [X] T011 Run the full suite with `python -m pytest -q`: everything passes, and no existing assertion in `tests/test_docs.py` was removed or loosened.
- [X] T012 Check every changed file for em-dashes (U+2014), emojis, absolute local paths and the trial report's client, repository and host names; remove any. Confirm `git status` lists only `README.md`, `docs/site/index.md`, `docs/site/daily.md`, `docs/site/recovery.md`, `docs/site/configuration.md`, `tests/test_docs.py` and `specs/340-docs-first-day/`.
