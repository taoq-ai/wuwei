# Feature Specification: Hook latency budget per hardware class and the CI latency job

**Feature Branch**: `231-latency-budget-docs`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #231, docs(perf). Design sections 2 (language decision) and 10.6 (latency);
the issue cites 9.1, but the hook budget lives in 10.6. Related: #211, #223.

## Root cause (reproduced read-only in this worktree)

The `latency` job (`.github/workflows/tests.yml:49-62`, `continue-on-error: true`,
`WUWEI_BENCH: "1"`, `ubuntu-latest`) runs `python -m pytest -q tests/test_hooks.py -k latency`.
Every benchmark routes through one helper, `assert_latency_budget`
(`tests/test_hooks.py:430-445`), which prints one line per path and, under `WUWEI_BENCH=1`,
asserts `cpu_ms < 50` (`tests/test_hooks.py:441`) or, for the in-workspace paths,
`wall_ms < 100` (`wall_budget=100`, `tests/test_hooks.py:665-666`).

Two gaps make a red job unreadable:

1. The report line (`tests/test_hooks.py:433-434`) prints the hook's CPU and wall p95, load
   and CPU count, but nothing about the interpreter start, which is most of the figure. On
   a 2-CPU runner the start alone is about twice the developer-hardware start, so every
   line reads as a regression.
2. No document says what the 50 ms figure applies to. Design 10.6 states it without a
   hardware class; `docs/site/` never mentions the budget or the job, and the job comment
   calls the runner "quiet".

Measured here (Apple M-series, 10 CPUs, load about 5, `WUWEI_BENCH=1`, main at 45775cb):

| Path | CPU p95 | Wall p95 | Budget asserted |
|---|---|---|---|
| PreToolUse | 41.8 ms | 47.5 ms | 50 ms CPU |
| PostToolUse | 39.4 ms | 44.3 ms | 50 ms CPU |
| status --line | 45.6 to 51.6 ms | 50.8 to 64.3 ms | 50 ms CPU |
| Stop in a workspace | 38.6 ms | 43.7 ms | 100 ms wall |
| SubagentStop in a workspace | 41.1 to 41.8 ms | 47.1 to 48.3 ms | 100 ms wall |
| SessionStart in a workspace | 97.1 to 110.4 ms | 104.7 to 125.2 ms | 100 ms wall |
| commit in a workspace | 112.7 to 114.5 ms | 82.5 to 83.4 ms | 100 ms wall |
| push in a workspace | 215.4 to 226.0 ms | 114.7 to 186.8 ms | 100 ms wall |

`<interpreter> -I -c pass` p95 over 60 runs on the same host: CPU 10.7 ms, wall 12.1 ms.

Observation, out of scope: on this host SessionStart and push in a workspace also exceed
their 100 ms wall budget, and commit and push CPU includes their git children. This issue
does not change budgets or hooks; the docs therefore claim 40 to 50 ms on developer hardware
only for the paths measured there (PreToolUse, PostToolUse, status --line).

## User Scenarios & Testing

### User Story 1 - Operator reads the budget and the red job (Priority: P1)

An operator who sees the `latency` job red finds, in the operator reference, what the 50 ms
figure applies to, what the runner figures are, and that the job is a trend line that never
blocks a merge.

**Independent Test**: `tests/test_docs.py` checks the reference page for the budget
statement, the hardware classes, the job's purpose and the exact job command, and checks
the workflow still runs that command with `continue-on-error`.

**Acceptance Scenarios**:

1. Given the docs, when an operator opens the operator reference, then a "Hook latency
   budget" section states "50 ms CPU p95 on developer hardware (M-series class); about 2x on
   2-CPU CI runners", the 100 ms wall p95 budget for the in-workspace paths, the runner
   figures from the three `main` runs of 2026-09-30, and the interpreter start floor.
2. Given the docs, then the section says the `latency` job is informational
   (`continue-on-error`), "a trend line, not a gate", names its command, and explains how to
   read a red line against the startup floor.
3. Given the docs index, then the operator reference entry names the latency budget.

### User Story 2 - Report line carries the startup floor (Priority: P1)

Anyone reading benchmark output sees the interpreter start next to each hook figure.

**Independent Test**: the budget decision table in `tests/test_hooks.py` replaces the floor
measurement with fixed values and asserts the report (skip reason and assertion message)
contains them.

**Acceptance Scenarios**:

1. Given `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency`, then each
   report line includes `python3 -I startup floor CPU <ms> ms, wall <ms> ms`, measured as
   the p95 of `<test interpreter> -I -c pass` over the same number of runs as the hook
   figure.
2. Given no `WUWEI_BENCH`, then the benchmarks still print and skip, and the skip reason
   includes the floor.
3. Given any setting, then the budget decision (50 ms CPU, or the wall budget when given)
   is unchanged and the floor is never subtracted or asserted.

### Edge Cases

- The floor is measured with `sys.executable`, the same binary the hooks run through the
  `python3` symlink in `subprocess_plugin` (`tests/test_hooks.py:29`); no literal interpreter
  path.
- The floor is measured once per run count per test session (60 under `WUWEI_BENCH=1`; 60
  and 20 otherwise), so the suite grows by at most 80 interpreter starts.
- The decision table must not spawn processes: it replaces the floor helper.

## Requirements

- **FR-001**: `assert_latency_budget` includes the startup floor (CPU and wall p95 of
  `sys.executable -I -c pass` over `runs` runs) in its report line, between the hook figure
  and the load.
- **FR-002**: The budget constant (50 ms CPU), the wall budgets, the `WUWEI_BENCH` rule, and
  the `latency` job (trigger, `continue-on-error`, command) do not change.
- **FR-003**: `docs/site/reference.md` has a "Hook latency budget" section covering
  scenarios 1.1 and 1.2; `docs/site/index.md` names it in the operator reference entry.
- **FR-004**: `tests/test_docs.py` fails if the section's key statements are removed or the
  documented job command stops matching the workflow.

## Success Criteria

- **SC-001**: A red `latency` job can be read from one report line: hook p95 next to the
  interpreter floor.
- **SC-002**: The operator reference answers "what does 50 ms apply to" and "why is the job
  red" with no other source.
- **SC-003**: `python -m pytest -q` passes; the default suite stays within about 2 s of its
  current time.

## Assumptions

- "Over the same runs" means the same number of runs as the hook figure, measured once per
  session at the first benchmark and cached, not interleaved with each hook call. Interleaving
  would touch all three benchmark loops for no reading benefit.
- The floor is printed as CPU and wall because the in-workspace paths are budgeted on wall
  time and the others on CPU.
- Runner figures in the docs come from the issue body (three `main` runs of 2026-09-30); no
  run ids or local paths. The developer-hardware figure is claimed only for the paths
  measured at 40 to 50 ms here.
- Design 10.6 still describes the old load heuristic (assert outside CI when load is low);
  the code asserts only under `WUWEI_BENCH=1` since #211. The design spec is owner-amended,
  so the docs describe the code and the spec is left alone.
- The workflow comment ("quiet runner") is left as is: the issue forbids changing the job.
- No new docs page: the operator reference already holds operator data and is linked from
  the index.
