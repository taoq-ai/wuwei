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

## Phase 4: Fix round 1 (gates at 6a5d00d)

- [x] T019 Tests first: a work tree outside the shell (10 cases: `--work-tree`, `--git-dir` with `--work-tree`, `-C`, `-c core.worktree`, `core.worktree` in config, from a subfolder), a remote in global config (2), `--exec` and `--receive-pack` in four spellings (5), `+` refspecs that pass and land (2), remote `pct` whose url decodes `%2e%2e`; 18 red at the merged head before the change
- [x] T020 `rev-parse --is-inside-work-tree` must print `true`; a typed word with a `remote.<word>.` key in any scope and no get-url answer is refused; `--exec` and `--receive-pack` prefixes are refused; `+` joins the word class; `TEMP` reads the temporary folders only for a scratch push
- [x] T021 design.md and doors.md name the scratch exception; SECURITY.md's path-base and config lines corrected; routes.json gets 2 rows
- [x] T022 The probe is committed as `specs/scratch-remotes/probe.py`, extended with the work-tree, core.worktree, global-config, pct, exec and receive-pack classes, `+` and `:` refspecs, and a subfolder and a non-repository session directory
- [x] T023 Merged origin/main 3d2eb29 (#1134 and others); full suite 1859 passed, 2 skipped
- [x] T024 Probe at the head: 42,768 generated, 40,824 ran git push, 0 holes (1,128 passes; 10,981 commands moved a protected main, none passed). The same probe at 6a5d00d over three of the six session directories (c, w, wcore): 274 holes
- [x] T025 Gate probes at the head: security worktree_base.py 13 generated, 13 ran, 0 holes; quality probe.py 2,366 generated, 2,366 ran, 0 holes; quality wt.py, cwt.py, glob.py and pct.py refuse every case
- [x] T026 18 mutants, each failing the item's tests; route corpus: 257 routes on main and the head, 0 move
- [x] T027 Runtime 3,004 against 2,986 on main
