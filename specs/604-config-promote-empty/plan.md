# Implementation Plan: promote keeps owner-set keys, an answer promotes only its keys, and an empty list is written empty

**Branch**: `604-config-promote-empty` | **Date**: 2026-10-09 | **Spec**: `spec.md`

## Summary

Small changes at the shared spots the two defects route through (orchestrator override: no
new state file):

1. `config promote` drops a stored answer's setting when its key is present in
   `config.toml` with a value other than its shipped default and `--keys` does not name it, and lists it with
   the `--keys` command. One function next to `calibrate.settle` decides, reusing `settle`.
2. `config promote --keys` limits a promote to named keys, without the repository survey or
   the calibration snapshot; `calibrate --answer` prints that command with its own keys.
3. `setup.merged`, the one function `config set` (host terminal and `--from-card`) routes a
   value through, writes `[]` as given instead of adding nothing to the effective list.

Root causes with file and line: `spec.md`, Root cause.

## Technical Context

Stdlib-only Python 3.11+ runtime; pytest dev-only. Tests run in-process (`main([...])`,
`command.promote(...)`) with the existing fixtures: `root` and `offline` in
`tests/test_interview.py`, `workspace`, `Confirm` and `config_set` in `tests/test_setup.py`,
`ws` in `tests/test_doctor.py`, `world` and `Rules` in `tests/test_invariants.py`.

## Constitution Check

- Test first per behaviour. Pass.
- Stdlib only. Pass.
- Exits unchanged (0, 1, 2). Pass.
- #530: no guard, posture or refusal changes; skipping a present key is not a refusal. Pass.
- #551: every Next line and skip line is an exact command. Pass.
- Rule change gets its invariant: a 9.2 row and `tests/test_invariants.py`. Pass.
- Ponytail: no new module, file, event kind or state key; one function, one argparse
  option, one condition. Pass.

## Changes

### 1. The skip rule (FR-001, FR-002)

`cli/wuwei/calibrate.py`, after `settle`: `kept(raw, settings)` returns
`(settings to apply, [(dotted key, current value)] skipped)`: a setting is skipped when its
key is present in `raw` with a value other than its schema default
(`workspace._default(configtext.declared(...))`) and `settle(raw, [setting])` would change it.

`cli/wuwei/commands/config.py`, `proposal`: keyword `keys=None`. `None` (setup) keeps
today's behaviour. A non-empty tuple keeps only the profile and answer settings whose dotted
key is listed and names the missing ones. An empty tuple (promote without `--keys`) runs
`calibrate.kept` on the answer settings, after the profile filter. Summary lines
`Skipped ...` and `Not in today's answers: ...` after the hand-edit lines; the
approved-calibration block only when `keys` is empty or `None`.

### 2. `config promote --keys` (FR-003)

`register`: `--measure` and `--keys` (`nargs='+'`, `metavar='KEY'`) in one mutually
exclusive group. `promote`: `keys = getattr(args, 'keys', None)`; without keys the repos
check and survey as today and `proposal(..., keys=())`; with keys `results = []`,
`proposal(..., keys=tuple(keys))`, `No config.toml changes` returns 0 without asking, a named key no answer sets
returns 1 with nothing written, and
`offer` gets no snapshot.

### 3. The Next line names the answer's keys (FR-004)

`cli/wuwei/commands/calibrate.py`, `_interview`: replace `pending` with `keys` (dotted keys
of `interview.settings({qid: answer}, config)` for each answer the card path did not write)
and `charters` (a workspace answer with a role or voice effect). Print
`Next: run bin/wuwei config promote --keys <keys> in a host terminal for these config keys`
plus `, then bin/wuwei promote for the charter and voice proposals.` when `charters`, else
`.`; only the charter line when no keys; nothing when neither.

### 4. An empty list is written empty (FR-005)

`cli/wuwei/commands/setup.py`, `merged`: `and value` on the list condition (`#604`).

### 5. Invariant row (FR-006)

Design 9.2 row I28 and `i28` in `tests/test_invariants.py`: an autonomy answer recorded,
`autonomy.mode = "supervised"` present, `config promote` keeps it and lists it,
`config promote --keys autonomy.mode` applies `autonomous`. `BROKEN` entry replaces
`calibrate.kept` with one that keeps every setting.

### 6. Docs (FR-007)

`docs/site/configuration.md` where `config set` and `config promote` are described.

## What must not change

- The #492 additive behaviour of `config set` for a non-empty list and for named-entry
  tables; `--replace`; `deploy.*` lists only grow.
- `setup`'s proposal and digest; repository calibration additions; `calibrate.settle`,
  `calibrate.apply`, `configtext`.
- The card write in `_interview`, the allowlist path, `interview.json`.
- `setup._from_card` and the decision card path (#600 works there).
- Doctor's docs row and its printed fix text.

## Verification

Run only the touched files with the pipeline interpreter:
`python -m pytest -q tests/test_interview.py tests/test_setup.py tests/test_doctor.py
tests/test_calibrate.py tests/test_config_writer.py tests/test_invariants.py`. CI runs the
full suite.
