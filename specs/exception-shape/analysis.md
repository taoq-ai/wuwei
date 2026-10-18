# Specification analysis: exception-shape

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | LOW | spec.md Clarifications | The promise lists routes.json among the files; the corpus reads shell commands only | Resolved: no row added, recorded as an assumption; the corpus is read at main and head |
| A2 | Scope | LOW | spec.md FR-002 | Refusing a leading space before exception: goes past the literal ref-and-gap rule | Accepted: the promise names the shape exception_refs reads, which does not strip; recorded as an assumption |
| A3 | Ambiguity | LOW | spec.md How this fails 1 | Near shapes the hook could read are now refused | Accepted: the refusal names the shape; probe counts in the PR |
| A4 | Coverage | LOW | spec.md How this fails 3 | A gap followed by a newline records the next line too | Accepted: the recorded gap holds the written one; the exception-parser follow-up owns it |
| C1 | Coverage | LOW | tasks.md | Acceptance 4 has no new test | Held by tests/test_guards.py::test_every_route_reads_as_recorded and the main-versus-head dump |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 gap after the last ref | yes | T001, T002, T004, T006, T012, T013, T015 | |
| FR-001a no ref before the chain | yes | T012, T013, T015 | gate round 1 |
| FR-002 no leading whitespace | yes | T001, T006 | |
| FR-003 other classes unchanged | yes | T008 | existing tests in test_guards.py and test_hook.py |
| FR-004 no route moves | yes | T009 | |
| FR-005 budget and vendored copy | yes | T007, T008 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
