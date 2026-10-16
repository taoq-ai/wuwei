# Specification analysis: gate-charters

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Dependency | LOW | spec.md Assumptions | tests/fixtures/routes.json is not on main yet (route-fixtures adds it) | Recorded; a gate that cannot run the differential writes `not run` with the reason |
| A2 | Ambiguity | LOW | spec.md Clarifications | The promise names SubagentStop; since #1082 the hand-back also attests | Resolved: the planner rule names both |
| A3 | Dependency | LOW | spec.md Clarifications | codex-attest-probe is parked, so the Codex route is undecided | Resolved: gates run as Claude seats until the probe records an attested seat |
| A4 | Inconsistency | LOW | charters/_common.md | Boundaries items renumber 2-4 to 3-5 | No file cites them by number |
| C1 | Coverage | LOW | tasks.md | Acceptance 2 to 4 are wording with no new test | Held by reading the files; acceptance 1 by the existing drift tests |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 never edit, -2 rule | yes | T002, T003 | |
| FR-002 scratch folder | yes | T004 | |
| FR-003 planner gate brief | yes | T005 | |
| FR-004 reference and codex pages | yes | T006, T007 | |
| FR-005 build, vendor, no runtime | yes | T008, T009, T010 | |

## Constitution alignment

No conflict: docs only, no door change, no config key, runtime budget untouched.
