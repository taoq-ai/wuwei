# Specification analysis: push-refspecs

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | item promise (2) | "unless the refspec's source names no default-branch ref" can be read at the source pattern or at the local refs | Resolved in Clarifications: a glob is refused on its destination alone; local refs can be written in the same command. Over-refusal counted by the probe |
| A2 | Ambiguity | LOW | item promise (2) | `--branches` is not an option of git 2.43 | Resolved: refused with its prefixes as the promise asks; unit tests only |
| C1 | Coverage | HIGH | probe at the first head | `git push origin @` from a clone on main moved main and passed | Resolved: `@` reads as `HEAD`; 2 real-git tests, a mutant; 0 holes at the head |
| C2 | Coverage | MEDIUM | acceptance 3 | `git push --tags origin` was refused from a clone on main | Resolved: `--tags` alone adds no current branch; 2 real-git tests, 2 mutants |
| C3 | Coverage | MEDIUM | git option parsing | `--mirr` and `--m` moved main and passed (any unique prefix) | Resolved: any prefix of `mirror` is a force push; 3 tests, a mutant |
| C4 | Coverage | MEDIUM | refspec split | `:/x:main` split at the first colon passed and moved main | Resolved: the last colon; a real-git test, a mutant |
| S1 | Scope | LOW | spec Assumptions | `X:HEAD` from a clone on main keeps main's over-refusal | Kept: main's rule, outside the promise |
| S2 | Scope | LOW | spec How this fails 2 | A local symbolic ref pushed with no colon reaches main | Outside (refs written before the call); a candidate in the handoff |
| B1 | Budget | LOW | spec Assumptions | Runtime +1 against a budget of +4 | Within budget |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T004 | test_a_refspec_that_moves_main_under_real_git_meets_the_push_door, test_a_refspec_that_cannot_reach_main_passes_the_push_door |
| FR-002 | T004, T008 | test_a_refspec_reaching_the_default_branch_by_git_rules_meets_the_push_door, test_a_push_from_main_reads_at_and_tags_as_git_does |
| FR-003 | T004 | test_a_refspec_refusal_keeps_the_push_door_text |
| FR-004 | T006, T011 | routes differential: 0 of 257 move; 12 rows added, 8 move |
| FR-005 | T007, T010 | probe at the head: 6,398 generated, 6,370 ran git push, 0 holes; 502 at main |
| FR-006 | T005 | design.md, doors.md; test_the_vendored_plugin_matches_the_tree_it_was_copied_from |
