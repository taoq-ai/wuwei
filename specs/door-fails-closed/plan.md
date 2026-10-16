# Implementation Plan: an error inside a door refuses the call

**Branch**: `claude/door-fails-closed` | **Spec**: `specs/door-fails-closed/spec.md`

## Summary

`hook.pre_tool` keeps the guards' decision when its record fails; `hook.handle` turns an exception on
a door call into a deny that names the error.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py. Runtime budget 3,000 lines; main was at 2,996.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; existing doors stop failing open.
- V. Test first: the new tests ran red (16 failed) before the change.
- VI. Budgets: no config key; runtime at 3,000.

## Design

- `pre_tool`: the `ws.record` of the decision sits in `try`; an exception prints to stderr and the
  decision is returned as before.
- `handle`: after recording `hook.error` (best effort), when the event is PreToolUse and
  `door(payload)` is true, return `permissionDecision: deny` with a reason that holds the error type
  and message (already capped at 300 characters).
- `door(payload)`: tool name as a string; `tool_input` read only when it is a mapping. True for the
  edit tools, the MCP merge, auto-merge and create-PR tools, or a Bash command where every regex of
  some `guards.DOOR_WORDS` entry is found in the raw text.

## Lines freed

`transcript(payload)` reads the transcript once and returns the last report text and the token
total; `last_text` falls back to it in one line and `subagent_stop` reads the tokens from it. The
`tokens` function goes. Net: hook.py goes from 2,996 to 3,000 runtime lines in total.
