# Feature Specification: First-day docs after the fix wave

**Feature Branch**: `340-docs-first-day`

**Created**: 2026-10-03

**Status**: Draft

**Input**: Issue #340, docs: first-day docs after the fix wave: setup, doctor, posture, MCP
warn-by-default, troubleshooting. Builds on #323 to #331 and #339 (all on main at 9568967,
released as 0.12.0) and on the previous sweep #294 and the README lead #314. Docs only.

## Current state (read on main, 0.12.0)

Each fix-wave item already documented its own command, so most of the issue's page list is
done. `python -m pytest -q tests/test_docs.py` passes (42 tests). What is still missing:

- `README.md:91-114` (Quick start): `setup --shadow` then `/wuwei plan`; `bin/wuwei doctor`
  is not there. The issue wants install, `setup --shadow`, `doctor`, `/wuwei plan`.
- `README.md:28-39` (What ships today): no bullet for setup, doctor or the security posture,
  so those areas have no link from the README.
- `README.md:116-126` (Limits): does not say that a first week in the observe posture
  (`setup --shadow`) is the suggested start.
- `docs/site/index.md:40-54` (Start here): same gap as the README quick start, no doctor.
- `docs/site/daily.md:63-65`: `bin/wuwei doctor` sits in section 2 (Configure), after the
  goals and min_reviewers advice, not straight after setup in section 1.
- `docs/site/daily.md:73-75` and `:184-185`: tell the owner to set `security.posture`,
  `owner.timezone`, `metrics.band_margin` and `sessions.rotate_after` by editing
  `config.toml`. Each is a one-line assignment that `bin/wuwei config set` writes after a
  digest (checked against the shipped template: every one reaches the digest prompt).
- `docs/site/configuration.md:9`: "Edit it in the workspace root" with no mention of
  `config set` or `config add-repo`.
- `docs/site/recovery.md:14-16`: opens with `bin/wuwei doctor` but has no troubleshooting
  entries. The owner's 0.11.0 trial (nine findings, B1 to B9) has no page that maps a
  symptom to the command that fixes or explains it.
- `docs/site/security.md:50-63`: the posture table and floors match
  `cli/wuwei/workspace.py:38-47` (`AREAS`, `POSTURES`, `FLOORS`) and the MCP default
  (`scanner.mcp.block`, `workspace.py:55-56`) today, but no test pins them, so a code change
  can leave the page wrong.

Already done and left alone: `reference.md` lists `setup`, `doctor` and `config`
(`set`, `add-repo`) and has `## Doctor` and `## Security posture`; `configuration.md` covers
`[security]`, `[security.areas]`, `scanner.mcp.block`, `scanner.mcp.timeout_seconds`,
`calibrate.fast_check_seconds` and the "CI only" calibration note; `concepts.md` has
`## Security posture`; `docs/integrity.md` names `.in_use`; `remote.md` is not touched by
setup.

## User Scenarios & Testing

### User Story 1 - The first day reads as one path (Priority: P1)

A new owner reads the README or the docs index and runs four things in order: install,
`setup --shadow`, `doctor`, `/wuwei plan`. Each shipped area in "What ships today" links to
its page, including setup, doctor and the posture.

**Why this priority**: it is the first thing every new owner reads, and today it skips the
command that finds first-day problems.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k "first_day or lead_and_limits"`.

**Acceptance Scenarios**:

1. **Given** the README, **When** the Quick start section is read, **Then** it names
   `setup --shadow`, `bin/wuwei doctor` and `/wuwei plan` in that order, and still names
   `config set`.
2. **Given** the docs index, **When** Start here is read, **Then** the same three steps
   appear in the same order.
3. **Given** the README, **When** What ships today is read, **Then** setup, doctor and the
   security posture each have a bullet with a link to their page, next to the existing
   links.
4. **Given** the README Limits section, **Then** it suggests `setup --shadow` (the observe
   posture) for a first week and keeps every phrase the #314 test pins.

---

### User Story 2 - Troubleshooting maps each trial failure to its fix (Priority: P1)

An owner hits one of the shapes the 0.11.0 trial found. The recovery page has a
troubleshooting section that opens with `bin/wuwei doctor` and has one entry per finding,
each naming what the owner sees and the command that fixes or explains it.

**Why this priority**: these are the real first-day failures; without the mapping each
one costs the owner round trips.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k troubleshooting`.

**Acceptance Scenarios**:

1. **Given** `docs/site/recovery.md`, **Then** a `## Troubleshooting` section exists, its
   first command is `bin/wuwei doctor`, and it has exactly nine `###` entries.
2. **Given** each of the nine trial findings, **Then** one entry names its symptom and its
   command:

   | Finding | Symptom named | Command named |
   |---|---|---|
   | B1 | `.in_use` process markers | `bin/wuwei integrity check` |
   | B2 | an MCP server `not attached (unapproved)` or unmeasured | `bin/wuwei mcp decide proceed-unmeasured` |
   | B3 | `config.toml` does not load | `bin/wuwei config check` |
   | B4 | `delete that line before using [[repos]] tables` | `bin/wuwei init --upgrade` |
   | B5 | a value to change without a hand edit | `bin/wuwei config set` |
   | B6 | `fast_checks = []` left empty | `bin/wuwei config promote` |
   | B7 | a test suite proposed as a fast check | `bin/wuwei calibrate --measure` |
   | B8 | `none visible (404: unprotected or no admin)` | `bin/wuwei config check` |
   | B9 | a read-only shell command refused | `bin/wuwei why last refusal` |

