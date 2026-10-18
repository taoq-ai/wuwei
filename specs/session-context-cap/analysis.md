# Specification analysis: session-context-cap

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | MEDIUM (closed) | spec.md Clarifications | The promise keeps "the board"; goals and standards were also inlined and are now left out | Resolved: the run skill reads both at its step 2, the pointer names their folder; recorded as an assumption |
| A2 | Inconsistency | LOW | spec.md How this fails 2 | The final cut can drop the left-out count when the board ends in a line that is not an item | Recorded as residual risk; the cap holds, and a test holds it with 30 andon lines |
| A3 | Ambiguity | LOW | spec.md Clarifications | "Lowest items" first holds per repository only; the board lists repositories in name order | Resolved: spec says which lines go; a board-wide score order would change board.py, outside the item's files |
| A4 | Coverage | LOW | plan.md Measurements | The 200-item main figure is unmeasured | The head figure is measured; main's grows with the board and is over the cap at 0 items already |
| A5 | Inconsistency | LOW | docs | design.md and hooks.md listed goals and standards as inlined | Resolved: both rows and the first-day line updated |

No open finding above LOW. A1 was MEDIUM and is closed in the spec.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 at most 10,000 characters | yes | T001, T002, T003, T007 | |
| FR-002 CLI path, planner.md path, the way, Decisions and Done | yes | T001, T005 | |
| FR-003 left-out count | yes | T002, T006 | |
| FR-004 runtime budget | yes | T009 | tests/test_setup.py size test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
