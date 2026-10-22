# Tasks: 1230-own-diff-delta

## Phase 1: Tests first

- [x] T001 Worktree from origin/main fbf187b on `leone/1230`; runtime 3,373
- [x] T002 Fake host (tests/conftest.py): the REST PR's `base.sha`, a compare's `merge_base_commit` and each file's `patch`
- [x] T003 [US1, US2, US3] tests/test_evidence.py: the unchanged own diff, 13 own-delta rows (acceptance 2 and the brief's probes), the `Generated` line in 8 spellings, the 300-file cap, the head-to-head fallback with no base sha
- [x] T004 tests/test_guards.py: the merge door and the create door read a base merge on the own diff
- [x] T005 Red at fbf187b's runtime: 14 failed, 7 passed (then 1 more each for the 300-file cap and backticked globs)

## Phase 2: Implementation

- [x] T006 `gh.compare` keeps `patch`; `gh._summary` keeps `baseRefOid`
- [x] T007 `gate_gaps(..., base='')`: own patches at both heads, `@@` lines reduced, moved files, `Generated` lines, head-to-head line counts, 300-file fallback
- [x] T008 `gaps` and `create_door` pass the base; both runtime copies; runtime 3,381 (+8)
- [x] T009 docs/design.md, docs/site/concepts/evidence.md, docs/site/reference.md

## Phase 3: Proof

- [x] T010 Green: the new tests and the full suite
- [x] T011 `probe.py` under real git at fbf187b and the head: 26 generated, 26 read at both trees, 0 holes (`probe.txt`)
- [x] T012 `route_diff.py`: corpus sha256 de377966... at both trees; gap and fix hosts 0 of 288 move; the merge host 54 move, each from a security delta review to pass (`route_diff.txt`)
- [x] T013 18 mutants, applied to both runtime copies one at a time: 18 killed by behavioural tests
