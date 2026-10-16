# Implementation Plan: a "Proceed" answer to the breaking: question records the owner's approval

**Branch**: `claude/breaking-proceed` | **Spec**: `specs/breaking-proceed/spec.md`

## Summary

Add "proceed" to the yes prefixes in `hook._answers`.

## Technical Context

Python 3.11 stdlib. Test in tests/test_breaking.py. Runtime budget 3,000 lines; main is at 2,999,
and this item is net 0.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; the existing answer recorder reads one more word.
- V. Test first: the new parametrized test ran red (2 failed) before the change.
- VI. Budgets: no config key; runtime at 2,999.

## Design

- `cli/wuwei/hook.py` `_answers`: the `startswith` tuple becomes
  `('yes', 'approve', 'accept', 'proceed')`.
- `.claude/wuwei/` re-vendored with `setup.vendor('.')`.
