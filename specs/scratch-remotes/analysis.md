# Specification analysis: scratch-remotes

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise | "the session scratch folder" has no source in the payload or environment | Resolved in Clarifications: the temp folder by realpath, with checkouts and workspaces kept out |
| A2 | Ambiguity | LOW | item promise | whether `url.*` config refuses outright | Resolved: only a rewrite whose prefix matches a url read; this environment sets an unrelated one |
| S1 | Scope | LOW | spec Assumptions | doors.md gets one parenthesis outside the item's file list | Kept: the doors page would otherwise state a refusal that no longer holds; named in the PR |
| B1 | Budget | MEDIUM | spec Size | runtime +11 against a budget of 3 | Named in the PR; 13 lines stay for push-refspecs and gh-args, estimated at about 6 |
| C1 | Coverage | MEDIUM | spec How this fails 2 | a pre-push hook or a path swapped between the hook and git is not seen | Accepted: listed in SECURITY.md, the same class as config set before the call |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T006, T007 | test_a_plain_push_to_a_scratch_remote_passes_the_push_door, test_a_named_remote_passes_only_when_every_url_and_pushurl_is_scratch, test_a_rewrite_that_matches_no_scratch_url_leaves_the_scratch_push_passing |
| FR-002 | T007, T009 | test_a_push_to_anything_but_a_plain_scratch_remote_keeps_the_push_door, test_url_rewriting_or_a_remote_command_in_config_keeps_a_scratch_push_at_the_door, test_a_scratch_remote_outside_the_temp_folder_keeps_the_push_door; probe 0 holes |
| FR-003 | T007 | test_a_scratch_push_keeps_the_force_door_and_an_unreadable_config_keeps_the_push_door |
| FR-004 | T011 | test_every_route_reads_as_recorded |
| FR-005 | T012 | test_the_vendored_plugin_matches_the_tree_it_was_copied_from |
| FR-006 | T013 | test_the_scratch_check_stays_linear_at_125_and_500_kb, test_the_scratch_shape_is_not_reread_for_each_segment |
| FR-007 | T006 | test_the_runtime_holds_its_size_budget; wc -l 2,987 |
