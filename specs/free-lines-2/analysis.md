# Specification analysis: free-lines-2

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise (1) | The helper keeps the name replay, which would shadow the replay module in the test file | Resolved in Clarifications: named replay_case |
| C1 | Coverage | LOW | acceptance 5 | No new test for two named items | Resolved in Clarifications: pinned by test_watch.py::test_a_pr_naming_two_items_links_both_and_closes_both_once_merged; a first-item-only mutant fails it |
| C2 | Coverage | LOW | spec How this fails 3 | The board TTL value has no dedicated assertion | Accepted: the argument is explicit in the diff; behaviour-neutral fold |
| C3 | Coverage | LOW | acceptance 1 | "2,962 lines or fewer" has no dedicated assertion | Held by the line count at the head and the 3,000 budget test; the room is for draft-raise |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 replay helper moved | yes | T002, T007 | |
| FR-002 board._list folded | yes | T002, T008 | |
| FR-003 items_named inlined | yes | T002, T009 | |
| FR-004 guards._default folded, same behaviour | yes | T004, T005, T010, T013 | |
| FR-005 re-vendored | yes | T011, T012 | drift test |
| FR-006 no outward change | yes | T003, T012 | routes.json test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget reduced.
