# Specification analysis: 1230-own-diff-delta

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against item 1230's
promise and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | item acceptance 3 | "declared generated" names no place, and the constitution caps config at six keys | Resolved in Clarifications: a dated `Generated (<repo>, <date>):` standards line, no config key |
| A2 | Ambiguity | MEDIUM | item promise | "the PR's diff against its base at the gated head" can be read from the old or the new base | Resolved: one base sha for both reads; three-dot compares put each head on its own merge base |
| C1 | Coverage | HIGH | design option | Counting a moved file by its own patches alone would let a PR hunk moved elsewhere in the file carry (12 moved lines read as 0 changed lines) | Resolved: a moved file counts its head-to-head lines; test "moves 12 PR lines", mutant M8 |
| C2 | Coverage | HIGH | design option | Measuring only files in the head-to-head compare would miss a merge that reverts main's change in a file the PR never touched (absent from that compare) | Resolved: a moved file missing there counts its own diff; test row, mutant M9, probe evil-revert class |
| C3 | Coverage | MEDIUM | GitHub compare | The compare lists at most 300 files, so a moved file past the cap is unseen | Resolved: an own diff at 300 files falls back to the head-to-head compare; test, mutants M16 and M17 |
| C4 | Coverage | MEDIUM | GitHub compare | A binary or long file has no patch, and a cached compare from before this change has none | Resolved: a missing patch never matches, so the file moves; test, mutant M3 |
| C5 | Coverage | LOW | standards line | A backticked or comma-separated glob, the standards file's own style, matched nothing | Resolved: globs split on spaces, commas and backticks; test, mutant M18 |
| R1 | Risk | MEDIUM | spec How this fails 2 | A hunk moved between identical three-line contexts reads the same | Kept as residual risk; any other move is caught |
| R2 | Risk | LOW | spec How this fails 1 | A stale `base.sha` reads main's commits as the PR's | Fails safe to today's behaviour; base.sha read on four open PRs |
| B1 | Budget | LOW | constitution VI | Runtime +8 against an item budget of +8 | 3,381 against main's 3,373 |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T003, T007 | test_a_base_merge_that_leaves_the_prs_own_diff_unchanged_carries_the_passes; probe far, above, update-branch |
| FR-002 | T003, T007 | own-delta rows "moves 12 PR lines", "adds a risky change the head-to-head compare misses" |
| FR-003 | T003, T007 | "a risky file with no patch"; test_a_compare_at_githubs_300_file_cap_is_measured_head_to_head; test_a_base_merge_is_measured_head_to_head_when_the_base_sha_is_unknown |
| FR-004 | T003, T007 | test_a_base_merge_that_changes_only_declared_generated_files_carries_the_passes (8 rows) |
| FR-005 | T004, T008 | test_the_merge_door_reads_a_base_merge_on_the_prs_own_diff; test_the_create_door_reads_a_base_merge_on_the_branchs_own_diff; route_diff.txt |
| FR-006 | T011, T012 | probe fix classes read the same at both trees; route differential fix host 0 moved |
