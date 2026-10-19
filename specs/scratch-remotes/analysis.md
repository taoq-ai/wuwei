# Specification analysis: scratch-remotes

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise | "the session scratch folder" is not named in the hook payload | Resolved in Clarifications: below gettempdir() or /tmp, realpath on both |
| A2 | Ambiguity | MEDIUM | item Assumptions | The url read only from `remote.<name>.url` misses a pushurl to the code host | Resolved: the rule reads `git remote get-url --push --all`; a mutant reading the url alone fails the tests |
| A3 | Ambiguity | LOW | item Assumptions | A relative path's base | Resolved from real git: the top of the work tree when the shell is inside it, else the shell's directory (fix round 1: the rule needs the shell inside) |
| S1 | Scope | LOW | spec Clarifications | Force pushes and deletes to a scratch remote pass | Kept: the promise passes a push to scratch, and push-refspecs needs + refspecs there |
| S2 | Scope | LOW | spec Clarifications | An option before the remote word keeps the door (`git push -u ../r.git main`) | Kept: over-refusal only; `git push ../r.git -u main` passes |
| C1 | Coverage | MEDIUM | spec How this fails 2 | Config written before the call can rewrite a typed path (insteadOf, pushInsteadOf, vcs, receivepack) | Resolved: the rule reads that config and keeps the door; an exec path or receive hook stays, listed in SECURITY.md |
| C2 | Coverage | LOW | spec How this fails 3 | A concurrent process can plant a .git entry between the read and the push | Accepted: writes local refs only; listed in SECURITY.md |
| B1 | Budget | MEDIUM | spec Assumptions | Runtime +18 against a budget of +3 | Recorded: 3,004 against main 2,986 under the 3,400 cap of #1134 |
| F1 | Coverage | CRITICAL | gates at 6a5d00d, spec Clarifications | A work tree outside the shell moved the guard's base for a relative remote | Resolved in fix round 1: `--is-inside-work-tree` must print true; 10 tests, a mutant, 0 probe holes |
| F2 | Coverage | HIGH | gates at 6a5d00d | A remote in global config was read as a path | Resolved: a `remote.<word>.` key in any scope refuses; 2 tests, a mutant |
| F3 | Coverage | MEDIUM | gates at 6a5d00d | `--exec` and `--receive-pack` run any program | Resolved: refused in every prefix git reads; 5 tests, a mutant |
| F4 | Consistency | MEDIUM | gates at 6a5d00d | `+` refspecs refused while force flags pass; design.md and doors.md silent on the exception | Resolved: `+` in the word class with 2 pass tests; one clause in each doc |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T007, T010, T011, T012, T020 | test_a_push_from_outside_its_work_tree_meets_the_push_door, test_a_remote_named_in_global_config_keeps_the_push_door, test_a_push_the_scratch_rule_cannot_read_as_local_meets_the_push_door, test_config_that_sends_a_scratch_push_elsewhere_keeps_the_push_door, test_a_push_to_a_git_directory_outside_the_temporary_folders_meets_the_push_door, test_a_push_from_a_worktree_to_its_own_repository_meets_the_push_door |
| FR-002 | T007 | test_a_push_to_a_scratch_bare_remote_passes_the_door_and_lands |
| FR-003 | T013 | routes differential, 0 moved; test_every_route_reads_as_recorded |
| FR-004 | T013 | the 4 scratch-remotes rows in routes.json |
| FR-005 | T014, T024 | the generated probe at the fix-round head: 42,768 generated, 40,824 ran the door program, 0 holes |
| FR-006 | T015 | SECURITY.md |
| FR-007 | T015 | test_the_vendored_plugin_matches_the_tree_it_was_copied_from |
