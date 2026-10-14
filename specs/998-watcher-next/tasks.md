# Tasks: Arm the PR stream watcher from next

## User Story 1: Watch PRs during other work

- [X] T001 [US1] Add failing tests for an open owned PR beside runnable work and as the sole runnable action in tests/test_next.py.
- [X] T002 [US1] Add failing Stop wake coverage for the missing watcher in tests/test_goal_refill.py.
- [X] T003 [US1] Implement watcher arming in the runnable set and safe resolution in cli/wuwei/commands/next.py.

## User Story 2: Keep one live watcher

- [X] T004 [US2] Add failing tests for a live watcher and terminal or absent PR in tests/test_next.py.
- [X] T005 [US2] Suppress duplicate watcher arming using existing live wait and PR listing in cli/wuwei/commands/next.py.

## Polish

- [X] T006 Update planner instructions in charters/planner.md and skills/wuwei-plan/SKILL.md.
- [X] T007 Run targeted and full explicit-file pytest, inspect the diff and check written files for em-dashes and emojis.
