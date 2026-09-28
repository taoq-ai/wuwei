# Tasks: Versioned charter upgrade

## Phase 1: Existing workspace migration

- [X] T001 [US1] Add a failing previous-template upgrade test in `tests/test_workspace.py` covering retained owner values, new keys and comments, pointer refresh, and charter conflict output.
- [X] T002 [US1] Implement config migration and charter comparison in `cli/wuwei/commands/init.py`.
- [X] T003 [US1] Add a failing repeat-upgrade test in `tests/test_workspace.py`.
- [X] T004 [US1] Make repeat upgrade idempotent in `cli/wuwei/commands/init.py`.

## Phase 2: Preview and refusal

- [X] T005 [US2] Add failing dry run and unknown-key tests in `tests/test_workspace.py`.
- [X] T006 [US2] Implement dry run and unknown-key refusal in `cli/wuwei/commands/init.py`.
- [X] T007 [US2] Add failing malformed, unreadable, and write-failure tests in `tests/test_workspace.py`.
- [X] T008 [US2] Implement fail-closed handling in `cli/wuwei/commands/init.py`.

## Phase 3: Verification

- [X] T009 Run focused and full pytest suites, review diff and hygiene.
- [X] T010 Add a regression test and preserve non-adjacent repository table order during upgrade.
