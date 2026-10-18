# Tasks: the verdict copy-in walks .wuwei/verdicts with directory file descriptors

## Phase 1: Tests first

- [x] T001 [US1] A parent (`verdicts/x`, `verdicts`) swapped for a ledger link after the check leaves the ledger unchanged and refuses (tests/test_hook.py)
- [x] T002 [US2] A looping `.wuwei/verdicts` refuses the hand-back and records verdict.missing (tests/test_hook.py)
- [x] T003 [US2] A RuntimeError from resolving the verdicts folder or the seat's path is refused like an OSError (tests/test_hook.py)
- [x] T004 [US3] No free name (all taken, unlistable) at each of three call sites is a refusal, never hook.error (tests/test_hook.py)
- [x] T005 [US3] The next free name lists the folder once (tests/test_hook.py)
- [x] T006 [US4] A pull never writes through a link planted under .wuwei (tests/test_sync.py)
- [x] T007 Run red: 11 failed on 3.13 at main's code; the loop test failed on 3.11 (RuntimeError, hook.error)

## Phase 2: Implementation

- [x] T008 `ws.atomic_write` walks below `root` by directory descriptor (cli/wuwei/ws.py)
- [x] T009 The copy-in passes the resolved root; `sync.pull` passes `.wuwei` (cli/wuwei/hook.py, cli/wuwei/sync.py)
- [x] T010 Resolve `verdicts` inside the `try` and catch RuntimeError (cli/wuwei/hook.py)
- [x] T011 `free()` lists once and returns a refusal text on OSError or StopIteration (cli/wuwei/hook.py)
- [x] T012 Move the re-plant test from `Path.unlink` to `os.unlink` (the old contract) (tests/test_hook.py)
- [x] T013 Full suite green on 3.13, 3.12 and 3.11; re-vendor `.claude/` with setup.vendor('.')

## Phase 3: Checks

- [x] T014 Mutants of each new condition in a scratch copy, each failing a test
- [x] T015 Route corpus differential at main and the head, with its sha256
- [x] T016 Race probe at main and the head, both levels, 2000 copy-ins, on 3.13 and 3.11
- [x] T017 Path and link probe at main and the head, on 3.13 and 3.11
