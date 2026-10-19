# Implementation Plan: an owner's exception waives only the gap it names, matched exactly

**Branch**: `fix/excepted-exact` | **Spec**: `specs/excepted-exact/spec.md`

## Summary

Replace the two-way substring test in `evidence.excepted` with set membership of a normalised text:
the gap's own text, or the gate list a gate gap names.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_evidence.py. Runtime 2,986 lines at 8c1939e; this item may
add 3.

## Constitution Check

- I. Stdlib only: yes, `re` and `str` methods.
- II. Evidence over steps: a waiver now needs the gap named. Spacing and end-mark variants that main
  missed now count (832 probe pairs); no part of a gap waives it.
- III. An auditor: no door changes.
- V. Test first: the new tests ran red on 8c1939e's code (4 failed, 178 passed in tests/test_evidence.py) before the change.
- VI. Budgets: no config key; runtime at 2,988.
- VII. Security first: a short accepted gap can no longer drop a security or owner review gap.

## Design

- `GATES`: a module regex for the gate list of `gates missing at head <sha>: <gates>` and `no gate
  passed at head <sha> (a delta review by <gate>)`, anchored at the start, `[\w, ]+`.
- `norm`: `casefold`, split and join on whitespace, `rstrip(' .,;:!?')`, `removesuffix('[waiting]')`,
  `rstrip` again. Linear in the text; no regex backtracking.
- `accepted`: the set of normalised gaps of approved exception rulings at this PR and head whose gap
  is a string, minus `''`.
- A gap is dropped when its normalised text or its normalised gate list is in `accepted`.

## Lines

evidence.py grows by 2 lines: runtime 2,986 to 2,988.

## Probe

`specs/excepted-exact/probe.py` crosses 71 printed gaps with 9,183 generated accepted gaps at main
and at the head, and builds 568 owner questions from the printed gaps through the guard and the
hook. Counts are in the PR body.
