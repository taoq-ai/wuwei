# Specification analysis: verdict-at-head

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance, the constitution, and #1135's walk in `breaking_gaps`.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md Assumptions | The promise says a verdict counts only on this PR; the spec keeps a finding from another PR of the item at an ancestor head | Resolved: the acceptance names a PASS; dropping findings loosens the gate. Recorded under Assumptions with what overturns it |
| A2 | Coverage | LOW | spec.md How this fails 3 | At the create and ready doors no PR is read, so a PASS for another PR of the item in the same repository counts there | Accepted for this item: the fix is in guards.py, outside the promise's files; reported as a candidate |
| A3 | Ambiguity | LOW | spec.md Clarifications | A finding at an older head after a finding at a newer head | Resolved: the newer one holds; fixture and the probe's no-clear property |
| C1 | Coverage | LOW | tasks.md | FR-005 (runtime size) has no new test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget and the measured +5 |
| C2 | Coverage | LOW | tests/test_guards.py | Fixtures that named acme/app#42 while their door read o/r stop counting | Resolved: pointed at the PR their door reads; the route probe lists every moved route |

No open finding above MEDIUM, and none open at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 the shared walk, ancestors only | yes | T001, T003, T004, T006 | |
| FR-002 a PASS for this PR | yes | T002, T004, T006, T007 | |
| FR-003 a finding displaces a pass | yes | T004, T006 | |
| FR-004 the carry rule unchanged | yes | T010 | existing delta tests green |
| FR-005 budget | yes | T010 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime under 3,400.
