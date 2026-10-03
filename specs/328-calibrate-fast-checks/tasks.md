# Tasks: fix(calibrate): fill an explicit empty fast_checks, and propose only genuinely fast checks

**Input**: `specs/328-calibrate-fast-checks/spec.md`, `specs/328-calibrate-fast-checks/plan.md`
**Test command**: `python -m pytest -q` from the repository root.

Every behaviour is a test task followed by its implementation task. Run each test, see it
fail for the expected reason, then implement the minimum that makes it pass. New tests go in
`tests/test_calibrate.py` and reuse its `FIXTURES`, `facts`, `repo_block`, `applied`,
`DEPLOY_TABLE`, `ports`, `workspace_root`, `configure`, `main` and `promote` helpers. Fake
timing: `monkeypatch.setattr(calibrate, 'monotonic', iter([...]).__next__)`. Fake checks
port: add `'checks'` to the `ports` fixture's dict, as a `SimpleNamespace(run=...)` that
records its calls and returns `registry.Result(...)`. Use neutral fixture names only.

## Phase 1: An explicit empty fast_checks is fillable (US1, B6)

- [X] T001 Test: in `tests/test_calibrate.py`, `test_empty_fast_checks_is_filled`: with
  `raw = repo_block('acme/widget', 'fast_checks = []\n') + DEPLOY_TABLE`,
  `applied(tmp_path, raw, [(0, facts('python'))])` gives
  `parsed['repos'][0]['fast_checks'] == ['python3 -m pytest -q', 'ruff check .']` and
  `edits == []`, and the text holds exactly one `fast_checks =` line. The same with
  `'fast_checks = []  # none yet\n'`. A multi-line `'fast_checks = [\n]\n'` stays a hand
  edit (`edits` names `repos.0.fast_checks`). Expect the first assertion to fail (today:
  an edit, no addition).
- [X] T002 Implement in `cli/wuwei/calibrate.py` `proposal()`: section lines for `path`
  from `_labelled(raw)` in place of `deploy_lines`; the fill condition covers
  `key == 'fast_checks'`; docstring updated. T001 passes; the existing
  `test_present_owner_values_become_hand_edits` and
  `test_empty_deploy_lists_are_replaced_and_others_kept` still pass.

## Phase 2: Classification without measurement (US2, B7)

- [X] T003 Test: in `tests/test_calibrate.py`, `test_classify_without_measure`:
  `calibrate.classify(FIXTURES / 'python', ['python3 -m pytest -q', 'ruff check .'], None, 60)`
  returns `ruff check .` as `(True, ...)` and `python3 -m pytest -q` as `(False, note)` with
  `'unmeasured'` and `'--measure'` in the note; `npm run lint`, `black --check .` and
  `make lint` are fast; `npm test`, `cargo test`, `go test ./...`, `make test` and
  `make check` are not. Expect AttributeError (no `classify`).
- [X] T004 Implement `LINT` and `classify` (the `runner is None` and lint branches) in
  `cli/wuwei/calibrate.py`. T003 passes.
- [X] T005 Test: in `tests/test_calibrate.py`, `test_ci_only_without_measure_runs_nothing`:
  `configure(workspace_root, ('acme/widget', FIXTURES / 'python'))`, a fake checks port
  whose `run` fails the test if called; `main('calibrate') == 0`; stdout has
  `+fast_checks = ["ruff check ."]` and a `CI only, not proposed as a fast check:` line
  naming `python3 -m pytest -q`; `calibration.md` labels `ruff check .` as `fast check`,
  labels pytest `CI only` with `unmeasured`, and has a `## CI only (not proposed as fast checks)`
  section with `- acme/widget: python3 -m pytest -q`; the builder charter proposal names
  `ruff check .` and not `python3 -m pytest -q`. Expect the `+fast_checks` assertion to
  fail (today both commands are proposed).
- [X] T006 Implement in `cli/wuwei/calibrate.py`: `survey(..., measure=False)` sets
  `result['checks']` (runner loaded only when measuring), `proposed(result)`, `propose()`
  uses `proposed(r)`, `report()` labels and the CI only section; in
  `cli/wuwei/commands/calibrate.py`: `charter_proposals(..., calibrate.proposed(result), ...)`
  and the CI only stdout lines. T005 passes.
- [X] T007 Update `tests/test_calibrate.py::test_calibrate_this_repository`: replace the
  `+fast_checks = ["python3 -m pytest -q"]` assertion with `'+fast_checks' not in out` and
  the report listing `python3 -m pytest -q` as CI only with `unmeasured`; keep the clean
  `git status` assertion. Run it; it passes with T006 in place.

## Phase 3: Fill and promote end to end (US1 acceptance)

