# Implementation Plan: one table per edge and the loop property test; no timing assertions; under 3000 tests

**Branch**: `b9-cleanup` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

Built after parts 23 and 24 on the same branch. Counts are at 71d3f06b
(`python -m pytest --collect-only -q`: 7668 tests, 2964 functions); re-measure after each phase.

## Summary

Make `tests/test_edges.py` the one home of each edge's decisions (eight tables), delete the
duplicates elsewhere, delete every duration assertion and move the hook latency measurement to
a script, keep the loop property test as the contract, and collapse parametrized tables into
table tests until the suite collects under 3000 with headroom; CI holds the limit.

## Technical Context

Tests and CI only, plus one script moved out of `tests/test_hooks.py`. No runtime code changes.
Expected count: about 6900 after part 23, about 6850 after part 24, about 6600 after the edge
consolidation, at most 2900 after the table collapse (collapsing every table would give about
2500).

## Constitution Check

- II, IV: guards keep table tests for exits 0, 1 and 2 (the edge tables carry all three);
  tests assert on exit codes, events and files.
- IV: this part changes tests only; each consolidated table is run red once by breaking its
  edge in a scratch copy (reverse the condition) to show the table still catches it.
- V: one table per edge instead of many files.
- Never loosen: every distinct row stays (spec Assumption 2).

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Edge rows in eight other files | duplicate coverage | the edge's table in `tests/test_edges.py` |
| Real-clock latency and duration assertions | (a) a flaky gate on CI speed, not on behaviour | `scripts/hook_latency.py` in the informational latency job |
| `timing` xdist group and its rerun step | (a) | nowhere |
| Parametrized cases as separate tests | count only | table tests with every row |

## Files to create (1)

- `scripts/hook_latency.py`: the measurement now in `tests/test_hooks.py` (`startup_floor`
  782, `assert_latency_budget` 798-823 without the asserts, the probe loops of
  `test_hook_latency` 825-846, `test_status_line_latency` 867-898 and
  `test_workspace_hook_latency` 1025-1052 minus the Stop path part 23 deleted); writes
  `latency.jsonl` rows as `WUWEI_LATENCY_OUT` does today and exits 0.

## Files to edit

### Edge tables (FR-001, FR-002)

`tests/test_edges.py` (223 cases, 46 functions) becomes:

| Table test | Rows from (71d3f06b) |
| --- | --- |
| `test_merge_edge` | `test_merge_refused` 12, `test_merge_allowed` 6, `test_grammar_merge_refused` 20, `test_wrapped_merge_refused` 17, `test_piped_xargs_merge_refused`; `test_merge.py:507` (9), `:521`; `test_profiles.py:184` merge rows; `test_parser_warns.py` `test_five_shapes` merge rows, `test_continued_admin_merge_is_named`; `test_scope_first.py` merge shapes (outside-workspace column); `test_seat_command_forms.py` `test_issue_330_effectful_forms` |
| `test_approve_edge` | `test_approve_refused`, `test_approve_allowed`, `test_approval_forms_refused`, `test_readable_comment_review_body_passes`; `test_profiles.py` approval rows; `test_guard_mutation.py:18` approve probe |
| `test_admin_edge` | `test_admin_refused`, `test_admin_allowed` (admin merge and branch protection); `test_profiles.py` admin rows |
| `test_force_push_edge` | `test_force_push_refused` 8, `test_force_push_allowed` 7, `test_wrapped_force_push_refused` 17, `test_force_push_names_the_item_branch`; `test_seat_command_forms.py` force-push rows; `test_parser_warns.py` `test_quoted_name_is_judged_as_the_plain_command`; `test_scope_first.py` force-push shapes; the doctor probe row part 23 moved here |
| `test_default_branch_push_edge` | `test_default_branch_push_refused` 6, `test_default_branch_push_allowed` 4, `test_hook_skipping_push_refused` 4, `test_loop_default_branch_push_refused` |
| `test_deploy_edge` | `test_deploy_refused` 23, `test_deploy_allowed` 9, `test_unmarked_workflow_is_allowed`, `test_deploy_runs_on_the_owners_yes`, `test_deploy_unreadable_config_fails_closed`, `test_custom_rules_require_literal_executable`; `test_profiles.py` deploy rows (terraform, release, kubectl); `test_card_confirms.py` deploy rows |
| `test_outward_send_edge` | `test_outward_send_refused_and_allowed`, `test_enforce_off_outward_send_blocks`; `test_outward.py` cases that call `edges.check_send` (`test_recorded_tools` 203, `test_routing_and_bypass_table` 31, `test_real_mcp_write_names` 26, `test_not_only_the_owner_is_not_local` 15, `test_local_tools_pass` 14, `test_scope_before_payload_and_policy` 8 and the rest of its about 37 `check_send` functions); `test_canary.py` edge cases |
| `test_pr_create_edge` | `test_pr_raise_refused` 4, `test_pr_raise_allowed` 2, `test_pr_raise_allowed_once_the_item_links_a_pr` |

