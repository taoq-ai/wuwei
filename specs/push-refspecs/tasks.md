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

## Phase 4: Fix round 1 (gates at b16d799)

- [x] T014 Tests first: 27 real-git cases (16 from the main clone on main for option values and `--no-tags`, 11 for a dash refspec after `--` or `--end-of-options`, another worktree's HEAD and a symbolic ref); 26 red at b16d799, then `_flags` with `PUSH_VALUED`, the last of `--tags`/`--no-tags`, and the rev-parse name for a source alone; green
- [x] T015 Merged origin/main 7fd8f4b; vendored guards.py copied; spec, plan, design.md, doors.md and SECURITY.md updated; runtime 3,098 against 3,093 (+5)
- [x] T016 Route corpus: 4 rows added (sha256 a3ddc985...); through main 7fd8f4b's guard 11 rows move and 0 of main's 257; through b16d799's guard 4 rows move and 0 of its 269
- [x] T017 Probe (`probe.py <main tree> <head tree> <folder>`) with the gates' classes added: 21,282 generated, 21,254 ran git push, 80 holes at the head, all force digit clusters held at main too; 1,064 at main; 0 regressions
- [x] T018 Mutants of each rule, applied to both guards.py copies, one at a time, wall-clock tests excluded: each killed by a behavioural test

## Phase 5: Fix round 2 (gates at 9cb834a)

- [x] T019 Merged origin/main 5a33509, then dc9aad9; tests first: 7 valued rows from main (`--exec`, `--receive-pack`, `--rece`, `--recurse-submodules`, `--recu`), `--tags -n`, `-vd`, the ambiguous `origin`, two later end markers, and a push of 15,000 refspecs in under 1 s; 7 red at 9cb834a
- [x] T020 `_sources` reads the refs once per push; every candidate of git's ref rules counts; the first end marker only; the current branch read once; green, with rows for root refs, remote-tracking symbolic refs, a worktree id that is not its folder's name, a linked worktree's own HEAD, and a FIFO in the git directory
- [x] T021 Route corpus read through main, 9cb834a and the head; probe with the round 2 classes; the gates' probe re-run; non-door checks with the new shapes; mutants of each name set member and each candidate

## Phase 6: Fix round 3 (gates at aa63d3b)

- [x] T022 Merged origin/main 17ff289 with a plain merge; tests first: 18 real-git rows for the security gate's root ref forms and the words that stop rev-parse, `tag v1` as a pass row, a call-count test in place of the 1 s bound, a fail-shut test per ref read, a `--del` text row; 16 red at the merged round 2 guard
- [x] T023 `_sources(cwd, words)`: one `for-each-ref` and one batched `rev-parse --symbolic-full-name` (`core.warnAmbiguousRefs=false`, `--end-of-options`); `tag`, `^x`, globs and `--` out of the batch, `main-worktree/--` last; a read that cannot run or finish in 5 s refuses; the root file reader and `suppress` removed; green
- [x] T024 Spec, plan, analysis, checklist, SECURITY.md (reftable limit removed), design.md and doors.md (a push whose refs git cannot read in 5 s)
- [x] T025 Probe: rootfile (240) and stopper (194) classes; the whole probe, main 17ff289 against the head: 22,698 generated, 22,670 ran the push, 80 holes at the head (force digit clusters, the same at main), 1,420 at main, 0 regressions
- [x] T026 Route corpus through main, the merged round 2 guard and the head; mutants of each batch rule; non-door checks with round 3's push shapes; runtime 3,340 against 3,322 (+18)

## Phase 7: Fix round 4 (gates at 457f6a8)

- [x] T027 Merged origin/main 5b5084b with a plain merge, no conflict; tests first: w's own root `--` pushed from w (3 rows) and after cd, env -C, pushd, a subshell and an absolute cd from c (5 rows), all 8 red at the merged head; `feature:feature ZZ` for the colon-in-batch mutant
- [x] T028 A `--` refspec meets the door as `--all` does; the `main-worktree/--` lookup and the `--` batch exclusion go; green; the colon-in-batch and `--`-refusal mutants are killed
- [x] T029 Route corpus row `git push origin -- --`; the corpus read through main 5b5084b, the merged round 3 guard and the head; the probe's rootfile class plants `--` in the common folder and in w's, and the stopper class pushes w's `--` from each clone and after cd, env -C, pushd and a subshell; runtime 3,369 against 3,351 (+18)
