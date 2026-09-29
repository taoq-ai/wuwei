# Implementation Plan: Intraday intake and autostart

**Branch**: `176-intraday-intake` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Connect sweep and seat-free discovery to trusted intake. Validate candidate evidence using the existing plan lint, apply autostart and capacity policy, then admit safe items or queue owner decisions. Reuse the existing state writer and build action.

## Technical Context

- Python 3.11+, stdlib runtime, pytest tests.
- Existing day state and append-only events are the storage boundary.
- No new adapter or configuration key is needed.

## Constitution Check

- Test first for each behavior.
- Exit 2 with a reason on unreadable inputs.
- Keep trusted records behind dedicated CLI producers.
- Reuse discovery, plan lint, state and build modules.

## Implementation

1. Test candidate admission and routing for each mode, unsafe evidence, CAP and budget.
2. Add `plan add` using existing plan lint and policy.
3. Test and connect discovery intake at sweep and seat-free events.
4. Reserve trusted state and event producers, then verify the full suite.

## Deferred

- Automatic creation of briefs and worktrees belongs to the existing build preparation flow. Intake returns a build request until those inputs exist.
