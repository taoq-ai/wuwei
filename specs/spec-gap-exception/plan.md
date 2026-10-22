# Implementation Plan: the owner may accept a full-tier spec gap, and a finding row is recorded whole

**Branch**: `leone/1223` | **Spec**: `specs/spec-gap-exception/spec.md`

## Summary

Take `specs/`, `openspec/` and `no spec in the diff` out of the question guard's process pattern.
In `hook.exception_refs`, keep the text up to the last `|` before cutting the gap at its first
sentence break.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_guards.py, tests/test_hook.py and (round 1)
tests/test_evidence.py. Runtime 3,396 of 3,400 lines at 6828776; this item may add 2, raised to 6
for round 1.

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: the question door and the merge door now agree on which spec gaps are
  the owner's.
- III. An auditor: no new door; the question door refuses less, only for gaps that hold a merge.
- V. Test first: the new tests ran red on 6828776's code (14 failed, 7 passed) before the change;
  round 1's ran red on b6d0635's code before its fix (counts in the PR body).
- VI. Budgets: no config key; runtime +0 lines in round 1, within the +6 it allows.
- VII. Security first: the merge door's exact match is unchanged; a longer or shorter recorded gap
  waives nothing, and (round 1) every open row and checklist is printed, so a yes waives only what
  the owner saw.

## Design

- guards.py, AskUserQuestion branch: the pattern becomes
  `r"template's sections|changed lines|open [0-9]+ days"`.
- hook.py, `exception_refs` (round 1): `cut` is the end of the last `|` followed by optional space
  and a `.`, a `?` or the end of the question, found only when the text after the references holds
  `: |` (a finding row), else 0. The gap is `tail[:cut]` plus the rest up to its first `. ` or `?`,
  then stripped of a trailing `.` as before. With `cut` 0 the result is main's.
- evidence.py, `_rule` (round 1): returns a list of gap texts. A checklists folder gives one per
  file with an unchecked box; `analysis.md` gives one per open CRITICAL or HIGH row. A row longer
  than 100 characters is cut after its last `|` within the first 100, or at 100 when no `|`
  follows the first; rows whose cuts are equal print whole. `spec_gaps` flattens the lists.

## Lines

Round 0: guards.py 0, hook.py 0. Round 1: evidence.py -2, hook.py +2. Runtime 3,396 at main and at
the head (+0 of the +6 the round allows).

## Probes

- `specs/spec-gap-exception/question_probe.py`: 21 gap kinds x 3 tiers x 11 question tails, each
  printed gap read from `wuwei evidence`, end to end through the guard, the hook, the evidence and
  (for two open rows or two checklists) the merge door.
- `specs/spec-gap-exception/refs_differential.py`: `hook.exception_refs` at main and at the head
  over the probe's questions; a question read right at main and wrong at the head is a row.
- `specs/spec-gap-exception/route_probe.py`: the route corpus through `guards.pre_tool` at main and
  at the head, verdict and reason, plain, with an approved exception for every gap the doors read,
  and with a full-tier spec PR holding two open rows and two checklists.
- `specs/spec-gap-exception/mutants.py`: mutants of each changed expression, on both copies.
