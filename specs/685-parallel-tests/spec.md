# Feature Specification: the suite runs in parallel and the slow tests are cut

**Feature Branch**: `685-parallel-tests`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #685 (owner, 2026-10-10): the full suite takes 19 minutes locally and
about as long in CI, and each item's PR waits on it. Reduce the development cycle without
loosening any test or budget (#346). Deliver: pytest-xdist as a dev-only dependency and a
parallel CI run with the wall-clock tests in one `xdist_group("timing")`, rerun alone when
the parallel run flags them; a profile and cheaper slow tests; the 3.11 and 3.12 jobs both
parallel; a target that runs only the tests a diff touches.

## Root cause

Measured on `main` (f497c9e) in this worktree, 2026-10-10. The host was shared with other
pipeline runs (load average 40 to 70 on 10 cores), so absolute seconds are about 2.3x the
owner's 19 minutes; the plan uses the ranking. Figures are in `research.md`.

1. **Everything runs on one core.** `.github/workflows/tests.yml:24` runs
   `python -m pytest -q` in one process; `pyproject.toml:10` lists only `pytest` as a dev
   dependency. The suite is 10,832 tests (10,822 passed, 10 skipped). Its files share no
   state: split into 8 file shards in 8 processes, every shard passed, in 403 s wall
   against about 2,660 s of summed shard time.
2. **A heavy tail.** Tests and phases of 0.5 s or more are 676 rows and 70% of the time
   (1,852 s of about 2,660 s). The largest avoidable costs repeat the same work for every
   test or every call:
   - `tests/test_setup.py:218` `project` builds three git repositories with 15 `git`
     launches per test (`make_repo`, line 207): 116 s of setup across the file.
   - `tests/test_canary.py:13` `secured` runs a full `init.run` per test: 88 s of setup.
     The initialized tree holds no absolute path of its own (checked: 74 files, none
     contains the workspace path), so a copy is the same workspace.
   - `tests/test_workspace.py:23` `cli()` launches a fresh interpreter
     (`python -S -P -m wuwei`) for each of its 47 calls: the file takes 169 s.
   - `tests/test_tone.py:37` `classes()` and `tests/test_reasons.py:151` `all_reasons()`
     parse every CLI module again on each call (four `all_reasons` calls, two `_cards`
     calls): 43 s for the two tone budget tests, 22 s for the two reason tests.
   - `tests/test_state_allowlist.py:161` `reader_inventory()` parses every CLI module for
     each of its four callers (0.9 s CPU each).
3. **Wall-clock tests have no grouping.** Twelve tests assert a clock or print a latency
   figure (`research.md`, Timing tests). Beside loaded workers they would measure the
   neighbours. `tests/test_invariants.py:1154` already flips at its 1.0 s CPU budget on the
   runner when run serially (#626).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Does `xdist_group("timing")` keep timing tests away from loaded workers? A: No. It puts
  them on one worker while the other workers keep running. That is why the issue also asks
  for a rerun alone, and this feature does both: the group in the parallel run, and a serial
  rerun of exactly the timing tests that failed there.
- Q: When the parallel run fails, which failures are retried? A: Only tests in the timing
  group. Any other failure fails the job with no retry; retrying a functional test would hide
  an isolation bug, which weakens it.
- Q: Why not always run the timing tests alone after the parallel run? A: Cost. The twelve
  timing tests are about 140 s of quiet serial time (the latency probes and the two scripted
  days); running them alone every time pushes the CI job past 6 minutes. In the group they
  share one worker in parallel with the rest and add no wall time.
- Q: How does the rerun step tell timing failures from the rest? A: From pytest's own
  last-failed cache, read by a few lines of inline Python in the step. Under `--dist
  loadgroup` every grouped failure is recorded as `<nodeid>@timing`. The step passes only
  when the cache is non-empty and every entry ends in `@timing`; it then runs
  `pytest.main(['-q', <those node ids without the suffix>])` alone. A missing or empty cache,
  or any other entry (a plain test, a collection error), fails the job without a retry.
  (Corrected by the builder: under `--dist loadgroup` xdist records a grouped failure as `<nodeid>@timing`, which a plain `--lf` run cannot match, so `--lf` fell back to every test and the collect-only guard always exited 0. See research.md, Rerun guard.)
- Q: `make test-fast` or `bin/wuwei dev test --changed`? A: Neither form. The repository has
  no Makefile, and `bin/wuwei` is the product a user installs, which should not carry a
  developer command. A stdlib script beside the other developer scripts:
  `python3 scripts/changed_tests.py [pytest args]`.
- Q: What does "plus their imports" select? A: A test file the diff changes; a test file that
  imports a changed module (under `cli/`, `adapters/` or `tests/`, test modules included),
  followed through test-to-test imports until nothing new is added; for a changed file that
  is not an importable module (docs, skills, charters, scripts, templates), a test file whose
  source contains that file's name. A change to `tests/conftest.py` or `pyproject.toml` runs
  the whole suite.
- Q: Which slow tests are cut? A: The five shared-spot costs in Root cause 2, each in a
  fixture or a helper, never in an assertion. `tests/test_invariants.py` gets only its marker
  line: #626 is changing its walk at the same time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A PR's suite finishes in minutes (Priority: P1)

A seat raises a PR; the 3.11 and 3.12 test jobs each run the full suite in parallel and
report within 6 minutes. A timing test that flipped beside a busy neighbour gets one run
alone; a real regression stays red.

**Why this priority**: every PR waits on this job; it is the owner's complaint.

**Independent Test**: a test reads `.github/workflows/tests.yml` and pins the parallel
command, the rerun step and its guard; `python -m pytest -q -n auto --dist loadgroup` passes
locally.

**Acceptance Scenarios**:

1. **Given** a PR, **When** the `test` job runs, **Then** both matrix entries (3.11, 3.12)
   install `pytest pytest-xdist` and run `python -m pytest -q -n auto --dist loadgroup`.
2. **Given** the parallel run fails only on timing tests, **When** the rerun step runs,
   **Then** it reruns those tests alone (their node ids from the last-failed cache) and the job takes the
   rerun's result.
3. **Given** the parallel run fails on any test outside the timing group, **Then** the job
   fails and no test is rerun.
4. **Given** the parallel run fails with nothing recorded as failed, **Then** the job fails.
5. **Given** the CI job on the runner, **Then** its wall-clock is under 6 minutes for the
   full suite, with before and after in the PR body.

### User Story 2 - Wall-clock tests share one worker (Priority: P1)

**Why this priority**: the budgets (#346) must not go red because of parallelism.

**Independent Test**: collect with `-m xdist_group` and compare the node ids with the list in
`research.md`.

**Acceptance Scenarios**:

1. **Given** the twelve timing tests listed in `research.md`, **Then** each carries
   `pytest.mark.xdist_group('timing')` and no other test does.
2. **Given** `-m xdist_group`, **Then** exactly those tests are selected, with or without
   pytest-xdist installed (the marker is registered in `pyproject.toml`).
3. **Given** the latency job (`WUWEI_BENCH=1`, no `-n`), **Then** it runs as today.

### User Story 3 - The local suite runs in under 5 minutes (Priority: P2)

**Independent Test**: `python -m pytest -q -n auto --dist loadgroup` on a 10-core machine,
wall-clock recorded in `research.md` before and after.

**Acceptance Scenarios**:

1. **Given** a quiet 10-core machine, **When** the suite runs with `-n auto --dist
   loadgroup`, **Then** it passes in under 5 minutes.
2. **Given** the five fixture and helper changes, **Then** every assertion in the touched
   tests is unchanged and each test still produces the same evidence: the same command
   reaches the same code and prints the same output.

### User Story 4 - A seat runs only the tests its diff touches (Priority: P2)

**Independent Test**: table tests of the selection on a temporary tree, and of the script's
exits with git and pytest replaced.

**Acceptance Scenarios**:

1. **Given** a diff that changes `tests/test_x.py`, **Then** `tests/test_x.py` is selected.
2. **Given** a diff that changes `cli/wuwei/heartbeat.py`, **Then** every test file with
   `from wuwei import heartbeat`, `import wuwei.heartbeat` or
   `from wuwei.heartbeat import ...` is selected, and a test file importing one of those test
   modules is selected too.
3. **Given** a diff that changes `docs/site/reference.md`, **Then** every test file whose
   source contains `reference.md` is selected.
4. **Given** a diff that changes `tests/conftest.py` or `pyproject.toml`, **Then** the whole
   suite runs.
5. **Given** no changed file maps to a test, **Then** the script says so and exits 0 without
   running pytest.
6. **Given** git cannot produce the diff, **Then** the script prints the reason and exits 2.
7. **Given** a selection, **Then** the script prints it and runs
   `<current interpreter> -m pytest -q <extra args> <files>`, exiting with pytest's code.

### Edge Cases

- A worker crash in the parallel run: xdist reports the test as failed, so the rerun guard
  treats it like any other failure (red unless it is a timing test).
- A collection error is recorded under its module, outside the timing group: the job fails.
- Untracked new files count as changed (`git ls-files --others --exclude-standard`).
- A deleted module still maps to its name, so tests that imported it run and fail loudly.
- Tests of one module now run on several workers. A test that depends on another test's side
  effect is fixed at its fixture; only when that is impossible does its module get its own
  `xdist_group`, recorded in `research.md`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `pyproject.toml` MUST list `pytest-xdist` under the `dev` extra and register the
  `xdist_group` marker; runtime code stays stdlib only.
- **FR-002**: The `test` job MUST install `pytest pytest-xdist` and run
  `python -m pytest -q -n auto --dist loadgroup` on both 3.11 and 3.12.
- **FR-003**: When that step fails, a second step MUST fail the job unless the last-failed
  cache is non-empty and every entry ends in `@timing`, and otherwise rerun those node ids
  (suffix removed) alone (no `-n`), the job taking that result.
- **FR-004**: The twelve timing tests MUST carry `pytest.mark.xdist_group('timing')`.
- **FR-005**: The `ziran-audit`, `latency`, `skill-evals` and `headless-e2e` jobs MUST keep
  starting in parallel with `test` (no `needs:`); the latency job is unchanged.
- **FR-006**: The five slow spots in Root cause 2 MUST be made cheaper at their fixture or
  helper, with every assertion unchanged.
- **FR-007**: `scripts/changed_tests.py` MUST select and run the tests a diff touches as in
  User Story 4, stdlib only, exit 0 with nothing to run, 2 when git cannot produce the diff,
  and otherwise pytest's own exit code.
- **FR-008**: `CONTRIBUTING.md` MUST name the parallel command and the changed-tests script.

### Key Entities

- **Timing group**: tests whose assertion or printed figure is a clock. Marked, selected by
  `-m xdist_group`.
- **Last-failed set**: pytest's cache of failed node ids, written by the parallel run and read
  by the rerun step directly (`.pytest_cache/v/cache/lastfailed`).

## Success Criteria *(mandatory)*

- **SC-001**: CI `test` job under 6 minutes per matrix entry on the runner (before and after
  in the PR body).
- **SC-002**: Local `pytest -n auto --dist loadgroup` under 5 minutes on 10 cores.
- **SC-003**: `git diff main -- tests` shows no changed or removed `assert` line and no
  changed budget constant.
- **SC-004**: The full suite passes serially and with `-n auto --dist loadgroup`, twice each.

## Assumptions

- No orchestrator notes file exists for #685; the issue is the only input.
- The local profile ran on a shared host (load 40 to 70). The ranking is trusted, the absolute
  seconds are not; the builder measures before and after on the quietest machine it has and
  records both in `research.md`.
- "Wall-clock benchmarks" means every test that asserts a clock or reports a latency figure
  (twelve, listed in `research.md`), not the decision and row tests in `test_hooks.py` that
  replace `startup_floor`.
- Rerunning a flagged timing test alone does not weaken it: the issue asks for it, the budget
  is unchanged, and the rerun is the quiet measurement the budget assumes.
- GitHub's `ubuntu-latest` runner for a public repository has 4 vCPUs, so `-n auto` is 4
  workers: about 19 minutes divided by 4, under 5 minutes before the cuts.
- The CI before and after figures go in the PR body, which the orchestrator writes; the
  builder records the local figures in `research.md`.
- Plain `python -m pytest -q` keeps working and `README.md` keeps it; `-n auto` is the
  documented fast form, not a requirement.
- `tests/test_invariants.py` is being changed by #626 in parallel; this feature adds one
  marker line there to keep the merge trivial.
- Test helpers that cache a read-only result (`all_reasons`, `_cards`, `reader_inventory`)
  save less under xdist, where a module's tests can land on different workers; they still
  save every repeat on the same worker and in a single-file run.
