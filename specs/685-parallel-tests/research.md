# Research: #685 parallel tests

## Profile on main (before)

Run 2026-10-10 on `main` f497c9e, pytest 9.1.1, Python 3.12, 10-core machine shared with other
pipeline runs (load average 40 to 70 during the run). The suite ran as 8 file shards in 8
processes (`--durations=0 --durations-min=0.5`), because a serial run on the loaded host was
on course for over an hour. Absolute seconds are about 2.3x a quiet run (the owner's 19
minutes serial); use the ranking.

- 10,832 tests: 10,822 passed, 10 skipped, in every shard (no cross-file coupling).
- 8 shards: 403 s wall, about 2,660 s summed.
- Rows of 0.5 s or more: 676, 1,852 s (70% of the time). Fixture setup in those rows: 278 s.

Slowest files (sum of rows of 0.5 s or more):

| s | file |
|---|---|
| 281 | tests/test_setup.py (116 of it fixture setup) |
| 178 | tests/test_invariants.py (15 `test_broken_rule_is_caught` params, about 10 s each) |
| 170 | tests/test_state_allowlist.py (the four reader inventory tests) |
| 170 | tests/test_workspace.py (47 `cli()` interpreter launches) |
| 167 | tests/test_hooks.py (latency probes, `seeded_workspace`) |
| 92 | tests/test_canary.py (88 of it fixture setup, `init.run` per test) |
| 89 | tests/test_path_day.py |
| 64 | tests/test_e2e_day.py |
| 50 | tests/test_worktree_command.py |
| 47 | tests/test_headless_e2e.py |
| 43 | tests/test_tone.py (two budget tests) |
| 43 | tests/test_cli.py |
| 43 | tests/test_scope_first.py (one test) |

Slowest single tests (they bound the parallel wall-clock, none above total/4):
`test_state_allowlist.py::test_reader_inventory_cannot_be_written_generically` 58 s,
`test_reader_inventory_detects_widened_allowlist[event]` 48 s,
`test_scope_first.py::test_every_table_row_outside_is_clean` 41 s,
`test_headless_e2e.py::test_scratch_build_and_observer_preserve_hook_results` 37 s.

In-process checks of the shared helpers (quiet moment, CPU time):
`reader_inventory()` 0.87 s (1,882 keys, 560 kinds), `test_tone.classes()` 1.33 s,
`test_reasons.all_reasons()` 0.95 s (1,378 reasons), `over_budget` 0.07 s. Under pytest on
the loaded host the two tone budget tests took 11.7 s and 15.5 s, nearly all of it
`ast.parse` and `ast.walk` over the CLI sources.

`init.run` (the canary fixture) on a fresh directory: 1.2 to 1.5 s wall, 0.25 s CPU, five
`git` launches. The resulting tree (74 files) contains no copy of its own absolute path, so a
copied tree is the same workspace.

### What is not cut, and why

- `test_state_allowlist.py` reader inventory tests: the cost is about 5,000 in-process CLI
  calls (`state set` and `event` per inventoried key and kind); each call is the evidence.
  Only the source scan is cached.
- `test_invariants.py` mutation tests: #626 is changing `walk` now; touching it here would
  conflict. Revisit after #626 merges (early exit at the first failure would save about 20%).
- `test_hooks.py` latency probes: design 10.6 says the benchmark p95 is measured and
  printed on every run, so they keep their runs.
- `test_path_day.py`, `test_e2e_day.py`, `test_headless_e2e.py`, `test_scope_first.py`: end
  to end by design.

## Timing tests

Every test that asserts a clock or prints a latency figure. These, and only these, carry
`pytest.mark.xdist_group('timing')`.

| test | clock |
|---|---|
| tests/test_invariants.py::test_invariants_hold | `process_time` walk < 1.0 s |
| tests/test_traces.py::test_large_arguments_record_under_50ms_cpu | `process_time` < 0.05 s |
| tests/test_integrity.py::test_cached_check_latency | `perf_counter` p95 < 50 ms |
| tests/test_heartbeat.py::test_stuck_state_lock_fails_the_state_probe | `monotonic` < 3 s |
| tests/test_adapters.py::test_watch_probe_runs_calls_together_and_times_out | `monotonic` < 3 s |
| tests/test_e2e_day.py::test_scripted_day | `monotonic` < 20 s |
| tests/test_path_day.py::test_the_day_closes_walking_only_next | `monotonic` < 60 s |
| tests/test_path_day.py::test_posture_day | `monotonic` < 60 s |
| tests/test_hooks.py::test_hook_latency | hook p95, `assert_latency_budget` |
| tests/test_hooks.py::test_status_line_latency | status line p95 |
| tests/test_hooks.py::test_workspace_hook_latency | hook p95 in a seeded workspace |
| tests/test_hooks.py::test_heartbeat_latency | heartbeat tick p95 |

