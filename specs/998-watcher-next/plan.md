# Implementation Plan: Arm the PR stream watcher from next

**Branch**: `998-watcher-next` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

## Summary

Use the existing `next` runnable set and recorded background wait. Add a watcher action when today's owned PRs remain open and housekeeping reports no live wait. The set reaches the existing Stop wake without changing its hook.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Python standard library
**Storage**: Existing day state, cached PR listing and event log
**Testing**: pytest with fake process host
**Target Platform**: Existing WUWEI CLI
**Project Type**: CLI plugin
**Performance Goals**: Reuse reads already made by `next`
**Constraints**: No Stop hook edit, no owner card, no new state writer
**Scale/Scope**: One workspace, one watcher

## Constitution Check

- Runtime remains stdlib only; no subprocess in the core.
- Reuse the recorded background path and trusted process ledger.
- Tests precede code and use fake host measurements.
- No state schema, event kind or adapter is added.
- Scope is the current WUWEI workspace; errors remain unmeasured.

## Project Structure

- `cli/wuwei/commands/next.py`
- `charters/planner.md`
- `skills/wuwei-plan/SKILL.md`
- `tests/test_next.py`
- `tests/test_goal_refill.py`

## Design

Read owned PR references and the cached listing already used by `next`; exclude terminal PRs and finished items. Use `watch.housekeeping`'s `live_waits` output to decide whether arming is due. Add the background command as a runnable set launch, preserving its wrapper and no owner card. The existing Stop hook responds to the set row. Avoid resolving dispatch launches when the set contains only the watcher.

No research, data model, contract or quickstart artifact is needed: this changes one derived action using existing data and command paths.
