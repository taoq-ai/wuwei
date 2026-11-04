# Tasks: redteam-goal

## Phase 1: Tests first

- [x] T001 Worktree from origin/main b566362 on `redteam-goal`; runtime 3,879
- [x] T002 [US1] `tests/test_smart.py`: the trigger table (clear, complicated, in doubt, complex, owner, risky), docs alone on an owner path, and the rows that now add goal (risky rise, owner path, trust path, complex or unclassified, spec artifacts)
- [x] T003 [US2] `tests/test_charters.py`: the red-team agent, the trigger in every home, the goal row
- [x] T004 Red: `tests/test_smart.py` 14 failed, 60 passed; the three charter tests failed

## Phase 2: Implementation

- [x] T005 `evidence.needed`: goal on `deep or risky or in_doubt`, both runtime copies; runtime 0 net
- [x] T006 `charters/sentinel-goal.md` red team and goal duties
- [x] T007 `_common.md` Done, `lead.md` rule 3, `planner.md` goal row, `agents.TABLE`
- [x] T008 docs: design section 6, evidence page, models page, team page
- [x] T009 `bin/wuwei agents build`, `setup.vendor`

## Phase 3: Proof

- [x] T010 Green: the full suite
- [x] T011 `route_diff.py` at main and head (`route_diff.txt`)
- [x] T012 Smart tier tests crossed between main and head (`smart_cross.txt`)
- [x] T013 Mutants on both runtime copies, one at a time
