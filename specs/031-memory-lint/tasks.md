# Tasks: Memory lint

**Input**: `specs/031-memory-lint/spec.md` and `plan.md`.

## Phase 1: Note quality

- [X] T001 [US1] Write failing stale-summary and line-cap tests in `tests/test_memory_lint.py`; run and confirm failure.
- [X] T002 [US1] Implement stale-summary and line-cap lint in `cli/wuwei/memory.py` and config defaults in `cli/wuwei/workspace.py`; run T001 tests.
- [X] T003 [US1] Write failing state-log and raw-intake tests in `tests/test_memory_lint.py`; run and confirm failure.
- [X] T004 [US1] Implement state-log and raw-intake findings in `cli/wuwei/memory.py`; run T003 tests.

## Phase 2: Unused notes

- [X] T005 [US2] Write failing probation, load, and unreadable-trace tests in `tests/test_memory_lint.py`; run and confirm failure.
- [X] T006 [US2] Implement working-day probation and trace reads in `cli/wuwei/memory.py`; run T005 tests.

## Phase 3: CLI and verification

- [X] T007 [US1] Write failing exit 0, 1, and 2 CLI tests in `tests/test_memory_lint.py`; run and confirm failure.
- [X] T008 [US1] Implement `wuwei memory lint` in `cli/wuwei/commands/memory.py`; run T007 tests.
- [X] T010 [US2] Add failing tests for forged trace and ledger writes in `tests/test_protect_state.py`.
- [X] T011 [US2] Reserve trace and ledger files in `cli/wuwei/guards/protect_state.py` and update config defaults in `tests/test_workspace.py`.
- [X] T009 Run the full pytest suite, inspect diff, and check authored files for prohibited text.

## Dependencies

Tasks run in listed order. SessionStart consumes `memory.lint` in issue #15.
