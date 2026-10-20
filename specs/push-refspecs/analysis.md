# Specification analysis: push-refspecs

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | item promise (2) | "unless the refspec's source names no default-branch ref" can be read at the source pattern or at the local refs | Resolved in Clarifications: a glob is refused on its destination alone; local refs can be written in the same command. Over-refusal counted by the probe |
| A2 | Ambiguity | LOW | item promise (2) | `--branches` in git 2.43 | git 2.43 lists it as an alias of `--all` (`git push -h`); refused with its prefixes; unit tests (the first text said 2.43 had none, corrected in round 1) |
| C1 | Coverage | HIGH | probe at the first head | `git push origin @` from a clone on main moved main and passed | Resolved: `@` reads as `HEAD` (round 1: a source alone through rev-parse; git rejects `@` as a destination); 2 real-git tests, a mutant; 0 holes at the head |
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
| G6 | Coverage | HIGH | gates at 9cb834a, quality and security | One git call per colon-less refspec: 15,000 tags pushed by name took the guard 77 s, past the hook's timeout, which lets the tool run | Resolved: the refs are read once per push (`_sources`) and the current branch once; a timed test holds 15,000 words under 1 s (0.28 s measured, 74 s at 9cb834a; main's 15,000 `:` took 61 s, now 0.11 s) |
| G7 | Coverage | MEDIUM | gates at 9cb834a, quality and security | `--exec`, `--receive-pack` and `--recurse-submodules` in `PUSH_VALUED` had no test; each mutant survived | Resolved: 7 real-git rows from main in VALUES_FROM_MAIN; each mutant killed |
| G8 | Coverage | LOW | gates at 9cb834a, security | `git push origin origin` moved main through `refs/heads/origin` (a symbolic ref to main) while rev-parse called it ambiguous | Resolved: every candidate of git's ref rules counts; a real-git test, a mutant per rule |
| G9 | Coverage | LOW | gates at 9cb834a, security | A later `--end-of-options` read as an end marker, where git reads a refspec | Resolved: `_flags` ends at the first marker only; 2 real-git tests, 2 mutants |
| G10 | Coverage | LOW | round 2 design | Root refs (`ORIG_HEAD`, a one-level file) and a worktree whose id is not its folder's name | Resolved: the root files of each git directory are read; 5 real-git tests and a FIFO test |
| G11 | Coverage | MEDIUM | gates at aa63d3b, security | The root ref file reader missed root refs git resolves to main: `ref:` with no space, a tab or 300 spaces, a symlink, a nested name, another worktree's per-worktree refs, and a lowercase name read from w's folder over the common one (136 holes in 200 generated commands) | Resolved: git resolves each colon-less word in one batched rev-parse and the reader is removed; 18 real-git rows, the probe's rootfile and stopper classes, mutants of each batch rule |
| G12 | Coverage | MEDIUM | gates at aa63d3b, quality | The 1 s wall-clock bound failed on a correct guard under load (5 of 36 runs) | Resolved: a call-count test (one word and 15,000 make the same git calls), with no clock |
| G13 | Coverage | LOW | gates at aa63d3b, security | Guard time grew with the files in the git directory (100,000 root files: 7.3 s); a FIFO swapped over a root file between `is_file` and `open` hung the guard; `_git` turned a timeout into `''` | Resolved by construction: the guard opens no file in the git directory, and both ref reads refuse on a timeout or a failed exec (2 tests) |
| G14 | Coverage | LOW | gates at aa63d3b, quality | Mutant M6 (dropping the `ref: ` check) survived | Resolved by construction: the check is deleted with the reader |
| B1 | Budget | LOW | spec Assumptions | Runtime +21 against a budget of +4, ceiling 6 (round 2) | Round 3: +18 against main 17ff289 (3,340 against 3,322), under the PR's earlier +21 and the 3,400 cap |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T004 | test_a_refspec_that_moves_main_under_real_git_meets_the_push_door, test_a_refspec_that_cannot_reach_main_passes_the_push_door |
| FR-002 | T004, T008 | test_a_refspec_reaching_the_default_branch_by_git_rules_meets_the_push_door, test_a_push_from_main_reads_at_and_tags_as_git_does |
| FR-003 | T004 | test_a_refspec_refusal_keeps_the_push_door_text |
| FR-004 | T006, T011, T016 | routes differential: 0 of main's 257 move; 16 rows added, 11 move |
| FR-005 | T007, T010, T017, T025 | probe at the head (round 3): 22,698 generated, 22,670 ran git push, 80 holes, all in the force class and the same at main (digit clusters, a separate item); 1,420 at main; 0 regressions |
| FR-006 | T005, T015 | design.md, doors.md, SECURITY.md; test_the_vendored_plugin_matches_the_tree_it_was_copied_from |
| FR-007 | T014 | test_a_word_an_option_takes_is_no_refspec_or_option_of_the_push, test_a_refspec_git_resolves_to_main_meets_the_push_door |
| FR-008 | T014, T020, T022 | test_a_refspec_git_resolves_to_main_meets_the_push_door, test_a_source_alone_git_sends_elsewhere_passes_the_push_door; probe rootfile and stopper classes |
| FR-009 | T019, T022 | test_a_push_of_15000_refspecs_makes_the_git_calls_a_push_of_one_makes, test_a_push_whose_refs_git_cannot_read_in_time_is_refused, test_a_fifo_in_the_git_directory_does_not_hold_the_push_door |
