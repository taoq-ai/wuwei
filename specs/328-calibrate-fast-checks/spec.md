# Feature Specification: fix(calibrate): fill an explicit empty fast_checks, and propose only genuinely fast checks

**Feature Branch**: `328-calibrate-fast-checks`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #328 (trial findings B6 and B7 of the owner's first run of v0.11.0). Builds on
#278 (calibrate) and #313 (profiles). Docs: `docs/site/configuration.md#calibration`.

## Root cause (read on main, 69453ed)

Reproduced read-only with a scratch script against `tests/fixtures/calibrate/python`
(facts `fast_checks = ['python3 -m pytest -q', 'ruff check .']`) and a config whose
`[[repos]]` entry has `fast_checks = []`:
`calibrate.proposal(raw, [(0, facts)])` returns `additions == []` and
`edits == [('repos.0.fast_checks', [], ['python3 -m pytest -q', 'ruff check .'])]`, so
`calibrate` prints "Config differs; edit by hand: repos.0.fast_checks" and
`config promote` never fills it.

- B6, empty list treated as an owner value: `cli/wuwei/calibrate.py:456` replaces a
  one-line `[]` only when `path == ('deploy',)`. For `('repos', i)` the key is present, so
  the list branch at `cli/wuwei/calibrate.py:458` (`not set(value) <= set(table[key])`)
  turns `fast_checks = []` into a hand edit. `apply()` already replaces a one-line
  assignment in place (`cli/wuwei/calibrate.py:480-484`), so only the selection is wrong.
- B7, every detected command is a "fast check": `toolchain()`
  (`cli/wuwei/calibrate.py:90-128`) emits test runners (`python3 -m pytest -q`, `npm test`,
  `cargo test`, `go test ./...`, `make test`, `make check`) with the same `fast_check` kind as
  linters (`ruff check .`, `black --check .`, `npm run lint`, `make lint`), and
  `proposal()` (`cli/wuwei/calibrate.py:434-438`) and `charter_proposals()`
  (`cli/wuwei/calibrate.py:521-522`) take `facts['fast_checks']` verbatim. Nothing
  classifies or measures a candidate. Fast checks gate every push (design 4.1, hook table:
  "push before the fast checks passed"), so a full suite there makes each push wait for CI-scale work.
- Constraint found while tracing: `config promote` recomputes the survey itself
  (`cli/wuwei/commands/config.py:126`) and records `drift_facts(r['facts'])` in
  `.wuwei/calibration.json` (`:134`); the steward's `calibrate.drift()`
  (`cli/wuwei/calibrate.py:657-684`) re-profiles without measuring. So the measured
  classification must not change `facts`, or every repository with a CI-only command
  would report drift daily.

## User Scenarios & Testing

### User Story 1 - An explicit empty fast_checks gets filled (Priority: P1)

The owner's repository entry has `fast_checks = []` (as written in the trial). Calibration
proposes the detected fast checks in place of the empty list, and `config promote` writes
them, without a hand edit.

**Independent Test**: `python -m pytest -q tests/test_calibrate.py -k empty_fast_checks`.

**Acceptance Scenarios**:

1. Given a repository entry with a one-line `fast_checks = []` and a checkout with a
   detected lint command, when `calibrate` runs, then its diff replaces the line with the
   proposed list, and "edit by hand: repos.0.fast_checks" is not printed.
2. Given the same config, when `config promote` is confirmed, then `config.toml` has the
   proposed `fast_checks` for that entry, every other value is unchanged, and the result
   validates.
3. Given `fast_checks = ["make test"]` (a non-empty owner value), then it stays a hand edit,
   as today.

### User Story 2 - Only genuinely fast commands are proposed as fast checks (Priority: P1)

Lint, format and type check commands are proposed as fast checks. A test runner is proposed
only when the owner opted in to a measured run (`calibrate --measure`) and that run passed
within `calibrate.fast_check_seconds` (default 60). Otherwise it is listed as CI only, with
the reason or the measured time, and not proposed.

**Independent Test**: `python -m pytest -q tests/test_calibrate.py -k "ci_only or measure"`.

**Acceptance Scenarios**:

1. Given a checkout with `python3 -m pytest -q` and `ruff check .` candidates and a fake
   timing of 75 seconds for the test run, when `calibrate --measure` runs, then the test
   command is listed under CI only in `calibration.md` with the measured number and the
   threshold, the proposal has `fast_checks = ["ruff check ."]`, and the builder charter
   proposal names only `ruff check .`.
