# Tasks: the push door reads each refspec's destination the way git does

## Phase 1: Real execution and tests first

- [x] T001 Worktree from origin/main dc39cae on fix/push-refspecs; runtime 3,011
- [x] T002 guards.bash on dc39cae passes `feature:heads/main`, `:`, `--all` (either order), quoted, double-quoted and backslashed globs, `heads/main`, `:/x:main`, `--mirr`, `--m`, `--al` and `--branches`
- [x] T003 [US1, US2, US3] Tests in tests/test_guards.py: real git on a scratch bare remote moves main (or leaves it) and the door, with the remote read as non-scratch, refuses (or passes); unit cases for `--branches`, `--bra`, `+:`, `refs/heads/m*`, `--delete heads/main`; reason text. 22 red on dc39cae's guard, 10 already green (the pass cases and the spellings main refused)

## Phase 2: Implementation

- [x] T004 `git_push`: the last colon, git's ref rules for a destination, a glob as a full-name pattern, `:` as `*`, `--all` and `--branches` prefixes, `--mirror` prefixes
- [x] T005 Tests green; vendored guards.py copied; design.md and doors.md name the spellings
- [x] T006 Route corpus: 12 rows added; main's 257 routes read the same at the head; 8 new rows move (pass on main, push at the head)
- [x] T007 Generated probe `specs/push-refspecs/probe.py` at the head: 6 holes, all `@` from a clone on main; and `--tags` alone refused on main
- [x] T008 Tests first for both (4 cases, red), then `@` read as `HEAD` and `--tags` alone adding no current branch; green

## Phase 3: Proof

- [x] T009 Rebased on origin/main 6682925; guards.py unchanged there; runtime 3,027 against 3,026 (+1)
- [x] T010 Probe at the head: 6,398 generated, 6,370 ran git push, 0 holes; at main 6682925: 502 holes
- [x] T011 Route corpus at main 6682925 (sha256 9e099867...) and the head (sha256 3c80e7c1...): 0 of 257 move; 8 of the 12 new rows move
- [x] T012 Mutants of each rule, applied to both guards.py copies, one at a time: each fails tests in tests/test_guards.py
- [x] T013 Full suite green at the head
