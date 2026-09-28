# Implementation Plan: Memory index and payload

**Branch**: `030-memory-index` | **Date**: 2026-09-28 | **Spec**: `specs/030-memory-index/spec.md`

## Summary

Reuse the note parser, workspace path and clock helpers, state reader and exit constants. Add one memory module for index generation and payload assembly, plus two CLI command modules. Extend config validation with `memory.max_notes` default 60. Use the shared workspace atomic writer for index, state and note creation.

## Technical Context

- Python 3.11+, standard library runtime, pytest development tests.
- Workspace Markdown files, TOML config and JSON state.
- Run tests with the interpreter named by issue #30.

## Constitution Check

- CLI remains the only writer. Note parsing and state defaults are reused.
- Findings return 1 and operational failures return 2.
- Tests precede each implementation behavior. No external runtime dependencies.

## Project Structure

- `cli/wuwei/memory.py`: render and atomically write index; assemble payload.
- `cli/wuwei/commands/index.py`, `payload.py`: CLI registration and status output.
- `cli/wuwei/workspace.py`: validate memory maximum and write files atomically.
- `tests/test_memory.py`: behavior and CLI tests.

No separate research or data model file is needed. The file formats and decisions are in the spec.
