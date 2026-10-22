# Specification analysis: gates-at-push

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against item 1221's
promise and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | acceptance 2 | "the team row names the owed gates" could mean a list of gate names | Resolved in Clarifications: the duty line names the owed gates as a duty; the item rows below name the gates |
| A2 | Ambiguity | MEDIUM | acceptance 4 | "a failing check" names no states | Resolved: the CI gaps of `evidence.gaps`, the merge door's reading |
| A3 | Ambiguity | MEDIUM | promise | Whether running CI holds the ready door | Resolved: yes, per the planner's reading of the issue ("require green CI at the head"); the door names `CI running` |
| C1 | Coverage | HIGH | ready door | A red draft could stay shut even after the owner accepts the gap, unlike the merge door | Resolved: `evidence.gaps` drops the exact gap the owner accepted at that PR and head; tests |
| C3 | Coverage | HIGH | ready door | A failing review-triggered status (review evidence, not CI) would hold the reviewer request that clears it (arch FIX at ceb9c45) | Resolved: the door reads `evidence.gaps`, which passes the review contexts to `ci_gaps`; test rows and mutant 5 |
| C2 | Coverage | MEDIUM | acceptance 3 | No runtime change makes it hold, so a test must pin it | Resolved: a SubagentStop attestation while CI runs, then green CI: no gap and the merge door passes |
| R1 | Risk | MEDIUM | spec How this fails 2 | A draft that is not green names its CI gaps and not its missing gates | Kept: CI is fixed or finishes first, and the gates read that head |
| R2 | Risk | LOW | route corpus | The PR standard note text moves on every draft create route | Listed as its own rows in route_diff.txt; no verdict moves there |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T003, T007 | test_gates_start_at_push_in_parallel_with_ci_and_green_ci_still_holds_ready; test_the_pr_standard_note_opens_a_draft_and_leaves_the_reviewer_to_the_shepherd |
| FR-002 | T002, T005 | test_owed_gates_on_a_head_whose_ci_runs_or_has_not_started_owe_a_gate_seat_and_a_red_head_none; test_owed_gates_on_a_head_missing_a_required_check_owe_a_gate_seat |
| FR-003 | T002, T006 | test_a_draft_whose_gates_passed_stays_draft_until_ci_is_green_and_names_what_holds_it; test_an_accepted_running_gap_opens_the_ready_door_at_its_head; test_a_required_check_not_run_or_unreadable_evidence_holds_the_ready_door; test_a_review_triggered_status_is_review_evidence_and_never_holds_the_ready_door; test_a_ready_pr_with_a_red_check_still_takes_a_reviewer_request; test_a_merge_with_its_gates_passed_and_a_failing_check_is_refused_naming_it; route_diff.txt |
| FR-004 | T002 | test_a_verdict_attested_while_ci_ran_counts_once_ci_turns_green_at_that_head |
| FR-005 | T008 | runtime 3,585 of 3,800 (+4) |