- [X] T008 Test: in `tests/test_calibrate.py`, `test_empty_fast_checks_calibrate_and_promote`:
  a config written as `configure(...)` output with `fast_checks = []` added to the
  `acme/widget` entry (fixture `python`); `main('calibrate') == 0`, stdout has
  `-fast_checks = []` and `+fast_checks = ["ruff check ."]` and no
  `edit by hand: repos.0.fast_checks`; then `promote(workspace_root, lambda digest, **kw: True) == 0`
  and `load_config(workspace_root)['repos'][0]['fast_checks'] == ['ruff check .']`, and
  the `.wuwei/calibration.json` snapshot still has the raw
  `fast_checks == ['python3 -m pytest -q', 'ruff check .']`. Expect it to pass only with
  T002 and T006; if it already passes, it is the acceptance guard and stays.

## Phase 4: Measured classification (US2)

- [X] T009 Test: in `tests/test_calibrate.py`, `test_classify_measures_test_runners`
  (parametrized): a fake runner returning `Result(0)` and fake timings `[0.0, 75.0]` gives
  `(False, note)` with `75.0` and `60` in the note; `[0.0, 3.0]` with `Result(0)` gives
  `(True, note)` with `3.0`; `[0.0, 3.0]` with `Result(1, {})` gives `(False, note)` with
  `exit 1`; `Result(2, reason='fast check could not run: TimeoutExpired')` gives
  `(False, note)` with `exit 2`; lint commands never call the runner; the runner is called
  with the checkout path as a string and the command. Expect the measuring branch to be
  missing (assertion on the note fails).
- [X] T010 Implement the measuring branch of `classify` in `cli/wuwei/calibrate.py`
  (`monotonic` imported at module level, `ponytail:` comment on the full-run sample).
  T009 passes.
- [X] T011 Test: in `tests/test_calibrate.py`, `test_calibrate_measure_lists_slow_tests_as_ci_only`
  (the issue's second acceptance): `configure(workspace_root, ('acme/widget', FIXTURES / 'python'))`,
  fake checks port returning `Result(0)`, timings `[0.0, 75.0]`;
  `main('calibrate', '--measure') == 0`; `calibration.md` CI only section has
  `python3 -m pytest -q` with `75.0` and `60`; the proposal has
  `+fast_checks = ["ruff check ."]`; the Next line names `config promote --measure`.
  Second case: `[calibrate]\nfast_check_seconds = 100\n` appended to the config, same
  timings: the proposal has both commands. Expect `unrecognized arguments: --measure`
  (exit 2) and a schema error for `[calibrate]`.
- [X] T012 Implement: `--measure` in `cli/wuwei/commands/calibrate.py` (`register`, pass to
  `survey`, Next line); `"calibrate": {"fast_check_seconds": (int, 60, 1)}` in
  `cli/wuwei/workspace.py` `SCHEMA`; `survey` reads the threshold from config. T011 passes.
- [X] T013 Test: in `tests/test_calibrate.py`, `test_config_promote_measure`: same
  workspace and fake port; `config.promote(SimpleNamespace(measure=True), confirm=...)`
  with timings `[0.0, 75.0]` prints a `CI only, not proposed as a fast check:` line in the
  digested summary and writes `fast_checks = ["ruff check ."]`; with timings `[0.0, 3.0]`
  on a fresh config it writes both commands; `promote(workspace_root, ...)` (bare
  `SimpleNamespace()`) never calls the port. Also `main('config', 'promote', '--measure')`
  is accepted by the parser (it then exits 2 for want of a host terminal, as
  `test_config_promote_through_cli_needs_a_host_terminal` does). Expect the summary
  assertion to fail.
- [X] T014 Implement in `cli/wuwei/commands/config.py`: `--measure` on the `promote`
  subparser, `measure=getattr(args, 'measure', False)` into `survey`, CI only lines in
  `summary`. T013 passes.

## Phase 5: Docs

- [X] T015 Test: in `tests/test_docs.py::test_calibration_is_documented_between_configure_and_plan`,
  add the phrases `--measure`, `calibrate.fast_check_seconds`, `CI only` and
  `repos.fast_checks` to the Calibration section check, and assert the
  `bin/wuwei calibrate` row of `docs/site/reference.md` mentions `--measure`.
  `test_configuration_names_every_config_section` already fails after T012 for the new
  `[calibrate]` section. Expect both to fail.
- [X] T016 Update `docs/site/configuration.md` (Sections table row for `[calibrate]`; the
  Calibration section per plan.md, including exactly what `--measure` runs) and
  `docs/site/reference.md` (calibrate row). T015 and the docs suite pass.

## Phase 6: Finish

- [X] T017 Run `python -m pytest -q`; everything passes. Check every file touched for
  em-dashes, emojis and absolute local paths and remove any.
