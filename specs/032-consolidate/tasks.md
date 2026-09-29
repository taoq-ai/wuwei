# Tasks: Consolidation

## Phase 1: Weekly review

- [X] T001 [US1] Write failing finding tests in `tests/test_consolidation.py`.
- [X] T002 [US1] Implement findings in `cli/wuwei/consolidation.py` and `cli/wuwei/commands/consolidate.py`.

## Phase 2: Safe fold

- [X] T003 [US2] Write failing snapshot and survivor tests in `tests/test_consolidation.py`.
- [X] T004 [US2] Implement snapshot before fold in `cli/wuwei/promotion.py`.

## Phase 3: Old days

- [X] T005 [US3] Write failing 35-day, index, commit and guard tests in `tests/test_consolidation.py`.
- [X] T006 [US3] Implement archive producer, config and skill in `cli/wuwei/consolidation.py`, `cli/wuwei/workspace.py`, `adapters/vcs/git.py`, `templates/workspace/config.toml` and `skills/wuwei-consolidate/SKILL.md`.

## Phase 4: Verification

- [X] T007 Run full pytest suite and inspect changed files for local paths, em-dashes and emojis.

## Phase 5: Review fixes

- [X] T008 Add regressions for regenerated indexes, invalid unrelated notes and missing changelogs.
- [X] T009 Preflight note indexes before folds and archives, and accept regenerated indexes.
- [X] T010 Remove the historical rule checker and its configuration, adapter operation and documentation.
