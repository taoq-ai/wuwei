# Feature Specification: one table per edge and the loop property test; no timing assertions; under 3000 tests

**Feature Branch**: `b9-cleanup` (feature directory `specs/849-edge-and-loop-tests/`)

**Created**: 2026-10-12

**Status**: Draft

**Input**: Issue #849, part 25 of the #789 deletion pass: "test(loop): one table per edge and
the loop property test; no timing assertions; under 3000 tests".

## Context

At 71d3f06b the suite collects 7668 tests from 2964 test functions: most of the count is
parametrized cases. The same edge is tested in many files (merge about 12 functions, force push
about 14, outward send about 45 functions with 300 cases), a scope test re-runs five other
files' tables outside a workspace, and eleven clock tests assert durations (hook latency
budgets, a cached check, trace recording, the scripted day under 20 s). Parts 23 and 24 delete
about 800 tests with their code. What the pass keeps is small: the edges (#839), the process
control in the derived `next` (#844) and the outward duties. Tests should follow it: one table
per edge, the loop property test as the loop's contract, and no assertion on time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each edge has one table (Priority: P1)

**Why this priority**: the edges are the only refusals left with `guards.enforce` on; a reader
must find all of an edge's cases in one place.

**Independent Test**: `tests/test_edges.py` holds exactly one table test per edge.

**Acceptance Scenarios**:

1. **Given** `tests/test_edges.py`, **When** collected, **Then** it has one table test for each
   of: merge, approve, admin (with branch protection), force push, default-branch push, deploy,
   outward send, bare `gh pr create`; each table's rows carry the call, the context (inside
   or outside a workspace, `guards.enforce` on or off, item linked or not) and the expected exit
   and reason fragment.
2. **Given** any row of an edge that another test file also asserted at 71d3f06b, **When** this
   part lands, **Then** the row is in the edge's table and no other file asserts the edge's
   decision for it.
3. **Given** an edge table, **When** a row fails, **Then** the failure message lists every
   failing row with what it got (no row hides behind the first failure).

### User Story 2 - The loop property test is the loop's contract (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `tests/test_loop.py`, **When** it runs, **Then** its generated worlds check every
   invariant the #844 property test checks (every ready launch offered, at most one owner
   decision, no item done with an open duty, every due duty in `next`, CAP never exceeded) and
   the per-issue dead-end and drift cases.
2. **Given** `pytest --durations=0 tests/test_loop.py` after part 23, **When** it runs, **Then**
   the property test's setup and calls take under one second in total on a developer machine;
   this is measured, never asserted.

### User Story 3 - No test asserts a duration (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `tests/`, **When** searched, **Then** no assertion compares an elapsed time,
   `time.monotonic`, `time.perf_counter`, `time.process_time` or a latency figure from a real
   clock with a budget, and no test carries the `timing` xdist group.
2. **Given** the CI latency job, **When** it runs, **Then** it measures hook latency with a
   script (`scripts/hook_latency.py`) and reports it through `scripts/latency_report.py`,
   informational as today.
3. **Given** a test of a timeout behaviour (a held lock, a slow probe), **When** it runs,
   **Then** it asserts the outcome (gave up, reason recorded) with a short configured limit,
   not how long it took.

### User Story 4 - The suite holds under 3000 tests (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the repository, **When** the test functions (`def test_`) under `tests/` are
   counted, **Then** there are fewer than 3000 (B9 lead call (b): test functions, not collected
   cases; no parametrized table is collapsed).
2. **Given** CI, **When** the tests job runs, **Then** a step fails if that count is 3000 or more.

### Edge Cases

- A table row that was a separate parametrized case keeps its id as the row's label.
- Rows that only differed by an obsolete context (a deleted profile, posture or tier) collapse
  to the rows the current code distinguishes; the table keeps one row per distinct decision
  input.
