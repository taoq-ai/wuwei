# Specification analysis: scratch-remotes

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise | "the session scratch folder" is not named in the hook payload | Resolved in Clarifications: below gettempdir() or /tmp, realpath on both |
| A2 | Ambiguity | MEDIUM | item Assumptions | The url read only from `remote.<name>.url` misses a pushurl to the code host | Resolved: the rule reads `git remote get-url --push --all`; a mutant reading the url alone fails the tests |
| A3 | Ambiguity | LOW | item Assumptions | A relative path's base | Resolved from real git: the top of the worktree |
| S1 | Scope | LOW | spec Clarifications | Force pushes and deletes to a scratch remote pass | Kept: the promise passes a push to scratch, and push-refspecs needs + refspecs there |
| S2 | Scope | LOW | spec Clarifications | An option before the remote word keeps the door (`git push -u ../r.git main`) | Kept: over-refusal only; `git push ../r.git -u main` passes |
| C1 | Coverage | MEDIUM | spec How this fails 2 | Config written before the call can rewrite a typed path (insteadOf, pushInsteadOf, vcs, receivepack) | Resolved: the rule reads that config and keeps the door; an exec path or receive hook stays, listed in SECURITY.md |
| C2 | Coverage | LOW | spec How this fails 3 | A concurrent process can plant a .git entry between the read and the push | Accepted: writes local refs only; listed in SECURITY.md |
| B1 | Budget | MEDIUM | spec Assumptions | Runtime +16 against a budget of +3 | Recorded with numbers: 2,992 leaves 8 lines under the cap for push-refspecs and gh-args (budgets 6 and 5); the config check (3 lines) is the cheapest to drop; #1134 proposes 3,400 |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T007, T010, T011, T012 | test_a_push_the_scratch_rule_cannot_read_as_local_meets_the_push_door, test_config_that_sends_a_scratch_push_elsewhere_keeps_the_push_door, test_a_push_to_a_git_directory_outside_the_temporary_folders_meets_the_push_door, test_a_push_from_a_worktree_to_its_own_repository_meets_the_push_door |
| FR-002 | T007 | test_a_push_to_a_scratch_bare_remote_passes_the_door_and_lands |
| FR-003 | T013 | routes differential, 0 moved; test_every_route_reads_as_recorded |
| FR-004 | T013 | the 4 scratch-remotes rows in routes.json |
| FR-005 | T014 | the generated probe: 10,260 generated, 9,720 ran the door program, 0 holes |
| FR-006 | T015 | SECURITY.md |
| FR-007 | T015 | test_the_vendored_plugin_matches_the_tree_it_was_copied_from |
