# Tasks: gates-at-push

## Phase 1: Tests first

- [x] T001 Worktree from origin/main 470ab63 on `leone/1221`; runtime 3,551
- [x] T002 [US2-US4] tests: the board duty while CI runs, has not started or misses a required check, none on a red head (tests/test_watch.py); the ready door on a red, running and green head with the owner exception, the merge door on a red head (tests/test_guards.py); a verdict attested while CI ran (tests/test_hook.py)
- [x] T003 [US1] tests/test_charters.py: the builder, planner, `_way`, `_pr` and shepherd text
- [x] T004 Red at 470ab63's runtime: 41 failed (33 ready door routes, 8 board rows); the charter test failed at main's charters; the merge door and the attested-while-CI-ran tests pass at main and pin behaviour already held

## Phase 2: Implementation

- [x] T005 `board.compute`: the owed-gates duty skips only a `CI failing` head; text `orchestration: gates owed with no gate seat running`
- [x] T006 `guards.ready_door`: a draft's `CI failing` gap, less the owner's exception at that PR and head, is refused first, naming the checks
- [x] T007 charters (planner, builder, `_way`, `_pr`, shepherd), the watch skill, `bin/wuwei agents build`, the vendored copy, docs/design.md section 7 and the gate row, docs/site/concepts/evidence.md and doors.md
- [x] T008 Both runtime copies; runtime 3,554 (+3, the item's budget)

## Phase 3: Proof

- [x] T009 Green: the focused files, then the full suite
- [x] T010 `route_diff.py`: corpus sha256 de377966... at both trees; 288 routes x 4 hosts; 23 verdict or reason moves (21 red, 2 excepted, each to a ready refusal naming the failing checks), 68 note-text moves with no verdict change (`route_diff.txt`)
- [x] T011 6 mutants, applied to both runtime copies one at a time: 6 killed by behavioural tests
