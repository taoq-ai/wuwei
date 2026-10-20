# Tasks: the one-way ADR note follows the repository's own ADR home

## Phase 1: Tests first

- [x] T001 [US1, US2] The note names the three homes and the amend rule, not the repository's docs/adr/ (tests/test_hook.py)
- [x] T002 [US3] The planner charter states the rule and the arch charter names no docs/adr/ (tests/test_charters.py)
- [x] T003 Run the new tests red

## Phase 2: Implementation

- [x] T004 The note text (cli/wuwei/hook.py)
- [x] T005 The planner bullet (charters/planner.md)
- [x] T006 The arch charter line (charters/sentinel-arch.md)
- [x] T007 Run the full suite green, runtime at 3,400 or fewer

## Phase 3: Docs and checks

- [x] T008 `bin/wuwei agents build`; the arch agent at or under 2,250 words
- [x] T009 docs/site/concepts/decisions.md and index.md
- [x] T010 Re-vendor .claude/ with setup.vendor('.')
- [x] T011 Route corpus on main and the branch
