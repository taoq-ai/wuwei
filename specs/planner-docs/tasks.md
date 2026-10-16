# Tasks: the planner reads tracker measures into the lead's brief

## Phase 1: Tests first

- [x] T001 [US1] Docs test: the plan skill reads tracker measures before launching the lead (tests/test_setup.py)
- [x] T002 [US2] Docs test: AGENTS.md and CONTRIBUTING.md name both suite commands (tests/test_setup.py)
- [x] T003 Run them red (`pytest -q tests/test_setup.py`: 2 failed, 20 passed)

## Phase 2: Implementation

- [x] T004 [US1] Add step 4 to skills/wuwei-plan/SKILL.md and renumber the later steps
- [x] T005 [US2] Add the `pytest -q` fallback to AGENTS.md and CONTRIBUTING.md
- [x] T006 [US3] Re-vendor .claude/ with setup.vendor('.')
- [x] T007 Run the full suite green
