# Specification analysis: merge-evidence

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise (1) | "owner review ruling" was not defined in code terms | Resolved in Clarifications: a ruling with no kind, as hook._answers writes it |
| A2 | Ambiguity | LOW | item promise (2) | Whether a generated release PR skips the CI read | Resolved in Clarifications: no, the generated exemption stays on the no-test gap |
| C1 | Coverage | LOW | spec How this fails 1 | An exception naming the owner review gap still clears it | Accepted: that is the exception path (`excepted`), outside owner_approved |
| C2 | Coverage | LOW | spec How this fails 2 | Docs CI that should hold a docs-only merge | Accepted as the plan item's assumption; owner can overturn |
| B1 | Breaking | MEDIUM | spec Breaking | A merge that passed on a breaking or exception ruling now holds | Declared with migration; commit carries BREAKING CHANGE |

No open finding above MEDIUM.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 owner review rulings only | yes | T002, T007 | |
| FR-002 docs-only skips the gap | yes | T003, T008 | |
| FR-003 unreadable host named | yes | T004, T008, T009 | |
| FR-004 pull_request_target counts | yes | T001, T005, T008 | |
| FR-005 vendored, within budget | yes | T012, T013 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime within budget.
