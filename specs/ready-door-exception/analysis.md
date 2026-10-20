# Specification analysis: ready-door-exception

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md Assumptions; item acceptance 6 | Acceptance 6 says only ready-door routes move, while the promise drops the not-counted lines from evidence.gaps, which the merge door reads | Resolved: recorded as an assumption; the 22 merge routes that move do so only under an approved exception for that PR and head with a stray verdict file, and the PR lists them |
| A2 | Coverage | LOW | spec.md How this fails 1 | A ruling whose PR differs in case from the door's reading waives nothing | Accepted: fails closed, the same exact match as wuwei evidence |
| A3 | Coverage | LOW | spec.md How this fails 2 | The door checks the ruling at the compare head, which can differ from headRefOid | Accepted: the gap the owner accepts names the same head, so text and head agree; another sha waives nothing |
| A4 | Coverage | LOW | mutants.py | One mutant (a "verdict " gap without the " not counted: " check) survives | Accepted: equivalent, only evidence.uncounted prints a gap starting "verdict " |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 ready door applies excepted | yes | T001, T002, T003, T007, T012, T013 | |
| FR-002 create door unchanged | yes | T013 | create routes stay shut under the exact ruling |
| FR-003 not-counted lines go | yes | T004, T005, T008, T014 | |
| FR-004 budget and vendored copy | yes | T009, T011 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
