# Tasks: seat-rules

## Phase 1: Evidence first

- [x] T001 Branch from origin/main at 9d6701e
- [x] T002 Write the six tests in `tests/test_setup.py` and run them red: 6 failed, 29 passed

## Phase 2: Charter rules

- [x] T003 [US2] [US3] `_gate.md` rules 3 and 4 (FR-002, FR-003, FR-004, FR-006)
- [x] T004 [US2] `builder.md` VAL (FR-003, FR-006)
- [x] T005 [US4] `planner.md` Running the work 2 (FR-001)
- [x] T006 [US5] `steward.md` rule 4 (FR-005)

## Phase 3: Build and checks

- [x] T007 [US1] `bin/wuwei agents build` and `setup.vendor('.')` (FR-007)
- [x] T008 Full suite green; no file under `cli/` changed
- [x] T009 No emojis and no em dashes in the diff
