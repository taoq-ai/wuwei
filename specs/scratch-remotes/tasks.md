# Tasks: the push door passes a push to a git directory in a scratch folder

## Phase 1: Real execution and tests first

- [x] T001 Worktree from origin/main efcd9e7 on claude/scratch-remotes; runtime 2,976
- [x] T002 Real git 2.43: a relative remote path (typed, or a remote's url) is read from the top of the worktree, not the shell's directory
- [x] T003 Real git 2.43: `git remote get-url --push --all` gives pushurl and pushInsteadOf; it refuses a word that names no configured remote
- [x] T004 [US1] From Bash, `git push ../r.git main` in a scratch clone meets the live door (main's vendored guard) and is refused, as on main
- [x] T005 [US1, US2] Tests: 12 real-execution passes, 36 refusals, the worktree case (tests/test_guards.py); 13 red on efcd9e7
- [x] T006 Spec, plan and tasks written after the red run (the spec engine step came late; recorded in the handoff)

## Phase 2: Implementation

- [x] T007 `TEMP` and `scratch` in guards.py; the call site in `bash`
- [x] T008 Tests green
- [x] T009 Mutants of each check in `git archive` copies; three survived (option check, `TEMP`, git directory read)
- [x] T010 Tests that kill them, each planting where a misreading guard would look: a bare `c/-u`, `r.git/q` beside a `q.git` link, a literal `%2e%2e` path, a `localhost` path, a moved `TEMP`
- [x] T011 Real git 2.43 entered a planted `p.git/.git` link before `p.git`, and decoded `%2e%2e` and dropped `localhost` in a `file://` URL: the rule refuses a target holding a `.git` entry, with its test and mutant
- [x] T012 Config that sends a typed path elsewhere (`insteadOf`, `pushInsteadOf`, `remote.*.vcs`, `remote.*.receivepack`) keeps the door, with tests and a mutant
- [x] T013 Route corpus: 4 rows added; base and head read 255 routes, 0 move, corpus sha256 recorded
- [x] T014 Generated probe under real bash and a stub git on PATH: 10,260 commands, 9,720 ran git push, 0 holes at the head (452 passes, 2,165 commands moved a protected main and none passed); 0 passes on efcd9e7
- [x] T015 Vendored guards.py rewritten by `setup.vendor`; SECURITY.md describes the rule and its holes

## Phase 3: Proof

- [x] T016 Full suite green at the head
- [x] T017 12 mutants, each failing the item's tests
- [x] T018 `cat cli/wuwei/*.py | wc -l` at 2,992
