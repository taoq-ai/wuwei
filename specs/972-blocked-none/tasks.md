# Tasks: Clear Blocked none notes and explain owner cards

## Phase 1: Regression tests

- [x] T001 [US1] Add the reported field case and punctuation boundaries to `tests/test_dispatch.py`; run the tests and observe the false escalation.
- [x] T002 [US2] Add a reworded Yes replay case to `tests/test_build_next.py`; run the test and observe that the reason lacks a verbatim instruction.

## Phase 2: Implementation

- [x] T003 [US1] Recognize the specified `none` prefix in the shared `_blocked` decision in `cli/wuwei/dispatch.py`.
- [x] T004 [US2] State the verbatim card requirement for unanswered cards in `_blocked_card` in `cli/wuwei/dispatch.py`.

## Phase 3: Verification

- [x] T005 Run every explicit test file importing `wuwei.dispatch` with the specified interpreter and `-p no:cacheprovider`; inspect the diff and report results.
