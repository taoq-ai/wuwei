# Implementation Plan: a breaking change is read from the latest arch verdict

**Branch**: `fix/breaking-latest` | **Spec**: `specs/breaking-latest/spec.md`

## Summary

`evidence.breaking_gaps` reads the `Breaking:` field of the last arch verdict that carries one,
instead of any verdict ever.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_evidence.py. Runtime budget 3,000 lines; main is at
2,976, and this item adds 1 (its budget is 2).

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; an existing gap reads fewer, newer verdicts.
- V. Test first: the new tests ran red (3 failed) before the change.
- VI. Budgets: no config key, no ledger kind; runtime at 2,977.

## Design

- `cli/wuwei/evidence.py` `breaking_gaps`: build `arch`, the arch verdicts from `verdicts()` that
  carry a `breaking` key (oldest first), and raise the gap when the title or body declares a break
  or `arch[-1]['breaking']` is set.
- `.claude/wuwei/` re-vendored with `setup.vendor('.')`.
