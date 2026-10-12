# Implementation Plan: selective second opinion

**Branch**: `871-codex-parallel` (batch) | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`dispatch.second_opinion(config, row, tier)` decides an item's second opinion (off, light,
selector). `tier` uses it. `_released` re-checks a recorded one at `dispatch next` and
`dispatch opinion` and drops it from the tier record when it no longer applies.

## Technical Context

Python 3.11+ stdlib. Files: `cli/wuwei/workspace.py` (schema), `cli/wuwei/dispatch.py`,
`cli/wuwei/signal.py` and `cli/wuwei/commands/why.py` (the new event kind),
`templates/workspace/config.toml`, `docs/site/configuration.md`. Tests:
`tests/test_dispatch.py`, `tests/test_workspace.py`.

## Constitution Check

- II: config validation fails closed on an unknown flag name (schema choices).
- III: one decision function, used at tiering and at release.
- IV: failing tests first.
- V: the stored tier record stays the single source every reader uses; the release writes it
  once, so `merge`, `derive`, `report` and `shepherd` need no change.

## Changes

1. `workspace.py`: `gates.second_opinion_when = [(str, None, ("trust_surface",
   "boundary_relevant", "agent_surface"))]`.
2. `dispatch.py`: `second_opinion(config, row, tier)`; `tier` calls it; `_released(root, config,
   data, item)` drops `gates.second_opinion` (kind `gate.released`) and returns fresh data;
   `next_step` calls it before `gate_set`, `opinion` before reading the record.
3. `signal.py` SILENT and `why.py` EVENT_PRODUCERS gain `gate.released`.
4. Template and configuration page document the key.

## Fix round 1 (review FIX)

- F1: `_released` returns unchanged when the second opinion's latest record (delta, else
  initial) is not PASS or has a `blocks: yes` finding. Only a pending or passed second opinion
  is released.
