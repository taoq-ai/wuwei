# Implementation Plan: Verdict lint scope

**Branch**: `931-verdict-lint-scope` | **Date**: 2026-10-14 | **Spec**: `spec.md`

## Summary

Limit finding parsing to Findings sections, validate scenario prose without a fixed phrase list, and identify Bash gate write targets before linting. Reuse the existing active-text filter, shell normalizer, workspace scope, file lint, and stop-seat lookup.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Standard library
**Testing**: pytest
**Target Platform**: CLI and Claude Code hooks
**Constraints**: Existing 0/1/2 exits, test first, smallest diff

## Constitution Check

- Stdlib runtime and existing modules only.
- Exit 2 remains for unreadable targeted files.
- Each behavior receives a failing test before implementation.
- No new state or external tool call.

## Project Structure

- `cli/wuwei/verdict.py`: finding section and scenario validation.
- `cli/wuwei/guards/verdict.py`: Bash target selection.
- `tests/test_verdict.py`: regression and existing verdict behavior tests.

## Design

Keep the current finding block recognition inside a Findings section. End it at the next peer heading. Derive a scenario from the finding's content after required metadata, allowing natural prose and explicit scenario fields. Use normalized shell command write targets and literal gate path arguments for Bash; retain conservative refusal for opaque interpreter snippets.
