# Implementation Plan: a seat counts as started only when the harness launched it, and once

**Branch**: `claude/seat-count` | **Spec**: `specs/seat-count/spec.md`

## Summary

Move the `seat.started` record from `pre_tool` to `post_tool`, add the response's `agentId`, and
count running seats as a set of agent ids.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py and tests/test_codex.py. Runtime budget 3,000
lines; main is at 2,997.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door, no change to a decision; only the record moves.
- V. Test first: four new or changed tests in test_hook.py and one in test_codex.py ran red
  (5 failed) before the change.
- VI. Budgets: no config key; runtime 2,997 to 2,998.

## Design

- `pre_tool`: the five-line Agent and Task record goes.
- `post_tool`: for Agent and Task, record `seat.started` with role, description, session and
  `agent` from `tool_response['agentId']` when the response is a dict.
- `running()`: `len(started ids - stopped ids)` for today, rewritten in place.
- `codex()`: `spawn_agent` maps its response to `{'agentId': <agent_id>}`, read from a dict or a
  JSON string.

## Lines

hook.py: pre_tool minus 5, post_tool plus 5, running in place, codex plus 1. Runtime 2,997 to 2,998.