Each row carries the `guards.enforce` column (from `test_enforce_off` 14 and
`tests/test_enforce.py` `TABLE` edge rows) and the inside or outside workspace column (from
`tests/test_scope_first.py` `GUARD_TABLES`). Kept beside the tables: `test_segments`,
`test_unparsed_call_is_logged_once_and_runs`, `test_unsplittable_calls_raise`,
`test_ceilings_are_not_read`. The 12 init and settings tests in this file move to
`tests/test_config_transition.py` (one subject per file).

Then delete from the source files the moved functions; delete `tests/test_profiles.py`,
`tests/test_seat_command_forms.py` and `tests/test_scope_first.py` when nothing else is left in
them; `tests/test_enforce.py` keeps one posture table without edge rows;
`tests/test_outward.py` keeps the `outward.allow` loading, the owner's-own-surface rule and the
prose lint (logged) as table tests.

### Loop contract (FR-003)

- `tests/test_loop.py`: docstring (line 12) states the contract and drops the xfail note;
  `materialise` after part 23 writes only the log; if `--durations` shows the setup over a
  second, write each world's records in one `state._write_state` call (spec Assumption 3).

### Timing (FR-004 to FR-006)

- `tests/test_hooks.py`: delete `startup_floor`, `assert_latency_budget`, `test_hook_latency`,
  `test_status_line_latency`, `test_workspace_hook_latency`; move
  `test_latency_budget_decision` (731-759) and `test_latency_row_is_written_before_the_budget`
  (763) to `tests/test_latency_report.py` against the script's decision function with fake
  figures. Keep the #346 import and GC proxies (238, 322, 532, 1076).
- `tests/test_integrity.py:298-310`: delete `test_cached_check_latency`; if no test shows the
  second check reads the cache, add one that counts the reads (no clock).
- `tests/test_traces.py:33-53`: drop the CPU and SIGPROF deadline; keep what it asserts on the
  record. `:867` `test_slow_record_gives_up_on_a_held_lock`: drop the elapsed assert, keep
  "gave up and recorded why" with a short configured lock timeout.
- `tests/test_e2e_day.py:14-113`, `tests/test_path_day.py:129-171,219-299`: drop the elapsed
  checks.
- Status-line tests part 23 moved into `tests/test_signal_status.py`: drop any elapsed check.
- `tests/test_dev_cycle.py:16-28,100,31-44`: delete `TIMING` and
  `test_exactly_the_clock_tests_share_the_timing_group`; the workflow test asserts the parallel
  run and the count step instead of the timing rerun.
- `.github/workflows/tests.yml:27-40`: drop `--dist loadgroup` if no group is left and the
  timing rerun step; add a step `python -m pytest --collect-only -q | tail -1` that fails at
  3000 or more; `:65-101` latency job runs `python scripts/hook_latency.py` then
  `scripts/latency_report.py`.
- `pyproject.toml`: drop the `xdist_group` marker line.

### Table collapse (FR-007)

Collapse in this order (surplus = cases minus functions at 71d3f06b), re-measuring after each
file, stop when the count is at most 2900:

| File | Cases | Functions | Note |
| --- | --- | --- | --- |
| `tests/test_protect_state.py` | 663 | 67 | records guard tables (`test_f9_dynamic_writes_are_logged` 74, `test_shell_state_guard` 47, `test_f8_protection_follows_target` 40, ...) |
| `tests/test_shell.py` | 425 | 51 | parser tables |
| `tests/test_hooks.py` | 347 | 63 | after the timing deletions |
| `tests/test_verdict.py` | 283 | 63 | verdict lint tables |
| `tests/test_code_host.py` | 223 | 54 | adapter mapping tables |
| `tests/test_merge.py` | 263 | 113 | policy tables |
| `tests/test_traces.py` | 175 | 52 | |
| `tests/test_pr_ownership.py` | 110 | 26 | |
| `tests/test_adapters.py` | 106 | 22 | |
| `tests/test_dispatch.py`, `tests/test_workspace.py`, `tests/test_vcs.py`, `tests/test_agent_launch.py`, `tests/test_config_writer.py`, `tests/test_ziran.py`, `tests/test_brief.py`, `tests/test_parser_warns.py` | | | as needed |

Rule: a `@pytest.mark.parametrize` over rows of one function's inputs and expected outputs
becomes `ROWS = (...)` and one test computing `bad = [(row, got) for row in ROWS if got !=
expected]` and asserting `not bad`. A parametrize over fixtures or worlds that change setup
(tmp workspaces per row) collapses the same way with the setup inside the loop. Do not collapse
`tests/test_loop.py`.

## Files to delete (up to 3)

`tests/test_profiles.py`, `tests/test_seat_command_forms.py`, `tests/test_scope_first.py`, each
only when its remaining content is the moved edge rows.
