# Feature Specification: --shadow means posture observe, and guards.mode retires

**Feature Branch**: `355-shadow-observe`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #355, fix(setup). Builds on #308 (shadow mode), #331 and #345 (posture
profiles, `setup --shadow` writes observe), #342 (doctor and `doctor --fix`), #343
(setup), #353 (config transition, same `init --upgrade` code; merged first). Evidence:
the owner's question of 2026-10-03 and the trial config that holds both keys.

## Root cause (reproduced read-only)

Reproduced in a scratch workspace outside the repository against this branch: `init .`
from the shipped template, then `[guards]` gains `mode = "shadow"` and
`shadow_since = "2026-09-29"` next to the template's `security.posture = "guarded"`
(the trial config's shape).

```text
config check -> exit 0
  Posture: observe
  ...
  guards.mode = "shadow" is deprecated: set security.posture = "observe"; ...
init --upgrade --dry-run -> exit 0
  No workspace changes needed
doctor
  ok   template: current
  ok   posture: observe, 3 days left
```

- `cli/wuwei/workspace.py:555-560`, `posture`: `guards.mode = "shadow"` silently
  overrides `security.posture`; nothing returns which key decided, so no surface can say.
- `cli/wuwei/commands/config.py:78-79` prints `Posture: observe` while the file says
  `guarded`; the deprecation note is a separate line at `config.py:92-94`, after the area
  table and the `scanner.mcp.block` line, so the two values read side by side.
- `cli/wuwei/commands/doctor.py:318-328`: the posture row shows the effective name with
  no source and `ok` status; following its nudge fix (`set security.posture =
  "guarded"`) would change nothing, because the alias still wins.
- `cli/wuwei/commands/init.py:183-214`, `_migrated_config`, only adds keys the template
  has and the config lacks. Nothing rewrites `guards.mode`, so `init --upgrade` reports
  no changes, the doctor `template` row is `current`, and `doctor --fix` (which applies
  `init-upgrade` from that row) has nothing to do.
- `templates/workspace/config.toml:227-236`: `guards.mode` is already gone, but
  `security.posture` is the second key under `[security]` and its one comment does not
  say what each profile does.

## User Scenarios & Testing

### User Story 1 - Upgrade and doctor --fix retire guards.mode (Priority: P1)

The owner runs `doctor`, sees the posture comes from a deprecated key, runs
`doctor --fix` (or `init --upgrade`), and the file then says what runs: `security.posture
= "observe"`, no `guards.mode`, `shadow_since` and `shadow_days` unchanged.

**Independent Test**: in process, `init.run` creates a workspace in `tmp_path`, the test
edits `config.toml`, then `init.run(... upgrade=True, dry_run=...)`; the file is read
back with `tomllib`.

**Acceptance Scenarios**:

1. Given `security.posture = "guarded"`, `guards.mode = "shadow"` and
   `guards.shadow_since = "2026-09-29"`, when `init --upgrade --dry-run` runs, then stdout
   holds exactly one line `Would upgrade config.toml: guards.mode = "shadow" becomes
   security.posture = "observe"` and the file is unchanged.
2. Given the same config, when `init --upgrade` runs, then the file has
   `security.posture = "observe"`, no `guards.mode`, `shadow_since = "2026-09-29"` and the
   same `shadow_days`; every other value and comment is unchanged; a second
   `init --upgrade` prints `No workspace changes needed`.
3. Given `guards.mode = "enforce"`, when `init --upgrade` runs, then the line is removed,
   `security.posture` is unchanged, and the dry run showed one line `Would upgrade
   config.toml: remove guards.mode = "enforce" (the default)`.
4. Given `guards.mode = "shadow"` with no `[security]` table, when `init --upgrade` runs,
   then the result has `security.posture = "observe"` (not the template's `guarded`).
5. Given `security.posture = "strict"` and `guards.mode = "shadow"`, then the result is
   `observe`: the rewrite keeps the posture that ran before it.
6. Given the trial config, when `doctor` runs, then its `template` row is `warn` with
   `apply = init-upgrade` and the rewrite line as detail, so `doctor --fix` applies it.

### User Story 2 - One posture line that names its source (Priority: P1)

`config check` and `doctor` show one effective posture and the key it comes from, never
two values side by side.

**Independent Test**: `tests/test_posture.py::checked` for `config check`;
`tests/test_doctor.py::ws` with `doctor.diagnose()` for the row.

**Acceptance Scenarios**:

1. Given `security.posture = "observe"`, then `config check` prints
   `Posture: observe (from security.posture)` and no line containing `deprecated`.
2. Given `security.posture = "guarded"` and `guards.mode = "shadow"`, then `config check`
   prints `Posture: observe (from guards.mode = "shadow", deprecated; run doctor --fix)`,
   that is the only line containing `deprecated`, no line contains `guarded`, and the
   exit code equals that of the same config without the key.
3. Given that config, when `doctor` runs, then the `posture` row is `warn`, value
   `observe (from guards.mode = "shadow", deprecated; run doctor --fix)`, fix
   `wuwei init --upgrade`, `apply = init-upgrade`.
4. Given `security.posture = "strict"`, the row is `ok`, value
   `strict (from security.posture)`; given observe with days left, `observe (from
   security.posture), 4 days left`; given observe past `shadow_days`, `warn` with the
   value starting `observe (from security.posture)` and the existing nudge text and fix.

### User Story 3 - setup --shadow and the template (Priority: P2)

**Independent Test**: `tests/test_setup.py::test_one_command_three_repositories`; the
template read as text and with `tomllib`.

**Acceptance Scenarios**:

1. Given `setup --shadow` on a fresh directory, then the config has
   `security.posture = "observe"`, `shadow_since` today, and no `guards.mode` key in the
   file (extends the #345 test).
2. Given the template, then `guards.mode` and a `mode =` line do not appear; the first key
   under `[security]` is `posture`, preceded by one comment line for each of `observe`,
   `guarded` and `strict`.
3. Given `init --shadow` and `init --posture strict` on a new directory, then the written
   `security.posture` is `observe` and `strict` (the replace still finds the key after the
   reorder).

### User Story 4 - Docs say --shadow is observe (Priority: P3)

`docs/site/configuration.md` and `docs/site/security.md` say `--shadow` sets `observe` for
`guards.shadow_days` days, then one nudge asks to switch to `guarded`; `guards.mode` is
described only as retired and rewritten by `init --upgrade` and `doctor --fix`. "shadow"
remains only as the flag name, the `shadow report` command, the week's keys and the
`## Shadow` report section.

### Edge Cases

- `guards.mode` written in a layout the line edit cannot reach (a quoted key
  `"mode" = "shadow"`, an inline `guards` table): the post-edit check fails, `init --upgrade` exits 2 with
  `cannot safely retire guards.mode in this TOML layout; set security.posture = "observe"
  and delete guards.mode` and writes nothing.
- `guards.mode = "shadow"` with `shadow_since = ""`: rewritten as usual; `shadow_since`
  stays empty (no nudge), as before the rewrite.
- `security.posture` already `observe` with `guards.mode = "shadow"`: only the `mode`
  line goes; the dry-run line is the same.
- A config with no `guards.mode`: no line, no change, nothing printed for it.
- `setup --shadow` on an existing workspace whose alias already makes the posture observe
  proposes nothing for the posture (as today); its closing `config check` prints the
  deprecated source line pointing at `doctor --fix`.

## Requirements

- **FR-001**: `init --upgrade` (and so `doctor --fix` via `init-upgrade`) removes
  `guards.mode`; when its value is `"shadow"` it also sets `security.posture = "observe"`.
  `shadow_since`, `shadow_days` and every other value and comment are kept. The dry run
  prints one line per rewrite. The effective posture before and after is the same.
- **FR-002**: The rewrite is verified by parsing the result; any other difference from
  the expected values refuses the upgrade (exit 2, nothing written).
- **FR-003**: One helper says where the effective posture comes from; `config check` and
  the `doctor` posture row both use it. `config check` drops its separate deprecation
  line.
- **FR-004**: The `doctor` posture row for the deprecated key is `warn` with fix
  `wuwei init --upgrade` and `apply = init-upgrade`.
- **FR-005**: The template's `[security]` table starts with `posture`, preceded by one
  comment per profile; `guards.mode` is absent.
- **FR-006**: Docs as in User Story 4.

## Success Criteria

- SC-001: After `doctor --fix` or `init --upgrade`, the trial config has one posture key
  and it states the posture that runs.
- SC-002: Neither `config check` nor `doctor` ever prints two posture values for one
  config.

## Assumptions

- `guards.mode` stays in `workspace.SCHEMA` with its alias meaning: a config not yet
  upgraded must keep loading and keep the posture it ran with. Removing it from the
  schema would make it an unknown key that `strict` refuses (#353). "Retire" means out of
  the template, out of the docs as a setting, and rewritten on upgrade.
- `setup` code does not change: #345 already writes observe on a fresh `setup --shadow`
  and proposes it on an existing workspace whose effective posture is not observe; the
  existing-workspace alias case is repaired by `doctor --fix`, which the posture line
  names. The issue's Acceptance asks of setup only the fresh-directory case.
- The rewrite runs after the template migration, so a config lacking `[security]` or its
  `posture` line first gets the template's line and then the rewritten value, and the
  dry run may show both an `add security.posture` line and the rewrite line.
- `config check` keeps the header form `Posture: <name> (from <source>)`; the issue's
  lowercase `posture: ...` is the doctor row as rendered (`posture: <value>`).
- The deprecated alias stays a report, not a finding, in `config check` (exit code
  unchanged), as #331 made it; `doctor` reports it as `warn` because it has a fix.
- `docs/site/concepts.md` and the design spec keep their one sentence on the alias; the
  issue names configuration.md and security.md, and the design spec is amended only by
  its owner.
- `config set guards.mode` and profile review are unchanged (profiles already refuse
  `guards`).

## Deferred

- None.
