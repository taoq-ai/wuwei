# Specification analysis: spec-gap-exception

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | MEDIUM | spec.md How this fails 1 | A row cut at 100 characters with a break after its last cell edge is recorded short | Resolved in round 1: evidence cuts a row at its last cell edge within 100 characters; 712 of 712 real rows read whole |
| A2 | Coverage | MEDIUM | spec.md How this fails 2 | A question with its own pipe is recorded long | Resolved in round 1: it broke gaps with no row, which read right on main (quality gate); only a gap that holds a row reads to the row's end now |
| A3 | Ambiguity | LOW | spec.md Clarifications | Which process fit lines the guard still sends back | Resolved: the three the item names; the others were never sent back |
| A4 | Coverage | LOW | tasks.md | The probe outputs are not committed | Accepted: the probes regenerate them; the PR body carries the counts and the corpus sha256 |
| A5 | Coverage | HIGH | evidence.py _rule, analysis.md rule | Only the first open row was printed, so a yes to it waived an unprinted CRITICAL row (security gate) | Resolved in round 1: each open row is its own gap; tests and probes hold the door on A2 until it is named |
| A6 | Coverage | MEDIUM | evidence.py _rule, checklists rule | Only the first checklist with an unchecked box was printed, so a yes to it waived the others (security gate) | Resolved in round 1: each checklist file is its own gap |
| A7 | Coverage | LOW | spec.md How this fails 2 | A row with no trailing pipe, or a pipe right after the row, is still recorded short | Accepted: fails closed, as on main; no real row here lacks its trailing pipe |

No open finding above MEDIUM. Round 1's HIGH (A5) is resolved.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 process words only | yes | T001, T005, T007 | |
| FR-002 a row reads to its end | yes | T003, T004, T008, T015, T021 | round 1 narrows it to gaps that hold a row |
| FR-003 budget and vendored copy | yes | T009, T011 | |
| FR-004 route corpus unchanged | yes | T012, T023 | round 1 adds approved exceptions |
| FR-005 each row and checklist its own gap | yes | T016, T017, T020 | round 1 |
| FR-006 cut at a cell edge | yes | T018, T020 | round 1 |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
