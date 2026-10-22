# Specification analysis: spec-gap-exception

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | MEDIUM | spec.md How this fails 1 | A row cut at 100 characters with a break after its last cell edge is recorded short | Accepted: fails closed; 2 of 702 real rows; a follow-up can cut the printed row at a cell edge |
| A2 | Coverage | LOW | spec.md How this fails 2 | A question with its own pipe is recorded long | Accepted: fails closed; the guard's refusal text names the shape |
| A3 | Ambiguity | LOW | spec.md Clarifications | Which process fit lines the guard still sends back | Resolved: the three the item names; the others were never sent back |
| A4 | Coverage | LOW | tasks.md | The probe outputs are not committed | Accepted: the probes regenerate them; the PR body carries the counts and the corpus sha256 |

No open finding above MEDIUM.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 process words only | yes | T001, T005, T007 | |
| FR-002 cut after the last pipe | yes | T003, T004, T008 | |
| FR-003 budget and vendored copy | yes | T009, T011 | |
| FR-004 route corpus unchanged | yes | T012 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
