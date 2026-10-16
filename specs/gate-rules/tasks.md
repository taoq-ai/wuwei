# Tasks: gate-rules

## Phase 1: Evidence first

- [x] T001 Baseline suite at e34586d in a scratch copy: 931 passed, 2 skipped
- [x] T002 Re-check the cited lines at e34586d: `_gate.md:46`, `verdict.py:12,49`, `reference.md:79`, `hook.py:90-91`
- [x] T003 Write the three tests and run them red: 6 failed

## Phase 2: Wording and rules

- [x] T004 [US2] `verdict.py` FORMAT and PR error, `_gate.md` and `reference.md` template (FR-008)
- [x] T005 [US3] `hook.py` Stop line, two lines for two (FR-008)
- [x] T006 [US1] `_common.md` and `_gate.md` rules (FR-001 to FR-004)
- [x] T007 `sentinel-security.md`, `builder.md` (FR-005, FR-006)
- [x] T008 [US5] `lead.md`, `planner.md` (FR-007)

## Phase 3: Build and checks

- [x] T009 [US1] `bin/wuwei agents build` and `setup.vendor('.')` (FR-009)
- [x] T010 [US4] Full suite green; `wc -l cli/wuwei/*.py` still 3,000
- [x] T011 No emojis and no em dashes in the diff
