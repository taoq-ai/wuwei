# Specification analysis: door-fails-closed

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | LOW | spec.md Clarifications | The promise names guards.DOORS; the code has guards.DOOR_WORDS | Resolved: DOOR_WORDS is what item 1068 added (#1077); reused as is |
| A2 | Ambiguity | LOW | spec.md Assumptions | "a Write or Edit" read as the guards' edit set, MultiEdit and NotebookEdit included | Recorded as an assumption with what overturns it |
| A3 | Coverage | LOW | spec.md How this fails 3 | A refusal whose record failed leaves no refused row | Accepted: stderr carries it; the item asks only that the deny reaches the harness |
| C1 | Coverage | LOW | tasks.md | Acceptance 4 (3,000 lines) has no new test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 decision kept when record fails | yes | T004, T008 | |
| FR-002 deny naming the error | yes | T001, T002, T003, T009 | |
| FR-003 door from DOOR_WORDS, MCP, edits | yes | T002, T005, T009 | |
| FR-004 others fail open | yes | T005, T006, T014 | |
| FR-005 runtime budget | yes | T010, T011 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
