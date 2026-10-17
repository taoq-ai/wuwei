# Tasks: process substitution, glued separators, $'...' quoting and ledger paths meet the doors

## Phase 1: Real execution and tests first

- [x] T001 Run each acceptance shape under `bash -c` with a stub `git` on PATH; record the log
- [x] T002 [US1] Pushes behind `<(`, `>(`, `;>`, `&&(`, `;(`, `);` and `|&` meet the push door (tests/test_guards.py)
- [x] T003 [US2] `$'` and `$"` quoting naming a door is unreadable; quoted literals and no-door commands pass (tests/test_guards.py)
- [x] T004 [US3] Ledger spellings without a trailing slash, `.wuwei` itself and `of=` are ledger writes; reads pass (tests/test_guards.py)
- [x] T005 [US3] The hook fails closed on `rm -rf .wuwei` and open on `cat .wuwei/plan.json` (tests/test_hook.py)
- [x] T006 [US4] 18 routes.json rows naming their source
- [x] T007 Run the new tests on 83f1f09: 39 red

## Phase 2: Implementation

- [x] T008 `OPS` split of punctuation runs; `|&` in `CONTROL`
- [x] T009 `$'` and `$"` outside quotes make `segments` return None
- [x] T010 `LEDGER` and the `DOOR_WORDS` ledger entry
- [x] T011 Run the tests green; a quoted-dollar case added red (3) then green

## Phase 3: Integration

- [x] T012 Docs: design.md, docs/site/concepts/doors.md, SECURITY.md known shapes
- [x] T013 Re-vendor `.claude/` with `setup.vendor`
- [x] T014 Route corpus probe on main and head with the corpus sha256
- [x] T015 Traced Bash commands read by main's and head's guards offline
- [x] T016 Full suite green; runtime at 2,999 lines
