# Implementation Plan: Runtime adapters

**Branch**: `026-runtime-adapter` | **Date**: 2026-09-28 | **Spec**: `specs/026-runtime-adapter/spec.md`

## Summary

Add Claude and Codex runtime modules behind the existing registry. Put companion execution and output validation in the Codex adapter. Add one core build-loop command that calls runtime and checks ports and records each iteration through the state writer.

## Technical Context

Python 3.11+, stdlib-only runtime, pytest development tests. External Codex calls use subprocess in the adapter. Existing workspace configuration, atomic writer, event writer, verdict checker and checks port are reused.

## Constitution Check

Tests precede each implementation. Adapter calls use 0/1/2. Core imports no subprocess. No engagement-specific defaults. Existing guarded state fields remain reserved.

## Project Structure

- `adapters/runtime/claude.py`, `codex.py`: runtime implementations.
- `cli/wuwei/commands/build.py`: orchestration and usage records.
- `cli/wuwei/workspace.py`: build and Codex adapter configuration.
- `tests/test_runtime.py`, `tests/test_build.py`: behavior and failure contracts.

No separate research, data model or contracts file adds useful detail beyond the spec and existing registry contract.
