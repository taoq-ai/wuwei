# Tasks

## Setup
- [x] T001 Read approved item, governing docs and observed fixture in tests/test_evidence.py.

## US1: Ready evidence
- [x] T002 [US1] Preserve ready regression coverage in tests/test_guards.py for positively classified pending review.

## US2: Pending review auto-merge
- [x] T003 [US2] Add failing CLI, REST and MCP auto-merge tests in tests/test_guards.py, including running CI.
- [x] T004 [US2] Allow pending review waits in cli/wuwei/evidence.py and its vendored copy.

## US3: Safety failures
- [x] T005 [US3] Add failing unreadable-classifier cases in tests/test_evidence.py and tests/test_guards.py.
- [x] T006 [US3] Keep classifier failures unreadable in cli/wuwei/evidence.py and preserve other safety refusals.

## Validation
- [x] T007 Update docs/design.md and run focused suites plus main/head route comparison.
- [x] T008 Recheck spec consistency, source/vendor parity and runtime budget; commit and push the draft PR.
