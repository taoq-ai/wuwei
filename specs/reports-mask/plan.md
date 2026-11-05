# Implementation Plan: a kept seat report is masked before it is written

**Branch**: `fix/reports-mask` | **Spec**: `specs/reports-mask/spec.md`

## Summary

Mask `guards.SECRETS` and the canary in the report `subagent_stop` keeps, and compare masked text
wherever the hook checks a kept report against what the planner was shown.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py and tests/test_native_evidence.py. Runtime budget
4,000 lines; main is at 3,904 and the item's budget is +2, +4 after the fix round's helper.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; the masking expression is the one the hook already uses.
- V. Test first: the two new masking tests ran red (2 failed) before the change.
- VI. Budgets: no config key; runtime at 3,906.

## Design

- `subagent_stop`: read the canary beside the reports folder, mask the report into `masked`, and use
  it for the repeat check and the write.
- `deliver`: the canary read moves above the notification check, which masks the notification's
  `<result>` before comparing it with the kept text.
- `_native_told`: masks the Codex final answer's text before comparing it with the kept text.
- `docs/design.md`: the SubagentStop row says the kept report is masked.

## Lines

hook.py 743 to 745: runtime 3,904 to 3,906. Fix round: `mask()` adds 4 lines with its spacing and
frees 2 (the `redact` lambda and the second line of the `_native_told` compare): runtime 3,908.
