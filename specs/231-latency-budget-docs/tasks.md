# Tasks: Hook latency budget per hardware class and the CI latency job

Each test task is written, run and seen failing for the stated reason before its
implementation task.

## Phase 1: Startup floor in the report line [US2]

- [X] T001 [US2] In tests/test_hooks.py, `test_latency_budget_decision`: replace the floor
  with `monkeypatch.setitem(globals(), 'startup_floor', lambda runs: (20.0, 22.0))`; the
  `'assert'` branch matches `r'startup floor CPU 20\.00 ms, wall 22\.00 ms'`; the `'skip'`
  branch matches `r'CPU 51\.00 ms.*wall 60\.00 ms.*python3 -I startup floor CPU 20\.00 ms, wall 22\.00 ms.*load'`.
  Run `python -m pytest -q tests/test_hooks.py -k latency_budget_decision`. Expected
  failure: the report has no startup floor (assert and skip cases fail to match).
- [X] T002 [US2] In tests/test_hooks.py: add `from functools import cache`, the cached
  `startup_floor(runs)` helper (p95 CPU and wall ms of `sys.executable -I -c pass` over
  `runs` runs, measured like the benchmarks), and the floor in the `assert_latency_budget`
  report between the hook figure and the load. Budget logic untouched. T001 passes.

## Phase 2: Operator reference [US1]

- [X] T003 [US1] Add `test_reference_states_hook_latency_budget` to tests/test_docs.py
  (phrases, the job command in both docs/site/reference.md and .github/workflows/tests.yml,
  `continue-on-error: true` in the workflow, `latency budget` in docs/site/index.md). Run it.
  Expected failure: `Hook latency budget` not in reference.md.
- [X] T004 [US1] Append the "Hook latency budget" section with "The latency CI job"
  subsection to docs/site/reference.md, and extend the operator reference entry in
  docs/site/index.md, as specified in plan.md. T003 passes.

## Phase 3: Verify

- [X] T005 Run `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency` and
  confirm every printed report line contains `python3 -I startup floor CPU` (failures on
  the in-workspace paths on a loaded host are expected and out of scope).
- [X] T006 Run `python -m pytest -q` from the repository root; everything passes. Check
  every changed file for em-dashes, emojis and absolute local paths, and confirm
  `git diff --stat` touches only tests/test_hooks.py, tests/test_docs.py,
  docs/site/reference.md, docs/site/index.md and specs/231-latency-budget-docs/.
