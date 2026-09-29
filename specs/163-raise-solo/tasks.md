# Tasks: Solo PR raise

## User Story 1: Worktree evidence

- [X] T001 [US1] Add failing brief and raise worktree tests in tests/test_shepherd.py
- [X] T002 [US1] Record worktree in cli/wuwei/brief.py and use it in cli/wuwei/shepherd.py

## User Story 2: Reviewer policy

- [X] T003 [US2] Add failing minimum and unmapped email tests in tests/test_shepherd.py
- [X] T004 [US2] Implement configurable reviewer minimum in cli/wuwei/workspace.py and cli/wuwei/shepherd.py

## User Story 3: Config and adapter

- [X] T005 [US3] Add failing none adapter and docs tests in tests/test_shepherd.py and tests/test_docs.py
- [X] T006 [US3] Update cli/wuwei/shepherd.py, templates/workspace/config.toml, and docs/site/configuration.md

## Verification

- [X] T007 Run full pytest suite and scan changed files for em-dashes and emojis

## Review fix

- [X] T008 Add a failing test for a worktree from another repository
- [X] T009 Refuse PR raise before reading HEAD when the worktree repository differs
