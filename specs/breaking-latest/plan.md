# Implementation Plan: a breaking change is read from the latest arch verdict

**Branch**: `fix/breaking-latest` | **Spec**: `specs/breaking-latest/spec.md`

## Summary

`evidence.breaking_gaps` reads Breaking from the latest arch verdict that read newer code on the
PR's line, instead of any verdict ever.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_evidence.py. Runtime budget 3,000 lines. Main is at
2,976, and this item adds 4. The item's budget was 2; the planner accepted the overrun in the
security fix round.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; an existing gap reads fewer, newer verdicts. The ancestry check is
  the compare call `gate_gaps` already makes.
- V. Test first: round 1 ran red (3 failed); the security round ran red (5 failed) before the fix.
- VI. Budgets: no config key, no ledger kind; runtime at 2,980.

## Design

- `cli/wuwei/evidence.py` `breaking_gaps`: walk the arch verdicts from `verdicts()` that carry a
  `breaking` key, oldest first. A verdict replaces the current one when it says yes, or is the
  first. A `no` replaces it only when its head differs from the current head, descends from it,
  and is an ancestor of the PR head (both checks by the existing ancestry helper). The gap rises
  when the title or body declares a break or the verdict reached says yes.
- `.claude/wuwei/` re-vendored with `setup.vendor('.')`.
