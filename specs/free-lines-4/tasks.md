# Tasks: free runtime lines with no behaviour change

## Phase 1: Tests first

- [x] T001 [US4] Split cases for `x&&>|y`, `x|&>y` and `x&>;y`, and a segments case for the glued runs (tests/test_guards.py)
- [x] T002 Run the split tests red in a copy with `&&`, `|&` or `&>` dropped from OPS (each fails)

## Phase 2: Implementation

- [x] T003 [US1] Walrus rewrites in evidence, hook, plan, report, setup, sync, upgrade, verdict (skip hook.exception_refs)
- [x] T004 [US1] guards: found-then-return in bash, dollar and glued booleans, sentinel comment, explicit _unwrap if/else
- [x] T005 [US4] guards.OPS drops only `\|\|` and `;;`
- [x] T006 [US1] guards.LEDGER_DENIED for the four ledger refusals
- [x] T007 [US1] Re-vendor .claude/ with setup.vendor() at the head

## Phase 3: Proof

- [x] T008 [US2] Full suite green
- [x] T009 [US3] Differential probe of guards.segments, 9d6701e against the head: 0 of 82,944 differ
- [x] T010 [US1] `cat cli/wuwei/*.py | wc -l` at 2,977 or less
