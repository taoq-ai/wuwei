# Tasks: a plan pass offers a goal as met when its date passed

## Phase 1: Tests first

- [x] T001 [US1] The pass offers a goal dated yesterday once, and not others (tests/test_plan.py)
- [x] T002 [US3] A no holds the goal until its date moves past the day of the no (tests/test_plan.py)
- [x] T003 [US2] A yes records goal.met G-2 and the report lists it (tests/test_hook.py, tests/test_report.py)
- [x] T004 [US4] Generated probe through guards.pre_tool and the hook (tests/test_hook.py)
- [x] T005 Run the new tests red (5 failed; probe 20,736 generated, 0 recorded)

## Phase 2: Implementation

- [x] T006 `view.goal_status` (cli/wuwei/view.py)
- [x] T007 The plan pass prints the due goals (cli/wuwei/__main__.py)
- [x] T008 The hook records goal.met rulings with a note (cli/wuwei/hook.py)
- [x] T009 The report lists met goals (cli/wuwei/report.py)
- [x] T010 Lead charter, run skill, design; `bin/wuwei agents build`; `setup.vendor('.')`
- [x] T011 Full suite green, runtime at 2,999

## Phase 3: Checks

- [x] T012 [US5] Route corpus at main and at the head: sha256 and every moved route
- [x] T013 Probe at main and at the head: generated, recorded, holes
- [x] T014 Mutants of each new condition in a scratch copy; strengthen the tests for each survivor
- [x] T015 [US2] Codex request_user_input path records the ruling (tests/test_codex.py)