3. **Given** the existing recovery test, **Then** it still passes unchanged.

---

### User Story 3 - The daily path and config page use config set (Priority: P2)

The daily path starts with setup and doctor, and wherever it tells the owner to change a
single value it gives the `bin/wuwei config set` line, not a hand edit.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k doctor_is_the_first_stop`.

**Acceptance Scenarios**:

1. **Given** `daily.md`, **Then** section 1 names `bin/wuwei doctor` after `setup --shadow`.
2. **Given** `daily.md`, **Then** switching from observe to guarded is
   `bin/wuwei config set security.posture '"guarded"'`, and the Long sessions keys are set
   with `bin/wuwei config set`; the phrase "in `config.toml`" for the posture switch is gone.
3. **Given** `configuration.md`, **Then** its opening paragraph names `bin/wuwei config set`
   and `bin/wuwei config add-repo` as the way to change one value, with a hand edit left
   for what they refuse.

---

### User Story 4 - The posture table cannot drift from the code (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_docs.py -k posture_table`.

**Acceptance Scenarios**:

1. **Given** `security.md`, **Then** the posture table has one row per area in
   `workspace.AREAS` and its observe, guarded and strict cells equal `workspace.POSTURES`.
2. **Then** the header marks the schema default posture (`guarded`) as `(default)`.
3. **Then** each floor in `workspace.FLOORS` is stated (`records` always blocks), and the
   MCP floor names the schema default of `scanner.mcp.block` (`critical`).
4. **Then** the MCP paragraph states the default (only a critical finding or a check that
   could not run blocks) and what the check never starts (an unapproved project server, an
   unpinned `uvx`, `npx` or `pipx run` launcher).

### Edge Cases

- The recovery test (`test_daily_path_and_recovery_pages`) reads the text after the first
  mention of `state transition`, `runtime dispatch`, `runtime continue` and
  `integrity reconfirm` up to the next `## ` heading and needs the word "recovery" there. A
  troubleshooting section placed above those sections that names one of them must itself
  contain "recovery".
- The hero: its stations did not change (Calibrate and the interview still describe what
  setup runs), so the generator, both SVGs and the alt text stay as they are. The PR says so.
- Nothing spec-only is presented as shipped: cruise mode keeps "not built".

## Requirements

### Functional Requirements

- **FR-001**: README Quick start and index Start here MUST list `setup --shadow`,
  `bin/wuwei doctor` and `/wuwei plan` in that order.
- **FR-002**: README What ships today MUST gain bullets for setup, doctor and the security
  posture (with the MCP gate's warn default), linking `docs/site/daily.md#2-configure`,
  `docs/site/reference.md#doctor` and `docs/site/security.md#security-posture`.
- **FR-003**: README Limits MUST suggest a first week in the observe posture with
  `setup --shadow`.
- **FR-004**: `recovery.md` MUST have a `## Troubleshooting` section opening with
  `bin/wuwei doctor`, with nine `###` entries per the table above, and no client or
  repository name from the trial and no absolute local path.
- **FR-005**: `daily.md` MUST name `bin/wuwei doctor` in section 1 and use
  `bin/wuwei config set` for the posture switch and the Long sessions keys.
- **FR-006**: `configuration.md` opening paragraph MUST name `config set` and `config add-repo`.
- **FR-007**: a test MUST pin the `security.md` posture table, its default, its floors and
  the MCP default to `workspace.AREAS`, `POSTURES`, `FLOORS` and `SCHEMA`.
- **FR-008**: no existing test is weakened or removed; no workflow file, code or hero file
  changes.

## Success Criteria

- **SC-001**: `python -m pytest -q` passes with the new and extended tests.
- **SC-002**: each of the nine trial findings has one troubleshooting entry with its command.
- **SC-003**: changing any cell of `workspace.POSTURES` without the docs fails a test.

## Assumptions

- Docs only. The issue's "start after the fix wave" condition holds: #323 to #331 and #339
  are on main.
- `[repos.ci_only]` in the issue is the "CI only" note in `calibration.md`, the calibrate
  output and the promote digest (spec 328), not a config table. `configuration.md#calibration`
  already documents it and a test pins "CI only"; no change.
- `reference.md`, `concepts.md`, `docs/integrity.md` and `remote.md` already carry what the
  issue asks (by #327, #331, #332, #339); they are left alone apart from the humanizer read.
- The troubleshooting section goes in `recovery.md`, not a new page: the page already opens
  with doctor and doctor's `install` row links to `recovery.md#integrity-reconfirm`.
- The posture-table test passes on today's text: it is a pin. The builder sees it bite by
  changing one cell locally, then restores it.
- Doctor still prints hand-edit fix lines for `security.posture` and `repos.N.identity`
  (`cli/wuwei/commands/doctor.py:262-271`, `:322`). That is code, out of scope; noted as
  deferred.
- The relayed owner reply in this run concerns the latency CI job; this issue changes no
  workflow and no latency assertion, and the latency phrases `test_docs.py` pins stay.
