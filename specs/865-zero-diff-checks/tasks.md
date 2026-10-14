# Tasks: Skip fast checks for an empty item diff

## Phase 1: Setup

- [X] T001 Read the existing build check path, diff and status helpers, and relevant fake ports; document the chosen scope in `spec.md` and `plan.md`.

## Phase 2: Regression tests [US1, US2]

- [X] T002 [US1] Add a clean empty-diff regression with a missing linter in `tests/test_fast_checks.py`; run it and confirm the expected failure.
- [X] T003 [US2] Add tests for nonempty, dirty, and unmeasured diffs in `tests/test_fast_checks.py`; run them before implementation and confirm the new unmeasured behavior fails.

## Phase 3: Implementation [US1, US2]

- [X] T004 [US1] In `cli/wuwei/commands/build.py`, skip configured checks for a measured clean empty diff and record `not applicable: no diff` in the build result and event.
- [X] T005 [US2] Preserve normal checks for changed or dirty items and exit 2 for an unmeasured diff in `cli/wuwei/commands/build.py`; update only existing build test fakes needed to represent a nonempty diff.

## Phase 4: Verification

- [X] T006 Run every test file importing the changed build module and inspect the results.
- [X] T007 Run the full suite with explicit test files; inspect the diff for scope, absolute paths, em-dashes, and emojis.

## Dependencies

T001 precedes T002 and T003. Both test tasks precede T004 and T005. All implementation precedes T006 and T007. No parallel tasks share runtime files.
