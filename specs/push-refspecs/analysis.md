# Specification analysis: push-refspecs

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | item promise (2) | "unless the refspec's source names no default-branch ref" can be read at the source pattern or at the local refs | Resolved in Clarifications: a glob is refused on its destination alone; local refs can be written in the same command. Over-refusal counted by the probe |
| A2 | Ambiguity | LOW | item promise (2) | `--branches` in git 2.43 | git 2.43 lists it as an alias of `--all` (`git push -h`); refused with its prefixes; unit tests (the first text said 2.43 had none, corrected in round 1) |
| C1 | Coverage | HIGH | probe at the first head | `git push origin @` from a clone on main moved main and passed | Resolved: `@` reads as `HEAD`; 2 real-git tests, a mutant; 0 holes at the head |
| C2 | Coverage | MEDIUM | acceptance 3 | `git push --tags origin` was refused from a clone on main | Resolved: `--tags` alone adds no current branch; 2 real-git tests, 2 mutants |
| C3 | Coverage | MEDIUM | git option parsing | `--mirr` and `--m` moved main and passed (any unique prefix) | Resolved: any prefix of `mirror` is a force push; 3 tests, a mutant |
| C4 | Coverage | MEDIUM | refspec split | `:/x:main` split at the first colon passed and moved main | Resolved: the last colon; a real-git test, a mutant |
| S1 | Scope | LOW | spec Assumptions | `X:HEAD` from a clone on main keeps main's over-refusal | Kept: main's rule, outside the promise |
| S2 | Scope | LOW | spec How this fails 2 | A local symbolic ref pushed with no colon reaches main | Round 1: resolved for a ref present when the guard reads (rev-parse); one written in the same command is listed in SECURITY.md |
| G1 | Coverage | HIGH | gates at b16d799, security | A word an option takes (`--repo --tags`, `-o --tags`) dropped the current-branch default; a regression from main | Resolved: options read with `_flags` and `PUSH_VALUED`; 13 real-git tests from main, 6 mutants; probe valued class 0 holes |
| G2 | Coverage | MEDIUM | gates at b16d799, security | A taken word read as a refspec (`origin -o ci.skip`, `--repo x origin`) suppressed the default, on main too | Resolved by G1's reader; spec How this fails 3 corrected |
| G3 | Coverage | HIGH | gates at b16d799, quality | A refspec after `--` that starts with a dash was dropped (`-- -x:main`) | Resolved: every word after the first `--` or `--end-of-options` is a refspec; 6 real-git tests, 2 mutants; probe end-of-options class 0 holes |
| G4 | Coverage | MEDIUM | gates at b16d799, security | `main-worktree/HEAD` and `worktrees/<id>/HEAD` take another worktree's HEAD | Resolved: a source alone adds its rev-parse name; 5 real-git tests, 4 mutants; probe resolve class 0 holes |
| G5 | Coverage | MEDIUM | round 1 probe | `--tags --no-tags origin` pushed main from main and passed at b16d799 | Resolved: the last of `--tags` and `--no-tags` wins; 2 real-git tests, 2 mutants |
| B1 | Budget | LOW | spec Assumptions | Runtime +5 against a budget of +4, ceiling 6 | One over the budget, inside the ceiling; the reason is in spec Assumptions |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T004 | test_a_refspec_that_moves_main_under_real_git_meets_the_push_door, test_a_refspec_that_cannot_reach_main_passes_the_push_door |
| FR-002 | T004, T008 | test_a_refspec_reaching_the_default_branch_by_git_rules_meets_the_push_door, test_a_push_from_main_reads_at_and_tags_as_git_does |
| FR-003 | T004 | test_a_refspec_refusal_keeps_the_push_door_text |
| FR-004 | T006, T011, T016 | routes differential: 0 of main's 257 move; 16 rows added, 11 move |
| FR-005 | T007, T010, T017 | probe at the head: 21,282 generated, 21,254 ran git push, 80 holes, all in the force class and the same at main (digit clusters, a separate item); 1,064 at main |
| FR-006 | T005, T015 | design.md, doors.md, SECURITY.md; test_the_vendored_plugin_matches_the_tree_it_was_copied_from |
| FR-007 | T014 | test_a_word_an_option_takes_is_no_refspec_or_option_of_the_push, test_a_refspec_git_resolves_to_main_meets_the_push_door |
| FR-008 | T014 | test_a_refspec_git_resolves_to_main_meets_the_push_door |
