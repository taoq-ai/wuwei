# Tasks: plan accuracy

## Phase 1: Tests first

- [x] T001 [US1] A wrong-shape candidates file (six shapes) exits 2 naming the shape and adds nothing (tests/test_plan.py)
- [x] T002 [US2] A changed promise or acceptance clears approval and the board shows "awaiting plan approval"; the same contract keeps it (tests/test_plan.py)
- [x] T003 [US3] `plan run` without `--reason` refuses and records nothing; with it the item carries the reason (tests/test_plan.py)
- [x] T004 [US4] `plan --help` has one line per action (tests/test_plan.py)
- [x] T005 Run the new tests red

## Phase 2: Implementation

- [x] T006 Validate the shape before adding in `add_from` (cli/wuwei/plan.py)
- [x] T007 Clear approval on a changed contract in `add` (cli/wuwei/plan.py)
- [x] T008 Refuse `run` without `--reason` (cli/wuwei/__main__.py)
- [x] T009 One actions table for choices and help (cli/wuwei/__main__.py)
- [x] T010 Run the full suite green

## Phase 3: Docs and vendor

- [x] T011 docs/site/reference.md names the shape, the approval rule and `plan run`
- [x] T012 Re-vendor `.claude/` with `setup.vendor('.')`
