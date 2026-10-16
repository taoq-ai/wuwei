# Implementation Plan: a gate's verdict is linted before its hand-back

**Branch**: `claude/verdict-handback` | **Spec**: `specs/verdict-handback/spec.md`

## Summary

Run the existing verdict check at the sentinel's SubagentHandback, record `verdict.missing` when a
stop block cannot reach the seat, and let a note leave out its file:line.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py and tests/test_verdict.py. Runtime budget 3,000
lines; main is at exactly 3,000, and this item must be net zero or fewer.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; the attest rule (role from the harness, gate must match) is the same
  `_verdict_problem`.
- V. Test first: the new tests ran red (4 failed) before the change.
- VI. Budgets: no config key; runtime at 2,997.

## Design

- `transcript(payload)` returns a third value, `ended`: whether the last report came from a
  `SubagentHandback` tool call.
- `pre_tool`: reads the role from `agent_type`. For a SubagentHandback from a `sentinel-*` role it
  calls `_verdict_problem` with the hand-back message as the last message. A problem becomes a deny
  through the existing decision path (recorded as `refused`); otherwise the guards decide as before.
- `subagent_stop`: reads tokens and `ended` from one transcript read; records `verdict.missing` on
  `stop_hook_active` or `ended`.
- `post_tool`: the Agent hand-back re-read goes (8 lines).
- `verdict.FINDING`: the `<file>:<line> ` group is optional. The blocking check needs both the place
  and `Failure:`. FORMAT says the place is optional on a note.
- `charters/_gate.md`: the hand-back is where the verdict is read; notes may leave out the place.

## Lines

hook.py 404 to 401, verdict.py unchanged in length: runtime 3,000 to 2,997.
