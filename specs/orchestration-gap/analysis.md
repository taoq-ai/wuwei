# Specification analysis: orchestration-gap

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance, the probe's recorded result and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM (closed) | spec.md Clarifications | The item put hook.py out of scope; the probe shows the Stop guard hides the line on a resumed day | Resolved: the brief puts the guard in scope; only the one guard line changes, and the route differential shows which Stop cases move |
| A2 | Coverage | LOW | spec.md How this fails 1 | The status session comes from CLAUDE_CODE_SESSION_ID; a harness without it shows both lines while seats run | Recorded as an assumption; a duty only, never a merge hold |
| A3 | Inconsistency | LOW (closed) | spec.md Composition | hook.running lost its runtime caller | Resolved in the merge round: removed from both copies, its tests read board.running |
| A4 | Ambiguity | LOW (closed) | spec.md Clarifications | "Open PRs" and "green head" were not defined by the item | Resolved: the distinct PRs the board lists; a head whose row has no CI gap and no required check missing |
| A5 | Coverage | LOW | tasks.md T016 | Four tests fail locally at main and the head (bash 3.2) | Not this change; CI runs them |

No open finding above LOW. A1 was MEDIUM and is closed.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 team row | yes | T001, T002, T004, T005, T009 | |
| FR-002 board.running | yes | T003, T009 | |
| FR-003 Stop guard | yes | T007, T011 | |
| FR-004 duty | yes | T006, T010 | |
| FR-005 runtime budget | yes | T016, T020 | +12, then -7 for hook.running |
| FR-006 charter and skill | yes | T013 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
