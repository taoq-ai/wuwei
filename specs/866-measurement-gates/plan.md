# Implementation Plan: Measurement Handoff Gates

**Issue**: #866 | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Use the existing builder handoff record for a measurement seat. Skip specification and fast checks for an admitted measure item. Tier a verified zero diff with no risk flags as one quality gate. Point the brief to the handoff record and existing workspace artifacts.

## Technical Context

- Python 3.11+ stdlib runtime, pytest development tests.
- Existing build result and scratch directory provide the evidence.
- No new role, module, or storage format.

## Constitution Check

- Runtime remains stdlib-only.
- Tests reproduce BACKFILL-EVIDENCE before the fix.
- No new integration or speculative abstraction.
- A measured diff prevents the zero-diff exception.
- The design document remains owner-only.

## Source Changes

- `cli/wuwei/specmode.py`: skip measure spec steps.
- `cli/wuwei/commands/build.py`: complete a measurement without fast checks and compare its worktree with the recorded starting HEAD.
- `cli/wuwei/dispatch.py`: one default quality gate, flagged gates, tiering from the recorded starting HEAD, a file reference to the handoff evidence, and a verdict path in the done action.
- `cli/wuwei/brief.py`: name the workspace scratch directory as the sole measurement scratch destination.
- `cli/wuwei/closing.py`, `cli/wuwei/report.py`: omit finished measurements from open work and list their current verdict files in Done.
- A quality PASS completes the measurement without PR raising or a polish build.
- Existing build, dispatch, and spec tests: prove the field case.
