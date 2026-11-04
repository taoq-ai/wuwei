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

- [x] T010 Green: the full suite at the head, 4,441 passed and 7 skipped (a first run failed 3 `tests/test_models.py` advice rows that used the goal row; they moved to sentinel-arch and Fable)
- [x] T011 `route_diff.py` at main and head (`route_diff.txt`): corpus sha256 de377966..., 288 routes, 2,304 cases, 171 moved, all on the complex, owner and risky hosts (57 each), each adding goal alone
- [x] T012 Smart tier tests crossed between main and head (`smart_cross.txt`): head tests on main fail 14, main tests on head fail 11, each by goal added on a named trigger
- [x] T013 Mutants on both runtime copies, one at a time: 9 of 9 killed by behavioural tests in `tests/test_smart.py` (drop complex, drop owner or risky, drop in doubt, goal at standard, owner paths only, risky pattern only, complex and risky together, goal on any smart code, drop the smart guard)
