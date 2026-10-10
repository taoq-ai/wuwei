# Tasks: the suite runs in parallel and the slow tests are cut

**Input**: `specs/685-parallel-tests/spec.md`, `plan.md`, `research.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
The fixture cuts (Phase 4) are refactors under existing tests: their test is the unchanged
test file passing, before and after, with the durations recorded.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Install pytest-xdist into the interpreter the task names (dev only; it is not in
  the repository). Record the before figures in `specs/685-parallel-tests/research.md`
  (Measurements): `python -m pytest -q --durations=50` serial wall-clock and load average.

## Phase 2: User Story 1 and 2 - parallel CI and the timing group (P1)

### Tests first

- [X] T002 [US1] Create `tests/test_dev_cycle.py` with the workflow pin from plan.md (Tests):
  the `test` job slice holds `pip install pytest pytest-xdist`,
  `python -m pytest -q -n auto --dist loadgroup`, `continue-on-error: true`,
  `if: steps.suite.outcome == 'failure'` and the inline rerun, which the test extracts and
  runs against fake last-failed caches (plan.md, Tests); `.github/workflows/tests.yml` has no `needs:`. Run it; it fails on
  the install line.
- [X] T003 [US2] In `tests/test_dev_cycle.py`, add the pyproject pin: `pytest-xdist` in
  `project.optional-dependencies.dev` and an `xdist_group` entry in
  `tool.pytest.ini_options.markers`. Run it; it fails.
- [X] T004 [US2] In `tests/test_dev_cycle.py`, add the timing set test: an AST scan of
  `tests/test_*.py` for functions decorated `pytest.mark.xdist_group('timing')` equals the
  twelve `(file, name)` pairs in `research.md` (Timing tests). Run it; it fails (empty set).

### Implementation

- [X] T005 [US2] `pyproject.toml`: add `pytest-xdist` to `dev` and the `markers` line
  (plan.md 1). T003 passes.
- [X] T006 [US1] `.github/workflows/tests.yml`, job `test`: install line, the parallel step
  with `id: suite` and `continue-on-error: true`, and the rerun step with its comment
  (plan.md 2). Nothing else in the file changes. T002 passes.
- [X] T007 [P] [US2] Add `@pytest.mark.xdist_group('timing')` above each timing test, one
  line each and nothing else: `tests/test_invariants.py` (`test_invariants_hold`),
  `tests/test_traces.py`, `tests/test_integrity.py`, `tests/test_heartbeat.py`,
  `tests/test_adapters.py`, `tests/test_e2e_day.py`, `tests/test_path_day.py` (two tests),
  `tests/test_hooks.py` (four tests). T004 passes.
- [X] T008 [US1] Verify the rerun guard on this repository with xdist (scratch, nothing
  committed): run `python -m pytest -q -n auto --dist loadgroup` on a temporary failing copy
  of one timing test and one plain test, and confirm the cache rows and exit codes match
  `research.md` (Rerun guard). Record the result there in one line.
- [X] T009 [US1] Run `tests/test_calibrate.py`, `tests/test_docs.py`,
  `tests/test_latency_report.py`, `tests/test_skill_evals.py`, `tests/test_headless_e2e.py`
  (they read `tests.yml`); all pass.

## Phase 3: User Story 4 - changed tests (P2)

### Tests first

- [X] T010 [US4] In `tests/test_dev_cycle.py`, load `scripts/changed_tests.py` with
  `spec_from_file_location` and add table tests of `select(paths, root)` on a `tmp_path`
  tree holding `tests/test_a.py` (`from wuwei import heartbeat`), `tests/test_b.py`
  (`from test_a import fixture_x`), `tests/test_c.py` (source mentions `reference.md`),
  `tests/test_d.py` (no match): changed `tests/test_d.py` selects it (4.1); changed
  `cli/wuwei/heartbeat.py` selects a and b (4.2); changed `docs/site/reference.md` selects c
  (4.3); changed `tests/conftest.py` or `pyproject.toml` returns `['tests']` (4.4); changed
  `templates/unused.txt` returns `[]` (4.5). Run them; they fail (no script).
- [X] T011 [US4] In `tests/test_dev_cycle.py`, add `main` tests with `monkeypatch` on the
  loaded module: `changed` raising `subprocess.CalledProcessError` returns 2 and prints
  `cannot read the diff` to stderr (4.6); an empty selection returns 0, prints
  `no test touched by the diff` and never calls `subprocess.run` (4.5); a selection calls
  `subprocess.run` with `[sys.executable, '-m', 'pytest', '-q', '-x', 'tests/test_a.py']`
  for `main(['-x'])` and returns its returncode 1 (4.7). Run them; they fail.

### Implementation

- [X] T012 [US4] Create `scripts/changed_tests.py` with `changed`, `module`, `imports`,
  `select`, `main` and the `ponytail:` ceiling comment (plan.md 5). T010 and T011 pass.
- [X] T013 [US4] Run `python3 scripts/changed_tests.py` on this branch once and record the
  selection size and wall-clock in `research.md`.

## Phase 4: User Story 3 - cheaper slow tests (P2)

Each task: run the file before (`--durations=10`, record), change only the fixture or
helper, run the file again serially and with `-n auto --dist loadgroup`, record. No `assert`
line changes.

- [X] T014 [P] [US3] `tests/test_setup.py`: module-scoped `repos` template and `project`
  copying it (plan.md 4a).
- [X] T015 [P] [US3] `tests/test_canary.py`: module-scoped `initialized` template and
  `secured` copying it; tests that assert on init's own output (at least
  `test_init_random_private_material`) run `init.run` themselves; compare one copied tree
  with one fresh init and note it in `research.md` (plan.md 4b).
- [X] T016 [P] [US3] `tests/test_workspace.py`: in-process `cli()`, the subprocess body kept
  as `cli_process` for `test_init_layout` only; any test moved back to `cli_process` listed
  in `research.md` with the reason (plan.md 4c).
- [X] T017 [P] [US3] `tests/test_reasons.py` `all_reasons` cached as a tuple;
  `tests/test_tone.py` `classes` returning fresh lists from a cached `_classes` (plan.md 4d).
- [X] T018 [P] [US3] `tests/test_state_allowlist.py`: `reader_inventory` cached, returning
  frozensets (plan.md 4e).

## Phase 5: Docs and verification

- [X] T019 `CONTRIBUTING.md`: the dev dependency line and the run line (plan.md 6).
- [ ] T020 (Deferred: the owner wants CI as the gate, 2026-10-10; the builder ran only the changed files.) Full suite serially, then `-n auto --dist loadgroup`, twice each (SC-004). Fix any
  order coupling at its fixture; group a module only as a last resort and record it in
  `research.md`.
- [ ] T021 (Deferred: the owner wants CI as the gate, 2026-10-10; the builder ran only the changed files.) Record the after figures in `research.md` (serial and parallel, with load
  average); confirm the parallel run is under 5 minutes on 10 cores (SC-002) or record why
  not.
- [X] T022 `git diff main -- tests` shows no changed or removed `assert` line and no changed
  budget constant (SC-003); no em-dashes, no emojis and no absolute local paths in any file
  written.
