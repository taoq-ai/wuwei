# Specification analysis: ci-not-started

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise | "unreadable Actions host" did not list the odd reply shapes | Resolved in Clarifications: GhError, AttributeError, TypeError, as review_contexts |
| A2 | Ambiguity | LOW | item promise | Whether a failed read is cached | Resolved in Clarifications: the exception leaves _cached before it writes |
| C1 | Coverage | LOW | spec How this fails 1 | A path-filtered pull_request workflow holds a docs-only PR | Accepted: a held merge, never a false pass; the owner can accept an exception |
| C2 | Coverage | LOW | spec How this fails 2 | A day-old cached "no CI" for a repository that just added CI | Accepted: same as main for that window |
| U1 | Underspecification | LOW | plan Design 2 | The door needs no code change | Pinned by test_auto_merge_is_refused_while_ci_has_not_started |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 CI not started gap | yes | T002, T009 | |
| FR-002 read only on empty rollup, cached a day | yes | T002, T005, T009 | |
| FR-003 unreadable host counts as CI | yes | T004, T009 | |
| FR-004 no pull_request run, no gap | yes | T003 | holds on main |
| FR-005 --auto refused on the new gap | yes | T006, T010 | |
| FR-006 re-vendored | yes | T013, T014 | drift test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime within budget.
