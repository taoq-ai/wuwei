# Tasks: one canary reader, and the canary behind the ledger door

## Phase 1: Tests first

- [x] T001 [A1] A canary of invalid UTF-8, and one mode 000, leaves seat.started, seat.stopped, the kept report and its delivery in place (tests/test_hook.py)
- [x] T002 [A1] A native (Codex) seat stop is recorded with a canary of invalid UTF-8 (tests/test_native_evidence.py)
- [x] T003 [A2] Each path class x wrapper x write route on the canary gets the ledger's verdict, and Write, Edit, MultiEdit, NotebookEdit and apply_patch are refused (tests/test_guards.py)
- [x] T004 Reading the canary passes (tests/test_guards.py)
- [x] T005 Run the new tests red on main's code

## Phase 2: Implementation

- [x] T006 `ws.canary(root)` (cli/wuwei/ws.py)
- [x] T007 The five canary reads in hook.py call it (cli/wuwei/hook.py)
- [x] T008 `canary` on `LEDGER` and `CACHE`, `/canary` on the ledger door word (cli/wuwei/guards.py)
- [x] T009 Re-vendor .claude/wuwei/cli/wuwei/
- [x] T010 Run the full suite green

## Phase 3: Checks

- [x] T011 [A3] Canary rows in tests/fixtures/routes.json; the corpus read at main and head, sha256 recorded
- [x] T012 Generated probe at main and head (probe.py), run.sh and cases.tsv for the owner's real-bash run
- [x] T013 Mutants on both copies, one suite at a time
