# Tasks: Notes

**Input**: `specs/029-notes/spec.md` and `plan.md`.

## Phase 1: User Story 1, create a note

- [X] T001 [US1] Write failing CLI tests for valid creation, summary refusal, decision routing, duplicate slug, and workspace failure in `tests/test_notes.py`; run them and confirm expected failure.
- [X] T002 [US1] Implement `wuwei note add` and atomic exclusive creation in `cli/wuwei/commands/note.py`; run the T001 tests.

## Phase 2: User Story 2, reusable validation

- [X] T003 [US2] Write failing parser tests for valid and invalid frontmatter in `tests/test_notes.py`; run them and confirm expected failure.
- [X] T004 [US2] Implement reusable parser and validator in `cli/wuwei/notes.py`; run the T003 tests and T001 tests.

## Phase 3: Verification

- [X] T005 Run the full issue interpreter test command, inspect the diff, and check authored files for em-dashes and emojis.

## Review fixes

- [X] T006 Add failing parser and CLI regression tests for malformed frontmatter, hidden line breaks, symlinked notes directories, Unicode output, and sync calls.
- [X] T007 Harden note parsing and creation against the review findings, then rerun the issue interpreter test command.

## Dependencies

T001 precedes T002. T003 precedes T004. T002 can call the planned parser before T004 is implemented, so the T001 tests become green after T004. T005 follows all implementation.

## Deferred

Existing note updates and archives belong to issue #81. Index and probation calculations belong to later memory work.
