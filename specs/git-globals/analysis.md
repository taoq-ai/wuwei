# Specification analysis: git-globals

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise 1 | `--super-prefix` is listed as valued, but git 2.43 removed it | Resolved in Clarifications: read as unknown, refused before a push |
| A2 | Ambiguity | LOW | item promise 2 | Whether an unknown option refuses without push | Resolved: only with a later word push, as the promise says |
| S1 | Scope | MEDIUM | spec, addition to the promise | A steering -c or --config-env is refused whatever the subcommand | Kept: within the item's aim, the brief asked for the alias form; named in the PR |
| C1 | Coverage | MEDIUM | spec How this fails 3 | Config written before the call and GIT_CONFIG_* stay holes | Accepted: listed in SECURITY.md; outside the promise |
| B1 | Breaking | MEDIUM | spec Breaking | Commands that passed on main are refused | Declared with migration notes, `!` and a BREAKING CHANGE line |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T007 | test_a_push_to_main_after_any_git_global_option_meets_the_push_door |
| FR-002 | T007 | test_an_unknown_git_option_before_a_push_is_refused_naming_it |
| FR-003 | T007 | test_a_command_line_alias_or_push_routing_config_is_refused |
| FR-004 | T009 | the records git clean tests and corpus rows |
| FR-005 | T011 | test_every_route_reads_as_recorded |
| FR-006 | T008 | test_setup runtime budget; wc -l 2,996 |
| FR-007 | T013 | test_the_git_option_loop_stays_linear_at_125_kb |
