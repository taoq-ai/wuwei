# Tasks: Optional SwiftBar indicator

**Input**: `specs/094-swiftbar/spec.md` and `plan.md`.

## Phase 1: Render status

- [X] T001 Write failing fixture tests for page, nudge, clean, and unmeasured output; run and inspect failure.
- [X] T002 Implement the plugin template and pass T001.
- [X] T003 Add tests for malformed, missing, and failed status; run them.
- [X] T004 Write failing tests for missing Python and status timeout, then make all unreadable paths unknown with exit 2 and reason.

## Phase 2: Setup guidance

- [X] T005 Write failing tests for macOS guidance and other-platform absence; run and inspect failure.
- [X] T006 Add read-only `wuwei init --menu-bar` guidance; pass T005.

## Phase 3: Verify

- [X] T007 Run the full test suite, inspect diff, and check changed files for forbidden characters and local absolute paths.

## Dependencies

T001 precedes T002. T003 precedes T004. T005 precedes T006. T007 follows implementation.

## Deferred

A menu_bar port and individual alert descriptions await another implementation or richer status data.
