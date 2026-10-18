# Tasks: a gate is read from its verdict at the newest head on this PR

## Phase 1: Tests first

- [x] T001 [US1] An older ancestor's PASS attested after a FIX at the head leaves the gate owed (tests/test_evidence.py)
- [x] T002 [US2] A PASS at a non-ancestor head, for another PR of the item or another repository, does not count (tests/test_evidence.py)
- [x] T003 [US3] A FIX then a PASS at the same head leaves the gate owed (tests/test_evidence.py)
- [x] T004 Boundaries: an older FIX after a newer one, a PASS at a descendant, a repository-only PR line, case, a finding from another PR, the create door with no PR read
- [x] T005 Run the new tests red on main

## Phase 2: Implementation

- [x] T006 Share the #1135 walk as `newer` and read gate verdicts through it (cli/wuwei/evidence.py)
- [x] T007 Point guard fixtures that named another PR at the PR their door reads (tests/test_guards.py, tests/test_evidence.py)
- [x] T008 State the reading in docs/design.md
- [x] T009 Re-vendor .claude/wuwei with setup.vendor('.')
- [x] T010 Run the full suite green, runtime at or under 3,400 and within the item's budget of 5
- [x] T011 Run the history probe and the route corpus probe at main and at the head