2. Given the same checkout and a fake timing of 3 seconds with a passing run, then both
   commands are proposed as fast checks and the report shows the measurement.
3. Given no `--measure`, then no repository command runs (the checks port is never
   called), the test runner is listed as CI only with "unmeasured", and lint stays in
   `fast_checks`.
4. Given `config promote --measure`, then promote measures the same way before printing
   its digest, and the digested summary lists each CI-only command with its note.

### Edge Cases

- A measured run that fails (exit 1) or cannot run (exit 2, including the checks port's
  own 300 second timeout) is CI only, with the exit and elapsed time in the note.
- All candidates CI only: nothing is proposed for `fast_checks`; an existing
  `fast_checks = []` stays.
- `make check` is ambiguous (often runs tests), so it is treated as a test runner.
- Drift: `.wuwei/calibration.json` and the steward's drift check keep comparing the full
  detected candidate list, so a CI-only classification never shows as drift.
- A candidate from a file with instruction-like text is dropped before classification, as
  today; measurement only ever runs commands from the fixed command table.

## Requirements

### Functional Requirements

- **FR-001**: `proposal()` treats a present `repos.fast_checks` whose value is `[]` and whose
  section holds a one-line `fast_checks = []` assignment like the deploy lists: an addition
  that `apply()` replaces in place. Any other present value keeps today's rules.
- **FR-002**: Every fast check candidate is classified. `ruff check .`, `black --check .`,
  `npm run lint` and `make lint` are fast (lint or format). Every other candidate is a test
  runner.
- **FR-003**: Without `--measure`, a test runner is CI only with the note "unmeasured" and
  the command to measure. No repository command runs.
- **FR-004**: With `--measure` (on `calibrate` and on `config promote`), each test runner
  candidate is run once through the existing checks port in its checkout and timed. It is
  fast only when the run exits 0 and took at most `calibrate.fast_check_seconds` seconds;
  otherwise CI only. The note states the elapsed seconds, the threshold, and the exit when
  not 0.
- **FR-005**: The proposal and the builder and quality charter proposals use only the fast
  candidates. `facts`, `drift_facts`, `calibration.json` and `drift()` are unchanged.
- **FR-006**: `calibration.md` shows each candidate's classification and measurement in the
  Toolchain section, and lists CI-only commands per repository in a "CI only" section next
  to the proposal. `calibrate` prints one line per CI-only command; `config promote`
  includes the same lines in its digested summary.
- **FR-007**: New config key `calibrate.fast_check_seconds`, integer, default 60, minimum 1,
  documented in `docs/site/configuration.md` with what `--measure` runs.

### Key Entities

- **Classification**: per repository, `{command: (fast, note)}` over the detected
  candidates, computed by the survey; never stored in workspace state.

## Success Criteria

- **SC-001**: The trial config shape (`fast_checks = []`) yields a filled `fast_checks` after
  one `calibrate` and one `config promote`, with no hand edit.
- **SC-002**: No test runner reaches a proposed `fast_checks` without a passing measured run
  under the threshold; no repository command runs without `--measure`.
- **SC-003**: The full suite passes, with the existing drift and profile tests unchanged.

## Assumptions

- The issue says the template example and the docs' minimal entry include
  `fast_checks = []`; on main the template has a commented `fast_checks = [...]` example
  and the docs' entry a non-empty list. The trial config held a one-line
  `fast_checks = []`, and that is the case fixed. Template and docs examples are not
  changed here.
- "Collection count or a timing sample": a timing sample of one full run through the
  existing checks port is used; a per-runner collection command (`pytest --collect-only`
  and so on) is not added. The checks port keeps its 300 second timeout and signature; a
  slow suite costs up to that per command on an opt-in `--measure`.
- `[repos.ci_only]` is a note in `calibration.md`, the `calibrate` output and the promote
  digest, not a new config key: nothing reads such a key.
- A measured test run that fails or cannot run is CI only rather than unmeasured; it never
  makes `calibrate` exit 2, because the proposal stays on the safe side (not proposed).
  The note says why.
- `config promote --measure` repeats the measurement rather than reading the one
  `calibrate --measure` made, so promote applies exactly what its own digest shows and no
  seat-writable file decides what is proposed.
- No type check command is detected today; the classification lists only the commands the
  detector emits. A detector for type checkers is out of scope.
- `--measure` runs repository code (a test runner, `npm test` or a `make` target) in the
  configured checkout with the checks port's environment; it may write tool caches there.
