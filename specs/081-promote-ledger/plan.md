# Implementation Plan: Proposal promotion and ledger

**Branch**: `081-promote-ledger` | **Date**: 2026-09-28 | **Spec**: `specs/081-promote-ledger/spec.md`

## Summary

Use the existing workspace clock, config reader, note parser, atomic writer, locked JSONL append, index and payload. Add a memory promotion module and thin CLI commands. Validate every path inside the real workspace before reading or writing it. Record each result in the ledger, then render the most recent run in the existing payload function. Consolidate reads recorded spans and lists candidates without mutation.

## Technical Context

- Python 3.11 standard library at runtime, pytest for tests.
- No external ports are needed.
- Tests use the issue interpreter and temporary workspaces.

## Constitution Check

- CLI is the only writer; proposals are requests, not trusted records.
- Invalid proposals are findings (1); missing or unreadable required input is unrun (2).
- Tests precede each behavior. Writes reuse shared helpers.

## Project Structure

- `cli/wuwei/promotion.py`: proposal validation, promotion, ledger summary and archive candidate selection.
- `cli/wuwei/commands/promote.py`, `consolidate.py`: command entry points.
- `cli/wuwei/memory.py`, `workspace.py`, `commands/note.py`, `state.py`: focused integration changes.
- `tests/test_promotion.py`: behavior and CLI tests.

No separate research, data model or quickstart artifact is needed; the contract is in the feature spec.
