# Implementation Plan: build next never hands out a brief a seat already used

**Branch**: `889-stale-brief` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`next_action` binds an unbound stopped builder seat that already ran the brief and returns its
continue; a running seat waits; any other used brief asks for a fresh one.

## Constitution Check

- III: one shared spot, `next_action`.
- IV: test first.
- V: reuses `_continue` and the #889 replacement path (`unbound` counts as stale); no new state
  field, no guard change.

## Files to edit

- `cli/wuwei/commands/build.py` `next_action`: `used` seat lookup by brief path; refusals for a
  running or unmeasured seat; `unbound` makes the same-brief launch replaceable; the new record
  binds `seat` and `agent_id`, starts at the seat's `head`, and its action is `_continue`.
- `tests/test_build_next.py`: `test_a_brief_a_seat_already_ran_continues_that_seat`.

## Verification

Build, brief, hooks, agent_launch, next and dispatch test files under 3.12 and 3.11.
