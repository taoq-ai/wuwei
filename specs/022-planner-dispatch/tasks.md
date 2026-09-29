# Tasks: Planner dispatch and receive

## User Story 1

- [X] T001 [US1] Test gate dispatch and refusal decisions in tests/test_dispatch.py
- [X] T002 [US1] Implement gate dispatch decisions in cli/wuwei/dispatch.py and cli/wuwei/commands/dispatch.py

## User Story 2

- [X] T003 [US2] Test verdict receive, fix, delta, residual and escalation in tests/test_dispatch.py
- [X] T004 [US2] Implement receive decisions and state recording in cli/wuwei/dispatch.py
- [X] T005 [US2] Test delta evidence accepted by pre-PR and merge policies in tests/test_pr_guards.py and tests/test_merge.py
- [X] T006 [US2] Reuse recorded verdicts in cli/wuwei/guards/pr.py and cli/wuwei/merge.py

## User Story 3

- [X] T007 [US3] Test sweep and seat-free discovery signals in tests/test_dispatch.py and tests/test_watch.py
- [X] T008 [US3] Implement discovery trigger in cli/wuwei/dispatch.py and existing sweep path

## Verification

- [X] T009 Run the full pytest suite and hygiene checks
