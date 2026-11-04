# Specification analysis: reports-mask

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | LOW | spec.md How this fails 1 | The promise names only the write; the notified checks in deliver and _native_told read the kept text and would stop matching | Resolved: FR-003 masks the notification side, tests T003 and T004 |
| A2 | Ambiguity | LOW | spec.md Assumptions | A pre-upgrade pending report holding a secret may be given once more | Recorded as an assumption with its cost |
| A3 | Inconsistency | LOW | spec.md Clarifications | The brief says reuse the masker; the hook has no shared helper, only one inline expression | Resolved: the same expression is reused inline, no new helper |
| C1 | Coverage | LOW | tasks.md | FR-004 (runtime budget) has no new test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 masked write | yes | T001, T002, T004, T006 | |
| FR-002 masked repeat check | yes | T003, T006 | |
| FR-003 masked notified checks | yes | T003, T004, T007 | |
| FR-004 runtime budget | yes | T009 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
