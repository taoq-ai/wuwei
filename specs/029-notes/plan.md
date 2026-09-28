# Implementation Plan: Notes

**Branch**: `029-notes` | **Date**: 2026-09-28 | **Spec**: `specs/029-notes/spec.md`

## Summary

Add `wuwei note add` and one importable parser/validator. Use existing workspace discovery, shared clock and exit codes. Persist with a temporary file and exclusive hard link so a duplicate cannot replace a note.

## Technical Context

- Language: Python 3.11+.
- Runtime dependencies: standard library only.
- Storage: Markdown files under `.wuwei/memory/notes/`.
- Testing: pytest, including CLI subprocess tests using the issue interpreter.

## Constitution Check

- One CLI writer, one reusable validation function, no new runtime dependencies.
- Validate before writing; use atomic exclusive creation.
- Exit 1 for content findings and existing slug, exit 2 for operational failures.
- Write failing tests and run them before implementation.

## Project Structure

- `cli/wuwei/notes.py`: parse and validate the small frontmatter subset.
- `cli/wuwei/commands/note.py`: CLI registration, creation, exclusive write.
- `tests/test_notes.py`: parser and CLI contracts.

No separate research, data model or contracts files are needed; the contract is stated in the spec.