- Mutation and canary tests that probe a non-edge guard stay where they are.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `tests/test_edges.py` MUST hold one table test per edge (eight), plus the shared
  parser tests (segments, an unparsed call logged once and run, unsplittable calls).
- **FR-002**: The edge rows in `tests/test_profiles.py`, `tests/test_seat_command_forms.py`,
  `tests/test_parser_warns.py`, `tests/test_scope_first.py`, `tests/test_guard_mutation.py`
  (edge probes), `tests/test_merge.py` (guard cases), `tests/test_outward.py` (`check_send`
  cases), `tests/test_canary.py` (edge cases) and `tests/test_enforce.py` (edge rows) MUST move
  into the edge tables and leave those files.
- **FR-003**: `tests/test_loop.py` MUST keep the property test and the per-issue cases; its
  docstring MUST describe the contract (no stale xfail note).
- **FR-004**: Every real-clock duration assertion MUST go: `tests/test_hooks.py`
  `assert_latency_budget` and its callers, `tests/test_integrity.py::test_cached_check_latency`,
  `tests/test_traces.py::test_large_arguments_record_under_50ms_cpu` (its non-timing assertions
  stay), the elapsed checks in `tests/test_e2e_day.py` and `tests/test_path_day.py`, and any
  status-line elapsed check part 23 moved; timeout tests assert outcomes.
- **FR-005**: The hook latency measurement MUST move to `scripts/hook_latency.py`; the CI
  latency job runs it; the latency decision tests move to `tests/test_latency_report.py` with
  fake figures.
- **FR-006**: The `timing` xdist group, its rerun step in `.github/workflows/tests.yml`, the
  marker in `pyproject.toml` and the `TIMING` pin in `tests/test_dev_cycle.py` MUST go.
- **FR-007**: Superseded by B9 lead call (b): the limit counts test functions (`def test_`);
  no parametrized table is collapsed and every row stays its own case.
- **FR-008**: CI MUST fail when the count of test functions reaches 3000.

### Key Entities

- **Edge table**: rows `(label, call, context, expected exit, reason fragment)` for one edge.
- **Loop contract**: the property test's invariants over generated worlds.

## Success Criteria *(mandatory)*

- **SC-001**: `grep -rh "def test_" tests | wc -l` reports fewer than 3000.
- **SC-002**: `grep -rnE "monotonic\(\)|perf_counter\(\)|process_time\(\)|elapsed|_ms *<|seconds *<|xdist_group\('timing'\)" tests`
  finds no assertion on a duration (a fake clock passed into the code is allowed).
- **SC-003**: `tests/test_edges.py` has eight edge table tests; no other file calls
  `edges.check_bash` or `edges.check_deploy` to assert a decision. `tests/test_outward.py` keeps
  its `check_send` calls: they test the outward lint beside the send edge.
- **SC-004**: The full suite passes in CI; `tests/test_loop.py`'s property test takes under one
  second in `--durations` output (recorded in the PR body).

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. A table test is one test function that loops its rows and asserts the list of failing rows
   is empty; it reports every failing row, so it loses nothing a parametrized case showed except
   a separate pass line per row. No pytest plugin is needed.
2. Collapsing a parametrized table is not loosening: every distinct row stays. A row is dropped
   only when the same input and expectation is already in the edge's table (a duplicate), and
   the plan names the file it came from.
3. "Under a second" is measured with `--durations`, never asserted (the issue forbids timing
   assertions). After part 23, `materialise` writes only the log (no `state.json`, no snapshot,
   no fsync per write) and the pair materialisation goes; if the setup still exceeds a second,
   `materialise` writes each world's records in one `_write_state` call. The 300 worlds and
   their invariants stay.
4. Hook latency stays measured (#346, the informational CI job) by a script, not a test.
5. The count limit lives in CI as a collect-only step; a test that collects the suite would
   double the run.
6. Builds on parts 23 and 24 on the same branch; the counts in plan.md are at 71d3f06b and the
   builder re-measures after each phase.
