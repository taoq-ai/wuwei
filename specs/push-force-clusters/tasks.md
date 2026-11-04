# Tasks: a force push in a short option cluster meets the push door

## Phase 1: Real execution and tests first

- [x] T001 Worktree from origin/main a53405f on fix/push-force-clusters; runtime 3,879
- [x] T002 Real git 2.54 on a diverged remote: `-4f`, `-f4`, `-6f`, `-qf6`, `-4vf`, `-uf`, `-df`, `-fo=x` and `-fo.x` move the ref; `-of`, `-o-f`, `-4` and `-q` do not; `-fx`, `-xf`, `-Vf` and `-4-f` exit 129
- [x] T003 Tests in tests/test_guards.py: clusters on a feature branch in two positions, clusters with no `f` that pass, and real git on a diverged main. 24 red on a53405f's guard (16 unit, 8 real git), 15 green there (the cases read as before)

## Phase 2: Implementation

- [x] T004 `git_push`: `re.match('-[^-]*f', a)` in place of `re.fullmatch(r'-[a-z]*f[a-z]*', a)`; 39 green
- [x] T005 Vendored guards.py copied; the drift test passes
- [x] T006 Route corpus: 5 rows naming the item (3 push, 2 pass)
- [x] T007 Controls `--follow-tags` and `--signed=if-asked` pass, so a pattern reading any dash before `f` fails

## Phase 3: Proof

- [x] T008 Route differential: the head corpus (293 routes) through a53405f's guard and the head's: 0 of main's 288 move in verdict or reason; 3 of the 5 new rows move (pass to push)
- [x] T009 Generated probe at main and the head: 6,090 generated, 6,090 ran git push, 0 holes and 0 misreads at the head; 1,431 holes at main; 0 newly passed
- [x] T010 Seven mutants of the pattern, applied to both guards.py copies one at a time: each killed by a behavioural test
- [x] T011 Full suite green; runtime 3,879 at the head (+0)
