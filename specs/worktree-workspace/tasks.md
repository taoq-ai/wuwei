# Tasks: worktree-workspace

## Phase 1: Tests first

- [x] T001 [US1, US2] `test_a_linked_worktree_resolves_to_its_main_checkouts_workspace`
- [x] T002 [US3] `test_a_worktree_with_no_workspace_above_its_main_checkout_and_a_plain_folder_are_no_workspace`
- [x] T003 Run at origin/main 8fc0d49b: 2 failed

## Phase 2: Implementation

- [x] T004 `ws.find` follows a linked worktree's `.git` file and `commondir` to the main checkout
- [x] T005 Vendored copy `.claude/wuwei/cli/wuwei/ws.py`
- [x] T006 SECURITY.md Hooks line

## Phase 3: Evidence

- [x] T007 `tests/test_ledger.py tests/test_setup.py`: 84 passed, 1 skipped; runtime 3,955 lines
- [x] T008 Probe: worktree of another repository, worktree with no workspace above its main, plain stray folder,
  forged loop, and the machine's real worktrees
