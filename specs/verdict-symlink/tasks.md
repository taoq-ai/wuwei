# Tasks: the worktree verdict copy-in refuses a symlink under .wuwei/verdicts

## Phase 1: Tests first

- [x] T001 [US1] A link at the copy path (dangling, to another file, to an identical file) is refused and its target unchanged (tests/test_hook.py)
- [x] T002 [US2] A link at `verdicts/x` and at `verdicts` into the ledger is refused and no ledger file is added (tests/test_hook.py)
- [x] T003 [US3] A link planted at the copy path right after the check is replaced, never followed (tests/test_hook.py)
- [x] T004 Run the new tests red: 5 failed on main's code (T003 holds the new write path and passes on main, where no check runs)

## Phase 2: Implementation

- [x] T005 Build the copy path under the resolved root and refuse a link at any component (cli/wuwei/hook.py)
- [x] T006 Write the copy through `ws.atomic_write` (cli/wuwei/hook.py)
- [x] T007 `ws.atomic_write` writes bytes as given (cli/wuwei/ws.py)
- [x] T008 Run the full suite green, runtime at 2,977

## Phase 3: Checks

- [x] T009 Mutants of each new condition, run in a scratch copy, each fail a test
- [x] T010 Route corpus through the guards and the PreToolUse hook at main and at the head, with its sha256
- [x] T011 Path class and symlink probes at main and at the head, on Python 3.13 and 3.11
- [x] T012 Re-vendor .claude/ with setup.vendor('.')
