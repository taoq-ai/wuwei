# Tasks: the fast-check timeout is per repository in config and the error names the limit

**Input**: `specs/724-check-timeout/spec.md`, `specs/724-check-timeout/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Run tests with `python -m pytest -q` from the repository root.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 - the key and the port parameter (P1)

### Tests first

- [X] T001 [P] [US1] In `tests/test_workspace.py`, add a test: a config with one `[[repos]]`
  entry and no `check_timeout_seconds` loads with `repos[0]['check_timeout_seconds'] == 300`;
  `check_timeout_seconds = 900` loads as 900; `0` is refused with a `ConfigError` naming
  `repos.0.check_timeout_seconds`. Run it; it fails (no default, unknown key).
- [X] T002 [P] [US1] In `tests/test_adapters.py`, change the `CALLS` row to
  `('checks', 'run', ('path', 'command', 'timeout'), True)`. Run `test_module_contracts` and
  `test_none_call`; they fail (registry and adapters take two parameters).
- [X] T003 [P] [US1] In `tests/test_fast_checks.py`, add an adapter test beside
  `test_local_checks_execute_configured_shell_command`: stub `subprocess.run` as a 600 s
  command (raise `TimeoutExpired(argv, kwargs['timeout'])` when `kwargs['timeout'] < 600`,
  else return exit 0); `adapter.run(str(tmp_path), 'suite', timeout=900)` is exit 0 and
  `adapter.run(str(tmp_path), 'suite')` is exit 2 (spec US1 scenarios 1 and 2 at the
  adapter). Run it; it fails (`run` has no `timeout` parameter).

### Implementation

- [X] T004 [US1] In `cli/wuwei/workspace.py`, add `"check_timeout_seconds": (int, 300, 1)` to
  the `repos` schema beside `"tests"` (plan Design 1). T001 passes.
- [X] T005 [US1] In `cli/wuwei/registry.py`, set `'checks': {'run': ('path', 'command',
  'timeout')}`; in `adapters/checks/none.py` and `adapters/checks/local.py` the signature
  becomes `run(path, command, timeout=300, root=None)`, and the local adapter passes
  `timeout=timeout` to `subprocess.run` (plan Design 2 to 4). T002 and T003 pass.

## Phase 2: User Story 1 - every caller passes the repository's limit (P1)

### Tests first

- [X] T006 [P] [US1] In `tests/test_fast_checks.py`, add a test on `workspace_case`: replace
  `fast_checks = ["unit"]` in `.wuwei/config.toml` with
  `fast_checks = ["unit"]\ncheck_timeout_seconds = 900`; a fake checks port
  `run(path, command, timeout=None, root=None)` records `timeout` and returns `Result(0)`;
  `main(['fast-checks', str(root / 'repo')]) == 0`, the recorded `timeout` is 900 and the
  record's exit is 0 (SC-001). Without the line the recorded `timeout` is 300 (SC-004). Run
  it; it fails (the port is called without `timeout`).
- [X] T007 [P] [US1] In `tests/test_worktree_command.py`, change the `checked` fake to
  `lambda path, command, timeout=None, root=None: runs.append((path, command, timeout)) or
  result` and update the `runs` assertions to carry `300`; add a case with
  `check_timeout_seconds = 900` in the repo table asserting 900 reaches the bootstrap run.
  Run it; it fails (bootstrap passes no `timeout`).

### Implementation

- [X] T008 [US1] In `cli/wuwei/fast_checks.py:92`, pass
  `timeout=repo['check_timeout_seconds']` to `runner.run`. T006 passes.
- [X] T009 [US1] In `cli/wuwei/commands/worktree.py:63`, pass
  `timeout=repos[0]['check_timeout_seconds']` to the bootstrap `run`. T007 passes.
- [X] T010 [US1] Update the fixed-signature check fakes so they accept `timeout`:
  `tests/test_fast_checks.py` (the `run` fakes near lines 43, 65 and 230; the last forwards
  `timeout` to the real adapter), `tests/test_build.py:48` (`FakeChecks.run`),
  `tests/fakes/day.py:218` (`check`). Run the full suite; no `TypeError` from a fake. Rows
  that quote the old timeout text as a fake port result (`tests/test_calibrate.py:323`,
  `tests/test_worktree_command.py:539`) stay as they are.

## Phase 3: User Story 2 - the error names the command, the limit and the setting (P1)

### Tests first

- [X] T011 [US2] In `tests/test_fast_checks.py`, add a test: `subprocess.run` stubbed to raise
  `TimeoutExpired`; `adapter.run(str(tmp_path), 'python3 -m pytest -q', timeout=900)` returns
  exit 2 with reason exactly ``fast check `python3 -m pytest -q` exceeded 900 s
  (repos.<n>.check_timeout_seconds); raise it with bin/wuwei config set or split the check``
  (spec US2 scenario 1, SC-002); an `OSError` from `subprocess.run` still gives
  `fast check could not run: OSError` (US2 scenario 2). Run it; the message assertion fails
  (today: `fast check could not run: TimeoutExpired`).

### Implementation

- [X] T012 [US2] In `adapters/checks/local.py`, add the `except subprocess.TimeoutExpired:`
  branch before the generic one, returning the message (plan Design 3). T011 passes.

## Phase 4: User Story 3 - calibration proposes the limit (P2)

### Tests first

- [X] T013 [US3] In `tests/test_calibrate.py`, update `test_classify_measures_test_runners`:
  the fake becomes `lambda path, command, timeout=None, root=None: calls.append((path,
  command, timeout)) or ...`, the call is `classify(..., runner, 60, None, 300, measured)`
  with `measured = {}`, and it asserts `calls == [(..., 'python3 -m pytest -q', 300)]` and
  that `measured` holds the measured seconds for that command (US3 scenario 3). Add a row
  with times `[0.0, 290.0]` whose note contains `near the 300 s check timeout`. Run it; it
  fails.
- [X] T014 [US3] In `tests/test_calibrate.py`, add a test beside
  `test_calibrate_measure_lists_slow_tests_as_ci_only`: `configure(...)`,
  `measured(monkeypatch, ports, [0.0, 290.0])`, `main('calibrate', '--measure') == 0`; the
  printed diff contains `+check_timeout_seconds = 600` (US3 scenario 1, SC-003). With
  `[0.0, 75.0]` the output has no `check_timeout_seconds` (US3 scenario 2). Run it; it fails.
- [X] T015 [P] [US3] In `tests/test_calibrate.py`, add a `proposal` unit test: facts with
  `check_timeout_seconds: 600` against a raw config without the key add it; against a raw
  config with `check_timeout_seconds = 450` it is the hand edit
  `('repos.0.check_timeout_seconds', 450, 600)`; facts without the key propose nothing. Run
  it; it fails.

### Implementation

- [X] T016 [US3] In `cli/wuwei/calibrate.py`, add `NEAR = 0.8`; give `classify` the
  `timeout=300, measured=None` parameters, pass `timeout=timeout` to the runner, fill
  `measured`, append the near-limit note, and rewrite the line 165 `ponytail:` comment (plan
  Design 6). T013 passes.
- [X] T017 [US3] In `cli/wuwei/calibrate.py`, in `survey` pass the repository's limit and a
  `measured` dict and set `result['check_timeout']`; in `proposed` add
  `'check_timeout_seconds': result.get('check_timeout')`; in `proposal` add the
  `('check_timeout_seconds', facts.get('check_timeout_seconds'))` row (plan Design 6). T014
  and T015 pass.
- [X] T020 [US3] Review fix: move the T017 survey lines into `calibrate.measure_checks` and
  call it from the setup flow's "Run your tests once now" loop in
  `cli/wuwei/commands/setup.py`, so setup also proposes `check_timeout_seconds`. Test first:
  `test_setup_proposes_check_timeout_near_the_limit` in `tests/test_setup.py`. Add
  `check_timeout_seconds` to the two fake repository dicts in `tests/test_build_next.py`.

## Phase 5: Docs and polish

- [X] T018 [P] In `docs/site/configuration.md`, add the `repos.check_timeout_seconds` row
  after `repos.tests` and update the calibration paragraph's "capped at 300 seconds" with the
  per-repository limit and the 80 % proposal sentence (plan Design 7, FR-006).
- [X] T019 Run `python -m pytest -q` from the repository root; everything passes. Check the
  changed files for em-dashes, emojis and absolute local paths and remove any.

## Dependencies

- T001 to T003 before T004, T005. Phase 1 before Phases 2 to 4.
- T006, T007 before T008 to T010; T011 before T012; T013 to T015 before T016, T017.
- T010 runs with T008 and T009; T018 any time after T005.
