# Tasks: Guard mutation coverage

## Phase 1: Coverage meta-check

- [X] T001 [US1] Register a temporary dummy guard and prove discover() and key() name it as uncovered.
- [X] T002 [US1] Add the live discover() and special-policy coverage comparison in tests/test_guard_mutation.py.

## Phase 2: Mutation probes

- [X] T003 [US1] Add a failing mutation probe for each registered guard and special policy in tests/test_guard_mutation.py.
- [X] T004 [US1] Add the minimum shared in-process mutation runner and case setup in tests/test_guard_mutation.py.

## Phase 3: Bypass rows

- [X] T005 [US2] Add missing spec 4.5 rows, including invoked script files, to relevant guard tables and run them red.
- [X] T006 [US2] Refuse invoked scripts containing guarded commands while allowing unrelated scripts.

## Phase 4: Validation

- [X] T007 Run the full specified pytest command and check changed files for local paths, em-dashes and emojis.

## Dependencies

T001 precedes T002. T003 precedes T004. T005 precedes T006. T007 follows all others.

## Delta review fixes

- [X] T008 Reproduce R1 with script-reader and hook-shim tests, skip unreadable, binary, non-regular and oversized files, and scope PR script reads to the workspace.
- [X] T009 Assess R2 compound script inspection and run the specified full pytest suite (4370 passed, 3 skipped).

R2 remains a residual: compound script inspection needs directory tracking and must
preserve the relevance checks that let harmless unsupported shell syntax pass.
That extension is deferred to keep this blocking regression fix small.
