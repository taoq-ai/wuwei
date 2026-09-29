# Implementation Plan: Owner memory edits

**Branch**: `169-owner-edits` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Add owner edit entry points for goals and voice. Validate content, write atomically, and use the existing workspace promotion commit producer with an owner provenance line. Refuse registered seat sessions at the hook boundary and preserve direct write guards.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib runtime, existing VCS port
**Storage**: `.wuwei/memory/` and `.wuwei` history
**Testing**: pytest
**Constraints**: three-state exits, no external runtime dependency, no new config

## Constitution Check

- Runtime remains stdlib-only and external Git stays in the VCS adapter.
- Tests precede each behavior change.
- Changes use shared path and atomic write helpers.
- Seat writes remain refused and errors fail closed.

## Project Structure

- `cli/wuwei/commands/goals.py`, `cli/wuwei/commands/voice.py`: entry points.
- `cli/wuwei/promotion.py`: owner edit producer.
- `adapters/vcs/git.py`: promotion commit message allowance.
- `cli/wuwei/guards/protect_state.py`: registered seat refusal.
- `tests/test_owner_edits.py`: behavior and integrity checks.
- `docs/site/configuration.md`, `templates/workspace/memory/voice.md`: owner flow documentation.
