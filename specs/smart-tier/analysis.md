# Specification analysis: smart-tier

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against item smart-tier's
promise and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | item promise | "a change to what a guard waives or refuses" names no mechanical test | Resolved in Clarifications: guard words over the whole patch, and a missing patch counts |
| A2 | Ambiguity | MEDIUM | item promise | "a cyclomatic complexity rise" names no threshold | Resolved: a rising function reaching 10 decision nodes (McCabe over 10) |
| A3 | Ambiguity | LOW | acceptance 2 | A clear item on a risky path owes security by the path alone | Kept as written; the off-risky rows hold the complexity signal |
| C1 | Coverage | HIGH | lowering | A seat-written domain could lower the gates on an owner or guard change | Resolved: the domain only adds; tests, the 70-case probe with 0 holes, mutants M1, M8, M15 |
| C2 | Coverage | HIGH | rose | An unread head, or no head sha at a door, could read as no rise | Resolved: unread is a rise and no sha is never read; tests, mutants M6, M14, M17 |
| C3 | Coverage | MEDIUM | rose | Two functions of one name could hide a rise | Resolved: counts are summed by name; test row, mutant M7 |
| R1 | Risk | MEDIUM | spec How this fails 1 | A guard change with none of the words reads as no guard change | Kept as residual risk; owner paths still take security here |
| B1 | Budget | MEDIUM | brief | Runtime +28 against the brief's +20 | Stated in the PR with its reason; the constitution's 3,600 holds at 3,424 |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T003, T005 | test_plan_add_defaults_to_smart_and_records_the_domain_and_doubt; test_the_lead_file_carries_domain_and_doubt_and_defaults_to_smart |
| FR-002 | T003, T006 | the acceptance tests, the complexity and guard rows, probe.txt |
| FR-003 | T003, T006 | test_spec_artifacts_are_owed_only_by_a_complex_item_and_hold_its_merge |
| FR-004 | T003, T007 | test_the_create_door_reads_the_complexity_at_the_branch_head; route_diff.txt |
| FR-005 | T003, T012 | test_acceptance_4_a_full_item_keeps_its_gates; route_diff.txt standard and full hosts |
