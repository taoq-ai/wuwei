# Implementation Plan: fix(calibrate): fill an explicit empty fast_checks, and propose only genuinely fast checks

**Branch**: `328-calibrate-fast-checks` | **Date**: 2026-10-03 | **Spec**: `specs/328-calibrate-fast-checks/spec.md`

## Summary

Two small changes at the spots every caller already routes through:

1. B6: in `calibrate.proposal()`, treat a one-line `fast_checks = []` like the deploy
   lists. `apply()` already replaces such a line in place.
2. B7: the survey classifies each detected fast check candidate (lint and format fast;
   test runners fast only after an opt-in measured passing run under
   `calibrate.fast_check_seconds`). The proposal and the charter proposals use only the
   fast ones; `facts` stay raw so drift and `calibration.json` do not change. The
   measurement goes through the existing `checks` port; no new port, adapter or
   subprocess use in the core.

## Technical Context

Python 3.11+ stdlib only (`time.monotonic`), pytest for tests. Calibrate stays off every
hook path (the steward imports it locally), so there is no hook latency impact.

## Constitution Check

- I stdlib only: yes. II three-state exits: calibrate and promote exit codes unchanged; a
  failed or unrunnable measurement makes the command CI only (not proposed), never clean.
- III one behaviour, one function: classification lives in `calibrate.classify`, called
  only from `calibrate.survey`, which both `calibrate` and `config promote` use.
- IV test first: tasks.md orders a failing test before each change. V ponytail: no new
  port parameter, no new detector, no new config key beyond the threshold the issue names.
- VII security: measurement is opt-in, runs only fixed-table commands (never text copied
  from the repository), through the checks port that already runs `fast_checks`.

## Changes

### `cli/wuwei/calibrate.py`

- `from time import monotonic` (module-level name so tests can monkeypatch
  `calibrate.monotonic` for fake timing).
- `LINT = ('ruff check .', 'black --check .', 'npm run lint', 'make lint')`: the fast
  candidates of the fixed toolchain table. Every other candidate is a test runner
  (`python3 -m pytest -q`, `npm test`, `cargo test`, `go test ./...`, `make test`,
  `make check`).
- `proposal(raw, targets)` (B6): replace the `deploy_lines` list (line 448) with the lines
  of the section at `path` from the existing `_labelled(raw)`, and widen the line 456
  condition to `(path == ('deploy',) or key == 'fast_checks') and table[key] == [] and any(_empty_list(key, l) for l in lines_of_path)`.
  Update the docstring ("deploy lists and `fast_checks` still at a one-line []"). Nothing
  else in `proposal` or `apply` changes.
