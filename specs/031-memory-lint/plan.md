# Implementation Plan: Memory lint

**Branch**: `031-memory-lint` | **Date**: 2026-09-28 | **Spec**: `specs/031-memory-lint/spec.md`

## Summary

Add one read-only lint function in `cli/wuwei/memory.py` and a thin `wuwei memory lint` command. Reuse note parsing and workspace config. Scan active notes and, when relevant, day traces and the promotion ledger.

## Technical Context

Python 3.11+ stdlib runtime; pytest dev only. Workspace Markdown, TOML, and JSONL. No network or external adapter.

## Constitution Check

One behavior per CLI function; no state writes; three-state exits; fail closed on unreadable input. Tests precede each implementation step. No new dependency.

## Project Structure

- `cli/wuwei/memory.py`: lint findings and local data reads.
- `cli/wuwei/commands/memory.py`: CLI dispatch and exit mapping.
- `cli/wuwei/workspace.py`: validated memory cap, state entry threshold, and probation defaults.
- `cli/wuwei/guards/protect_state.py`: reserve trusted trace and ledger files.
- `tests/test_memory_lint.py`: in-process behavior and one CLI smoke test.

No additional design artifacts are needed; the record shapes and assumptions are in the feature spec.
