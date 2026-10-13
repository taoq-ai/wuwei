# Implementation Plan: Clear Blocked none notes and explain owner cards

**Branch**: `972-blocked-none` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Use the existing shared blocked-line decision in `cli/wuwei/dispatch.py` to recognize `none` followed by `.`, `,` or `;`. Add the verbatim instruction to that same function's unanswered card reason so both build and dispatch callers receive it. Preserve owner answer matching and the recorded retro field.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Standard library runtime; pytest for tests
**Storage**: Existing day events and state; no schema change
**Testing**: Explicit affected pytest files, offline
**Target Platform**: WUWEI CLI
**Project Type**: Existing Claude Code plugin
**Performance Goals**: No meaningful change to next-step latency
**Constraints**: No new module, dependency, owner prompt, or network call
**Scale/Scope**: Two branches in one shared module and focused regression tests

## Constitution Check

- Runtime stays stdlib only.
- The shared CLI function remains the one writer and decision point.
- Regression tests fail first, then the smallest implementation passes.
- Owner questions continue through the existing owner-card record flow.
- No commit, push, or owner-only action is performed.

## Project Structure

- `cli/wuwei/dispatch.py`: shared Blocked parsing and owner-card reason.
- `tests/test_dispatch.py`: field case, punctuation, and substantive blocker regressions.
- `tests/test_build_next.py`: repeated blocked build step with an unmatched owner answer.

## Design

The latest stopped builder retro field is already selected by `_blocked`. Match `none` only at the start of that trimmed value when followed by end of string or one of the three punctuation marks. `_blocked_card` already creates the exact card and serves both build and dispatch; append the verbatim instruction when its answer is absent. Existing mismatch detail remains available.

## Verification

Run the two new tests in red, implement, then run every test file importing the changed dispatch module. Keep all tests offline and use the prescribed interpreter and explicit file paths.