- New `classify(checkout, commands, runner, seconds, root=None)` returning
  `{command: (fast, note)}` in the order of `commands`:
  - `command in LINT`: `(True, 'lint or format')`.
  - `runner is None`: `(False, 'test runner, unmeasured; run bin/wuwei calibrate --measure')`.
  - otherwise: `start = monotonic()`, `result = runner.run(str(checkout), command, root=root)`,
    `took = monotonic() - start`; fast when `isinstance(result, registry.Result)` and
    `result.exit == 0` and `took <= seconds`. Note: `measured {took:.1f} s, threshold {seconds} s`
    plus `, exit {result.exit}` (and the result's reason when it has one) when not 0.
  - `ponytail:` comment: one full timed run capped by the checks port's 300 s timeout;
    add a port timeout or a collect-only command if `--measure` proves too slow.
- `survey(root, config, selected, *, style=True, measure=False)`: load
  `runner = registry.load('checks', config) if measure else None` (never loaded without
  `--measure`), and for each result set
  `result['checks'] = classify(result['checkout'], result['facts']['fast_checks'], runner, config['calibrate']['fast_check_seconds'], root)`.
  `result['facts']` is not modified.
- New `proposed(result)`: `{**result['facts'], 'fast_checks': [c for c, (fast, _) in result['checks'].items() if fast]}`.
- `propose(raw, results, settings=())` line 586: pass `proposed(r)` instead of
  `r['facts']`.
- `report(results, ...)`:
  - Toolchain rows of kind `fast_check` are labelled with the classification:
    `fast check (<note>)` or `CI only (<note>)`, from `result['checks'][value]`.
  - After the proposed changes (and the hand edits), a `## CI only (not proposed as fast checks)`
    section, present only when some result has a CI-only command:
    `- <repo name>: <command> (<note>)`. This is the issue's `[repos.ci_only]` note.

### `cli/wuwei/commands/calibrate.py`

- `register`: `parser.add_argument('--measure', action='store_true', help='time test runners through the checks port (runs repository commands)')`.
- `run`: `calibrate.survey(root, config, selected, measure=args.measure)`; pass
  `calibrate.proposed(result)` to `charter_proposals` instead of `result['facts']`; after
  the hand-edit lines print `CI only, not proposed as a fast check: <repo>: <command> (<note>)`
  per CI-only command; the Next line says `bin/wuwei config promote --measure` when
  `args.measure`. Exit codes unchanged.

### `cli/wuwei/commands/config.py`

- `register`: the `promote` subparser gets the same `--measure` flag.
- `promote`: `calibrate.survey(..., style=False, measure=getattr(args, 'measure', False))`
  (existing in-process callers pass a bare `SimpleNamespace()`); append the same
  `CI only, not proposed as a fast check: ...` lines to `summary` before the snapshot block,
  so the digest covers them. The snapshot (`drift_facts(r['facts'])`) is unchanged.

### `cli/wuwei/workspace.py`

- `SCHEMA`: add `"calibrate": {"fast_check_seconds": (int, 60, 1)}`.

### Docs

- `docs/site/configuration.md`:
  - Sections table: add `[calibrate]` pointing to [Calibration](#calibration).
  - Calibration section: the additive-proposal sentence (line 241) also names
    `repos.fast_checks` still at a one-line `[]`; a paragraph on the classification (the
    four lint and format commands are fast; test runners are CI only unless measured),
    `--measure` on `calibrate` and `config promote` (it runs each detected test runner
    once in the configured checkout through the checks port, the same runner as
    `wuwei fast-checks`, capped at 300 s, and may leave tool caches there), the
    `calibrate.fast_check_seconds` key (default 60), and the CI only section of
    `calibration.md`.
- `docs/site/reference.md`: the `bin/wuwei calibrate` row mentions `--measure`.

## Must not change

- `toolchain()` and the detector table rows (`tests/test_calibrate.py` DETECTORS), the
  `fast_check` finding kind, `profile()` facts, `drift_facts`, `DRIFT`, `drift()`, the
  `calibration.json` snapshot shape.
- `apply()`, `settle()`, profile import and interview settings; the checks port signature
  (`registry.PARAMETERS['checks']`, `adapters/checks/*.py`) and its 300 s timeout.
- A non-empty owner `fast_checks` stays a hand edit; a multi-line or inline-table `[]`
  stays a hand edit.
- No repository command runs without `--measure`; `calibrate` without it leaves the
  checkout unchanged (`test_calibrate_this_repository` keeps asserting a clean
  `git status`).
- No new event kind, state key or day file.

## Existing tests that change

- `tests/test_calibrate.py::test_calibrate_this_repository` asserts
  `+fast_checks = ["python3 -m pytest -q"]` in the output. After this change the
  unmeasured pytest is CI only and this repository has no lint candidate, so the test
  asserts instead that `+fast_checks` is absent and the report lists
  `python3 -m pytest -q` under CI only with "unmeasured". This is the intended behaviour
  change of B7, not a regression.

## Project Structure

Files touched: `cli/wuwei/calibrate.py`, `cli/wuwei/commands/calibrate.py`,
`cli/wuwei/commands/config.py`, `cli/wuwei/workspace.py`, `tests/test_calibrate.py`,
`tests/test_docs.py`, `docs/site/configuration.md`, `docs/site/reference.md`. No new
files outside `specs/`.
