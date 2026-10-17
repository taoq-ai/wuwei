# Tasks: git options before the subcommand are read by allowlist

## Phase 1: Real execution and tests first

- [x] T001 Worktree from origin/main d1c3d79 on claude/git-globals; runtime 2,996
- [x] T002 Read git 2.43's options from real git (each before `status`): value forms and the unknown ones
- [x] T003 [US1] Real git against a local bare remote: `--config-env core.abc=Y` and `--attr-source HEAD` moved main, `--namespace x` did not (local path); the guard on main passed all three
- [x] T004 [US2] Generated probe, 6,478 commands under real git; main has 504 holes
- [x] T005 [US1, US2, US3] Tests: valued options before a push to main, unknown options before a push, steering -c forms, known options that pass, a 125 KB timing case (tests/test_guards.py)
- [x] T006 Run the new tests on the base: 22 red, 10 green (the pass cases and timing)

## Phase 2: Implementation

- [x] T007 `GIT_OPTS` and the loop reading it; the refusal after the loop
- [x] T008 Tighten four existing lines; runtime 2,996
- [x] T009 Run the tests green; full suite green
- [x] T010 Re-read the 6,478 probe commands through the head guard: 0 holes, 666 of 666 known-option feature pushes pass
- [x] T011 Route corpus: 10 rows added by code; no older row moves
- [x] T012 Vendored guards.py byte-identical; SECURITY.md updated
- [x] T013 Timing at 125 KB: worst 0.173 s at the head, 0.164 s on main

## Phase 3: Fix round 1 (verdicts at 6f40026)

- [x] T014 Tests first: alias after an unknown option, one-word steering then a known option, lone valueless options before main, every option in each form, push routing config without push passes, 125 KB and 500 KB split timing (18 red at 6f40026)
- [x] T015 Append in place in `segments` and `_unwrap` (the quadratic copies)
- [x] T016 An alias or include match wins over an earlier odd word; remote, branch, url and push.default refuse only before a push; the refusal names the alias rule on its own
- [x] T017 design.md section 6 and doors.md History row list the new refusals; SECURITY.md updated
- [x] T018 Route corpus: 4 rows added; probes, mutants and timing re-run
