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

## Phase 3: Gate round 1

- [x] T012 The site page and design.md state the reading, naming the create and ready doors (docs/site/concepts/evidence.md, docs/design.md)
- [x] T013 A test that the walk asks the code host about each pair of heads once, run red, then `gate_gaps` passes the verdict's own head to `newer` (tests/test_evidence.py, cli/wuwei/evidence.py)
- [x] T014 Count compare calls on long histories at main and the head and correct plan.md (specs/verdict-at-head/calls.py)
- [x] T015 Pin an imported 0.34 PASS counting for every PR of its item, and an imported short-head FIX holding against a PASS at that commit (tests/test_evidence.py)
- [x] T016 An arch `Breaking: no` from another PR clears no yes, run red, then the filter (tests/test_evidence.py, cli/wuwei/evidence.py)
- [x] T017 Merge origin/main, re-run the suite, the probes and the mutants

## Phase 4: Merge of main 5a33509 (#1166 Supersedes)

- [x] T018 Merge origin/main with a merge commit; resolve verdicts() (path and ref) and gate_gaps (the walk with the Supersedes rule inside it) once, then re-vendor
- [x] T019 A FIX at the head, then a PASS at the head naming it clears; without Supersedes, naming another item's file, at an older head, or for another PR it does not; run red before the rule (tests/test_evidence.py)
- [x] T020 An arch yes for another PR of the item at the head holds this PR (tests/test_evidence.py)
- [x] T021 The history probe gains a named-PASS family; re-run it, the route differential and seven mutants at main 5a33509 and the merged head
