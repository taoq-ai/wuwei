# Specification analysis: wide-specs

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | promise (2) | Whether a contract file pattern (OpenAPI, `.proto`) inside `specs/` also takes arch | Resolved in Clarifications and Assumptions: yes, the contract rule applies to spec files too |
| A2 | Ambiguity | LOW | promise (1) | Whether a code file under `specs/` counts twice | Resolved: one filter, each file once |
| C1 | Coverage | MEDIUM | `gate_gaps` | The delta rule changes through `needed` with no test of its own | Resolved: T003 pins a long docs delta, a 200 and a 201-line spec delta, and a spec contract delta |
| C2 | Coverage | LOW | acceptance 1 | Holds on main already, so it cannot run red | Pinned anyway; noted in SC-001 |
| U1 | Underspecification | MEDIUM | code under `docs/` | `docs/conf.py` is not code to `needed`, so a 300-line one no longer takes arch through the count of every line (main: arch; head: none) | Resolved as an assumption in spec.md: code keeps its existing meaning; code under `docs/` taking no gate at any size is a candidate item outside the promise |

No open finding: A1, C1 and U1 (MEDIUM) are resolved; A2 and C2 are LOW and resolved.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 wide counts code and specs | yes | T001, T002, T006 | |
| FR-002 spec contract takes arch | yes | T001, T007 | |
| FR-003 delta rule follows | yes | T003 | |
| FR-004 rules, agents, vendor, runtime | yes | T004, T008, T009, T010 | |

## Constitution alignment

Stdlib only, test first, no config key, no new door, runtime within the cap. No violation.

## Metrics

- Requirements: 4; tasks: 10; coverage 100 percent
- Critical issues: 0; high: 0
