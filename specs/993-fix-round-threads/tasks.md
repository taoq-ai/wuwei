# Tasks: Fix round threads and gate receipt

## User Story 1: Every owed thread

- [X] T001 [US1] Write and run failing multi-thread fix test in `tests/test_pr_actions.py`.
- [X] T002 [US1] Include all owed threads in `cli/wuwei/pr_actions.py` fix feedback.

## User Story 2: Active round feedback

- [X] T003 [US2] Write and run failing ready, running, and stop-race supplementary feedback tests in `tests/test_pr_actions.py`.
- [X] T004 [US2] Retain and deliver active round feedback in `cli/wuwei/pr_actions.py` and `cli/wuwei/commands/build.py`.

## User Story 3: Gate receipt

- [X] T005 [US3] Write and run failing stop receipt and wrong-round tests in `tests/test_dispatch.py`.
- [X] T006 [US3] Receive gate verdicts at stop and improve round errors in `cli/wuwei/guards/agent_launch.py` and `cli/wuwei/dispatch.py`.

## Validation

- [X] T007 Run every affected test file with explicit paths and record the last pytest summary in `specs/993-fix-round-threads/analysis.md`.
- [X] T008 Review scope, errors, diff, em-dashes and emojis in changed files.

## Reviewer fix round

- [X] T009 Write failing tests for completed, stale-prompt, held, recovered and parked feedback paths, plus corrected gate receipt.
- [X] T010 Deliver `pending_feedback` at every continuation and new-round entry point.
- [X] T011 Reuse one dispatch helper for stop-time and manual gate round selection.
- [X] T012 Run affected test files with the issue's interpreter and explicit paths.
