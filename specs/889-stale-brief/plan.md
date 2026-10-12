# Implementation Plan: an unfinished build whose worktree moved past its brief takes a new brief

**Branch**: `889-stale-brief` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`next_action` lets a newer brief replace an unlaunched build whose brief the worktree moved
past, keeping the record's start head and fix rounds.

## Technical Context

Stdlib Python 3.11+. No new state field, no new event kind (`build.started` as today).

## Constitution Check

- III: the one shared spot, `next_action`, which `build next`, `next` and `dispatch` all call.
- IV: test first, red, then code.
- V: one condition and one record spread; the guard is unchanged.

## Files to edit

- `cli/wuwei/commands/build.py` `next_action`: `stale` when the record is `ready`/`launch` on
  the same worktree and today's logged HEAD of its brief is not the vcs HEAD; a stale record is
  replaced, spread into the new one, with `start` kept (or the old brief's logged HEAD).
- `tests/test_build_next.py`: one parametrized test (moved, legacy, unmoved).
- Review round: `stale` needs an unlogged brief or a logged HEAD that differs (F1); a stale
  fix-round launch keeps its feedback tail (F2); a record with no previous one starts at the
  brief header's `Merge-base:` sha (F4), else HEAD.

## Verification

Every test file importing `wuwei.commands.build` under 3.12; build, brief, hooks, agent_launch
and next files under 3.11.
