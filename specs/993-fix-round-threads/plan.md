# Implementation Plan: Fix round threads and gate receipt

**Branch**: `993-fix-round-threads` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

## Summary

Reuse the owed-reply list to collect every unanswered review request. Extend the active build record with supplementary feedback and deliver feedback queued during a running seat in a continuation after stop. Let the gate stop hook call the existing `dispatch.receive` producer after marking the seat stopped. Improve round mismatch messages.

## Technical Context and Constitution Check

Python 3.11+ stdlib runtime and pytest tests. State writes use the existing atomic writer. The code host stays behind its adapter. No new state producer, module, config or dependency. Tests use fake host and VCS ports. The issue's explicit test-file command controls validation.

## Root Cause

`pr_actions._thread` selects one owed reply before constructing feedback. `_fix_round` returns an existing build action without adding new feedback. `build.next_action` refuses an unrelated brief while a build is unfinished. The gate stop hook never calls `dispatch.receive`.

## Implementation

1. Test multi-thread feedback, then build one feedback body from all owed replies.
2. Test ready, running, completed, held and recovered supplementary feedback. Queue it on the build record until launch confirms delivery or a continuation or new round consumes it.
3. Test stop receipt, corrected verdict retry and round wording. Resolve the gate and round in one dispatch helper shared by the stop hook and manual receive.
4. Run every test file importing changed modules and review the diff.
