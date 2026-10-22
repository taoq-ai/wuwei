# Implementation Plan: the owner may accept a full-tier spec gap, and a finding row is recorded whole

**Branch**: `leone/1223` | **Spec**: `specs/spec-gap-exception/spec.md`

## Summary

Take `specs/`, `openspec/` and `no spec in the diff` out of the question guard's process pattern.
In `hook.exception_refs`, keep the text up to the last `|` before cutting the gap at its first
sentence break.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_guards.py and tests/test_hook.py. Runtime 3,396 of 3,400
lines at 6828776; this item may add 2.

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: the question door and the merge door now agree on which spec gaps are
  the owner's.
- III. An auditor: no new door; the question door refuses less, only for gaps that hold a merge.
- V. Test first: the new tests ran red on 6828776's code (14 failed, 7 passed) before the change.
- VI. Budgets: no config key; runtime unchanged (both edits are in place).
- VII. Security first: the merge door's exact match is unchanged; a longer or shorter recorded gap
  waives nothing.

## Design

- guards.py, AskUserQuestion branch: the pattern becomes
  `r"template's sections|changed lines|open [0-9]+ days"`.
- hook.py, `exception_refs`: `tail[:(cut := tail.rfind('|') + 1)] + re.split(r'\.\s|\?', tail[cut:],
  maxsplit=1)[0]`, then strip and drop a trailing `.` as before. With no `|`, `cut` is 0 and the
  result is the old one.

## Lines

guards.py 0, hook.py 0: runtime stays at 3,396.

## Probes

- `specs/spec-gap-exception/question_probe.py`: 14 gap kinds x 3 tiers x 6 question tails, each
  printed gap read from `wuwei evidence`, end to end through the guard, the hook and the evidence.
- `specs/spec-gap-exception/route_probe.py`: the route corpus through `guards.pre_tool` at main and
  at the head, verdict and reason.
- `specs/spec-gap-exception/mutants.py`: 12 mutants of the two changed expressions, on both copies.
