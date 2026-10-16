# Tasks: the doors read a command inside a loop or if body, after shell flags, and after a wrapper's options

## Phase 1: Tests first

- [x] T001 [US1] Doors inside for, while, until, if, elif, else, brace group and after `!` are refused (tests/test_guards.py)
- [x] T002 [US2] `bash -lc`, `sh -ec`, `bash -e -c` and a loop in a `bash -c` body meet their door (tests/test_guards.py)
- [x] T003 [US3] `timeout`, `nice -n`, `env -u`, `stdbuf`, a wrapper chain and `xargs -n 1 sh -c` reach the door (tests/test_guards.py)
- [x] T004 [US4] Ordinary loops, ifs, brace groups and wrapped commands pass (tests/test_guards.py)
- [x] T005 [US2] An unreadable `bash -c` body naming a door is refused with the hint; `segments` returns None (tests/test_guards.py)
- [x] T006 The ledger door still reads `python3` and `rm` after a wrapper with options (tests/test_guards.py)
- [x] T007 Run the new tests red

## Phase 2: Implementation

- [x] T008 `WRAPPERS` adds timeout and stdbuf; `READ` names the programs a door reads (cli/wuwei/guards.py)
- [x] T009 Reserved words dropped with `VAR=value`; first-program rule after a wrapper (cli/wuwei/guards.py)
- [x] T010 Combined shell flags before `-c` (cli/wuwei/guards.py)
- [x] T011 An unreadable nested body makes `segments` return None (cli/wuwei/guards.py)
- [x] T012 Redirect loop in three lines, net zero in cli/wuwei/ (cli/wuwei/guards.py)
- [x] T013 Run the full suite green

## Phase 3: Docs and checks

- [x] T014 docs/design.md section 7 names the new readings
- [x] T015 SECURITY.md records the residual shapes
- [x] T016 Mutants of each new condition, run in a scratch copy, each fail a test; a mid-command redirect test added for the redirect loop
- [x] T017 Re-vendor the plugin into .claude/ with setup.vendor
