# Specification analysis: compound-doors

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against item compound-doors'
promise and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | LOW | spec.md Clarifications | `READ` names more programs than the promise lists (network tools, writers, sed, python) | Accepted: without them the ledger and leak doors stop reading what main read after a wrapper; pinned by T006 |
| A2 | Ambiguity | LOW | spec.md Assumptions | The first-program rule can over-read (`nohup echo git push origin main`) | Accepted: a refusal, never a pass; recorded as pre-mortem 1 |
| A3 | Coverage | LOW | spec.md How this fails 3 | An unreadable nested body once hid the outer segments from the leak and infra doors | Fixed: the `UNREAD` marker keeps the outer segments; pinned by T018 |
| C1 | Coverage | LOW | tasks.md | Acceptance 6 (3,000 lines) has no new task test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 reserved words | yes | T001, T004, T009 | |
| FR-002 first-program rule | yes | T003, T006, T009 | |
| FR-003 combined shell flags | yes | T002, T010 | |
| FR-004 unreadable nested body | yes | T005, T011, T018, T019 | |
| FR-005 timeout, stdbuf | yes | T003, T008 | |
| FR-006 net zero lines | yes | T012 | tests/test_setup.py size test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
