# Specification analysis: doors-by-rest

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | promise, contents/ and git/refs/ | "refused like a push to the default branch" could mean only writes on the default branch | Resolved in Clarifications: every write method on these routes is refused, as the promise lists them without a branch; no seat route uses them |
| A2 | Ambiguity | LOW | promise, graphql | The mutation list names "a branch protection or ruleset mutation" without names | Resolved: BranchProtectionRule and RepositoryRuleset as name parts, so create, update and delete all match |
| U1 | Underspecification | LOW | promise, Outside | `-F query=@file` is outside, but the field reader reads every `-F k=@file` | Resolved in Clarifications: it is read as gh reads it; tested, not promised |
| U2 | Underspecification | LOW | acceptance 1 | A REST create with no head field | Resolved: the current branch, as gh pr create does |
| C1 | Coverage | LOW | --input - and -F body=@- | A stdin body is not read | Recorded under Assumptions: the door then refuses rather than passes when gates are missing |
| I1 | Inconsistency | LOW | plan, budget | The estimate was +18; the change is +36 | Within the cap (2,996 of 3,000); the reader that follows gh's parser is the difference |

No open finding above LOW: A1 is resolved.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 gh api read as gh reads it | yes | T001, T003, T004, T006, T013 | probe plus tests |
| FR-002 one route table | yes | T003, T006, T009, T013 | |
| FR-003 graphql mutations refused | yes | T007, T008, T013 | |
| FR-004 gh pr new | yes | T005, T013 | |
| FR-005 MCP file tools | yes | T010, T011, T014 | |
| FR-006 charter, agents, SECURITY.md | yes | T015, T017 | |
| FR-007 budget and routes | yes | T002, T016, T019, T020 | |

## Constitution alignment

Stdlib only, test first, no config key, no new door, runtime under 3,000 lines. No violation.

## Metrics

- Requirements: 7; tasks: 20; coverage 100 percent
- Critical issues: 0; high: 0
