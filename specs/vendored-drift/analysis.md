# Specification analysis: vendored-drift

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | LOW | item acceptance 4 | The item says "1.2.0 today"; main is 1.2.1 after release #1072 | Resolved in Clarifications: the copy carries the root version at the head |
| U1 | Underspecification | LOW | spec.md Clarifications | The promise does not say whether a project's own agents in `.claude/agents/` are drift | Resolved: only files vendor writes are compared there; recorded as an assumption |
| C1 | Coverage | LOW | tasks.md | Acceptance 5 (3,000 lines) has no new task test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget; this item adds no runtime line |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 drift test names paths | yes | T001, T002 | |
| FR-002 extras only in owned folders | yes | T002 | |
| FR-003 release-please bumps the copy | yes | T003, T005 | |
| FR-004 re-vendor at head | yes | T006 | |
| FR-005 no runtime lines | yes | T007 | size test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
