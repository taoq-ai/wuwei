# Implementation Plan: Hook latency budget per hardware class and the CI latency job

**Branch**: `231-latency-budget-docs` | **Spec**: `specs/231-latency-budget-docs/spec.md`

## Summary

One test helper and one report-line change at the shared spot every benchmark routes
through (`assert_latency_budget` in `tests/test_hooks.py`), plus a "Hook latency budget"
section in the operator reference, checked by a docs test against the workflow. No runtime
code changes.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Nothing under `cli/`, `adapters/`, `hooks/` or
`.github/` changes.

## Constitution Check

- I Stdlib only: the helper uses `subprocess`, `resource`, `statistics`, `time`, `functools`.
- III One behaviour, one function: the floor lives in one helper, called only from
  `assert_latency_budget`, which all eight benchmark lines already share.
- IV Test first: the decision table asserts the floor in the report before the helper
  exists; the docs test asserts the section before it is written.
- V Ponytail: no new file, no refactor of the three benchmark loops, no config.

## Changes

### 1. Startup floor in the report line (`tests/test_hooks.py`)

- Add `from functools import cache` to the module imports.
- New module-level helper, placed right above `assert_latency_budget` (line 430):

  ```python
  @cache
  def startup_floor(runs):
      """p95 CPU and wall ms of a bare interpreter start, the floor under every hook figure."""
  ```

  Body: the same measurement pattern the benchmarks use (local imports of
  `getrusage`/`RUSAGE_CHILDREN`, `quantiles`, `perf_counter`), looping `runs` times over
  `subprocess.run([sys.executable, '-I', '-c', 'pass'], check=True)`, collecting
  `ru_utime + ru_stime` deltas and `perf_counter` deltas, returning
  `(quantiles(cpu, n=100)[94] * 1000, quantiles(wall, n=100)[94] * 1000)`.
  `sys.executable` is the binary the hooks run via the `python3` symlink in
  `subprocess_plugin`. Never a literal path.
- `assert_latency_budget(name, cpu_ms, wall_ms, capsys, *, wall_budget=None, runs=60)`:
  call `floor_cpu, floor_wall = startup_floor(runs)` and build the report as

  ```
  {name} p95 over {runs} runs: CPU {cpu_ms:.2f} ms, wall {wall_ms:.2f} ms, python3 -I startup floor CPU {floor_cpu:.2f} ms, wall {floor_wall:.2f} ms, load {load:.2f} on {cpus} CPUs
  ```

  Everything after the report string (print, `WUWEI_BENCH` branch, `cpu_ms < 50`,
  `wall_ms < wall_budget`, skip) stays exactly as it is. The floor is only printed.
- `test_latency_budget_decision` (line 411): add
  `monkeypatch.setitem(globals(), 'startup_floor', lambda runs: (20.0, 22.0))` so the table
  spawns nothing. Tighten its three branches to see the floor:
  - `'assert'`: `pytest.raises(AssertionError, match=r'startup floor CPU 20\.00 ms, wall 22\.00 ms')`.
  - `'skip'`: extend the match to
    `r'CPU 51\.00 ms.*wall 60\.00 ms.*python3 -I startup floor CPU 20\.00 ms, wall 22\.00 ms.*load'`.
  - `'pass'`: unchanged (nothing raised, nothing to read).
- Callers `test_hook_latency`, `test_status_line_latency`, `test_workspace_hook_latency`
  need no change: they already pass `runs` (60, 60, and 60 or 20).

### 2. Operator reference (`docs/site/reference.md`)

Append a section at the end of the page (after "Host terminal actions"):

- Heading `## Hook latency budget`.
- One paragraph: every tool call waits for `bin/wuwei hook <event>`, so the hook path carries
  a budget (spec 10.6). The budget is "50 ms CPU p95 on developer hardware (M-series class);
  about 2x on 2-CPU CI runners", and applies to PreToolUse, PostToolUse and
  `bin/wuwei status --line`. Inside a workspace, Stop, SubagentStop, SessionStart and the
  PreToolUse `git commit` and `git push` checks are held to 100 ms wall p95.
- Why the hardware class matters: `python3 -I -c pass` (the interpreter start every hook
  pays) takes about 20 ms on an M-series Mac and about twice that on a GitHub-hosted 2-CPU
  runner. PreToolUse, PostToolUse and `status --line` measure 40 to 50 ms CPU p95 on an
  M-series Mac.
- A table "CPU p95 on a 2-CPU runner, three `main` runs of 2026-09-30": PreToolUse about
  100 ms; PostToolUse 90 ms; `status --line` 110 ms; Stop 90 ms; SubagentStop 85 to 106 ms;
  SessionStart 140 to 157 ms; commit 115 ms; push 135 to 148 ms. No run ids.
- `### The latency CI job`: the `latency` job in `.github/workflows/tests.yml` runs
  `python -m pytest -q tests/test_hooks.py -k latency` with `WUWEI_BENCH=1` on every push and
  pull request. It is `continue-on-error`: a trend line, not a gate. On a 2-CPU runner it is
  red on every push, because the runner is about 2x slower than the hardware the budget is
  set for; a red job never blocks a merge.
- The report line format, in a `text` fence with placeholders (no invented figures):
  `<path> p95 over <runs> runs: CPU <ms> ms, wall <ms> ms, python3 -I startup floor CPU <ms> ms, wall <ms> ms, load <load> on <n> CPUs`.
  How to read it: compare the hook figure with the floor on the same line. A hook that keeps
  its usual distance above the floor is the runner; a hook whose distance above the floor
  grows from one run to the next got slower.
- Local runs, in a source checkout: `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency`
  asserts the budgets. Without `WUWEI_BENCH=1` the benchmarks print the same lines and skip,
  because wall time on a busy host is load-bound.

### 3. Docs index (`docs/site/index.md`)

Line 11: `[Operator reference](reference.html): JSON, decisions, retro, companion protocol and hook latency budget`.

### 4. Docs test (`tests/test_docs.py`)

New `test_reference_states_hook_latency_budget`: reads `reference.md` (whitespace-joined, as
the existing tests do for wrapped text) and `.github/workflows/tests.yml`; asserts the phrases
`Hook latency budget`, `50 ms CPU p95 on developer hardware (M-series class)`,
`about 2x on 2-CPU CI runners`, `100 ms wall p95`, `python3 -I -c pass`,
`a trend line, not a gate`, `continue-on-error`, `WUWEI_BENCH=1`, `startup floor`; asserts the
command `python -m pytest -q tests/test_hooks.py -k latency` appears in both the page and the
workflow, and `continue-on-error: true` in the workflow; asserts `latency budget` in
`index.md`.

## Must not change

The 50 ms constant and `wall_budget=100`, the `WUWEI_BENCH` decision in
`assert_latency_budget`, the three benchmark loops, `.github/workflows/tests.yml` (including
the job comment), anything under `cli/`, `adapters/`, `hooks/`, and the design spec.