Not timing: `test_hooks.py::test_latency_budget_decision` and
`test_latency_row_is_written_before_the_budget` replace `startup_floor` and test the decision;
`test_heartbeat.py::test_launcher_probe_outcomes` feeds fixed milliseconds.

Quiet serial cost of the twelve: about 140 s (latency probes about 70 s, the two days about
65 s). Running them alone after every parallel run would add that to the job, so they run in
the group and only the flagged ones rerun.

## Rerun guard: pytest semantics, verified

**Builder correction (T008).** The guard below does not work under xdist. With
`-n 2 --dist loadgroup` (pytest-xdist 3.8.0) a failed grouped test is cached as
`test_x.py::test_t@timing`. A later plain `--lf` run collects `test_x.py::test_t`, matches
nothing, and falls back to every test, so `--lf -m "not xdist_group" --collect-only` exited 0
and the guard failed the job on every timing-only failure (also with `-n 1 --dist loadgroup`).
The step now reads `.pytest_cache/v/cache/lastfailed` directly (plan.md 2). Scratch run, one
parametrized timing test and one plain test:

| parallel run failed | rerun step |
|---|---|
| timing only, passes alone | reruns the 2 ids, exit 0 |
| plain only | not rerun, exit 1 |
| plain and timing | not rerun, exit 1 |
| timing only, fails alone too | reruns, exit 1 |

The original analysis, kept for the record:

pytest 9.1.1, a scratch project with one timing test and one plain test:

| last-failed cache holds | `pytest --lf -m "not xdist_group" --collect-only` |
|---|---|
| only timing tests | exit 5 (all deselected) |
| a plain test (with or without timing tests) | exit 0 (collected) |
| nothing (empty cache) | exit 0 (`--lf` falls back to every test) |

`pytest --lf -m xdist_group` then reruns exactly the failed timing tests. So the guard passes
only on exit 5, which is fail closed for a crash that recorded nothing. The builder confirms
that a `-n auto` run writes the same cache (xdist reports through the controller).

## Choices

- **pytest-xdist** over a hand-rolled shard runner: the issue names it, it is dev-only, and it
  balances per test, not per file.
- **`--dist loadgroup`**: the only xdist mode that honours `xdist_group`; it distributes the
  rest like `load`.
- **Runner**: `ubuntu-latest` for a public repository has 4 vCPUs; `-n auto` uses 4 workers.
  19 minutes of serial work over 4 workers is about 5 minutes before the cuts.
- **Changed tests**: the product already runs only changed test files at pace `fast`
  (`cli/wuwei/fast_checks.py:35`, `commands`), but that needs a workspace, a plan and the
  checks port; a seat in this repository needs a plain command. The script reuses nothing
  from it and follows imports, which `fast_checks` does not.

## Measurements to record (builder)

| run | before | after |
|---|---|---|
| local serial `python -m pytest -q` | | |
| local `python -m pytest -q -n auto --dist loadgroup` | | |
| `python3 scripts/changed_tests.py` on this branch's diff | n/a | |

Record the load average next to each figure.

Builder, 2026-10-10, same shared host (load average 28 to 44). The full serial suite was not
run: the owner wants CI as the gate. Figures:

| run | before | after |
|---|---|---|
| the six cut files (`test_setup`, `test_canary`, `test_workspace`, `test_reasons`, `test_tone`, `test_state_allowlist`), `-n 8` | 158.8 s (load 35 to 40) | 39.2 s (load 27 to 33) |
| `test_workspace.py`, `-n 8` | | 17.1 s, 160 passed |
| `python3 scripts/changed_tests.py -n 8 --dist loadgroup` on this branch | n/a | selects `tests` (pyproject changed), full suite 317 s wall at load 40 to 44 |

Canary copy check (T015): a copied initialized tree and a fresh init have the same 90 paths
(outside `.wuwei/.git/objects`) and the same modes; the contents differ only in the random
material (`security.json`, `credentials/backup.env`, the generated agents, charters and
skills that embed the canary) and the git index; the copy is byte-identical to its source and
no file holds the tree's own path. No `test_workspace.py` test needed `cli_process` besides
`test_init_layout`.
