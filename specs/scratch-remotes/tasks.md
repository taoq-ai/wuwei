# Tasks: the push door passes a push whose remote is a local path under the session scratch folder

## Phase 1: Reading and tests first

- [x] T001 Worktree from origin/main c84913e on claude/scratch-remotes; moved onto 9c637ab when free-lines-5 merged
- [x] T002 Read the hook payload and environment for the scratch folder: none names it; `tempfile.gettempdir()` is `/tmp`
- [x] T003 Read from real git 2.43: relative remote paths resolve from the checkout top; `git config -z --get-regexp` output; the environment's command-line `insteadOf`
- [x] T004 [US1, US2] Tests with real local repositories and no push: plain scratch pushes pass; the working repo, its .git, symlinks, .wuwei holders, GitHub, rewrites, receivepack, vcs, options and non-plain shapes keep the door; force stays refused; timing at 125 KB and 500 KB (tests/test_guards.py)
- [x] T005 Run the new tests on main: 14 red, the refusal cases and timing green

## Phase 2: Implementation

- [x] T006 `PLAIN`, the whole command and the checkout folder passed to `git_push`, read only for a push that meets the default branch
- [x] T007 `scratch`: the config read, urls and pushurls, the rewrite, receivepack and vcs check, realpath under the temp folder, no `.git` or `.wuwei` at or above
- [x] T008 Tests green; full suite green
- [x] T009 Generated probe, 368 commands (23 locations x 16 spellings) under real bash with a stub git: 0 holes at the head, every main-target command refused on main
- [x] T010 Mutants: 10 of 10 killed by the tests
- [x] T011 Route corpus: 6 rows added by code; no older row moves
- [x] T012 Vendored guards.py byte-identical; SECURITY.md and doors.md describe the exception
- [x] T013 Timing at 125 KB and 500 KB on head and main: linear, within noise
