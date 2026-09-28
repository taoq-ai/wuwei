# Tasks: WUWEI morning plan

## Proposal

- [X] T001 Add failing tests for proposal content, validation and no state/worktree in `tests/test_plan.py`.
- [X] T002 Implement proposal validation and atomic files in `cli/wuwei/plan.py`.

## Approval

- [X] T003 Add failing tests for selected items, goals, CAP, policy, envelope and reservations in `tests/test_plan.py` and update existing state contract tests.
- [X] T004 Implement dedicated approval producer and CLI command in `cli/wuwei/plan.py`, `cli/wuwei/commands/plan.py`, `cli/wuwei/state.py` and `cli/wuwei/commands/event.py`.

## Carry-over

- [X] T005 Add failing tests for explicit prior-day import and `state.import` event in `tests/test_plan.py`.
- [X] T006 Implement prior-day import in `cli/wuwei/plan.py`.

## Skill and verification

- [X] T007 Add `skills/wuwei-plan/SKILL.md` with measured sweep, lead seat and morning gate steps.
- [X] T008 Run full pytest, inspect changed files for forbidden text and paths, and mark tasks complete.
