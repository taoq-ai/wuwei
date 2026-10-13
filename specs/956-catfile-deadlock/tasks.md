# Tasks: Prevent git cat-file batch deadlock

**Input**: `spec.md`, `plan.md`

## Phase 1: Setup

- [X] T001 Confirm root cause and shared caller path in adapters/vcs/git.py and cli/wuwei/integrity.py.

## Phase 2: User Story 1 - Inspect a large development checkout

- [X] T002 [US1] Add a large committed-tree regression in tests/test_vcs.py with request and output each above 64 KiB.
- [X] T003 [US1] Run the regression alone and confirm it fails because batch stdin is a pipe.
- [X] T004 [US1] Change adapters/vcs/git.py `_run` to supply input from a rewound TemporaryFile.
- [X] T005 [US1] Run the regression and every test file importing the changed adapter with explicit pytest file arguments.
- [X] T006 [US1] Review the diff, requirement coverage, and working-tree state.
