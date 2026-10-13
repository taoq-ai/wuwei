# Tasks: Restore the test function budget

## Phase 1: Setup

- [x] T001 Capture the CI regex count and collected node IDs per file in `specs/977-test-budget/research.md`.

## Phase 2: CI budget [US1]

- [x] T002 [US1] Add the real suite budget regression in `tests/test_dev_cycle.py` and observe the expected failure.

## Phase 3: Coverage preserving consolidation [US2]

- [x] T003 [US2] Merge identical-body parameter tables in `tests/test_shell.py`, `tests/test_edges.py`, `tests/test_merge.py`, and `tests/test_protect_state.py`.
- [x] T004 [US2] Parameterize related named scenario families in `tests/test_dispatch.py`, `tests/test_workspace.py`, and the other affected test files listed in `specs/977-test-budget/verification.md`, retaining each original body and fixture signature.
- [x] T005 [US2] List any deleted exact duplicates in `specs/977-test-budget/verification.md`.

## Phase 4: Verification

- [x] T006 Run all changed test files with the required interpreter and explicit file arguments.
- [x] T007 Compare collected cases per changed file with T001 and confirm the CI regex count below 2810; record results in `specs/977-test-budget/verification.md`.
- [x] T008 Run all explicit test files and inspect the final diff for no runtime edits, skips, weakened assertions, or embedded absolute local paths; record results in `specs/977-test-budget/verification.md`.
