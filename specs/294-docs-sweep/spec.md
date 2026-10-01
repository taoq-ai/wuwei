# Feature Specification: Docs sweep: README, site and animated hero up to date with waves F to R and the calibration layer

**Feature Branch**: `294-docs-sweep`
**Created**: 2026-10-01
**Status**: Ready
**Input**: GitHub issue #294, "docs: bring the README, the site and the animated hero up to date with waves F to R and the calibration layer". Depends on #287, #288 and #291, all on `main` (ddc9495).

## Problem (reproduced)

Each item since #220 and #259 updated the page it touched; nothing checks the whole. Reproduced
read-only on `main` (ddc9495) in this worktree; `tests/test_docs.py` passes (25 passed), so the
drift below is invisible to the suite.

1. `bin/wuwei --help` prints 50 commands. 23 of them never appear as `wuwei <command>` on
   `docs/site/reference.md`: agents, board, calibrate, consolidate, dashboard, discover,
   event, git-hook, index, init, memory, merge, note, outbound, payload, promote, reply,
   report, retro, runtime, signal, sweep, voice. The page has no command list at all
   (`docs/site/reference.md` lines 5 to 11 go straight to the plan JSON).
2. `templates/workspace/config.toml` has 36 table headers (commented ones included). 32 are
   never named as a section on `docs/site/configuration.md`; only `[[repos]]`, `[boundary]`,
   `[environments]` and `[outbound]` are. The schema sections `[listen]`, `[responder]` and
   `[chat]` (`cli/wuwei/workspace.py` lines 83, 84 and 139) are not in the template at all,
   so a template-only check cannot see them. `test_every_template_config_key_is_documented`
   (`tests/test_docs.py` line 106) checks keys, never sections.
3. `test_site_pages_and_links` (`tests/test_docs.py` lines 63 to 71) checks a hard-coded page
   tuple, so a new page missing from `index.md` passes.
4. README (`README.md` lines 90 to 104): the quick start goes from `init` straight to
   `/wuwei plan`; calibrate and the owner interview are missing. Line 21 still says "The
   current release includes the CLI, role charters and interactive day planner"; nothing
   lists what ships by area. `docs/site/index.md` "Start here" (lines 20 to 50) has the same
   gap.
5. Stale words for shipped things: `docs/site/configuration.md` lines 170 to 171 say "MCP
   scanning (#35) and role audits (#36) remain deferred" (both shipped);
   `docs/site/reference.md` line 128 says "the control plane (#65) will set `remote`" (#65
   is merged and nothing sets it, `cli/wuwei/sessions.py` line 11 only declares the role);
   `docs/site/charter-overrides.md` line 15 marks the steward-led proposal cycle
   "**Planned:**" (shipped: `steward run --trigger sweep|close|tool-calls`);
   `docs/site/configuration.md` line 93 opens with "Planned planner rotation" for the
   shipped scheduled rotation.
6. Missing explanations: `docs/site/concepts.md` has no section on review tiers, decision
   classes and cruise levels (designed only), the session registry, the listener, the
   heartbeat, or the cockpit and board. `docs/site/daily.md` step 4.3 (lines 82 to 87) does
   not say `dispatch next` returns the item's `tier` (`cli/wuwei/dispatch.py` line 185), and
   section 5 does not say how a DM answer shows. `docs/site/security.md` line 15 and
   `docs/integrity.md` do not name the plugin's own MCP server (the board, declared in the
   signed `.claude-plugin/plugin.json`) or the registry gate. `docs/site/recovery.md` and
   `docs/site/rehearsal.md` do not link each other.
7. The hero (`scripts/build-hero.py` lines 196 to 310) has no calibrate station, no tier on
   the gate markers, the owner as the only owner surface, and no heartbeat. Running
   `python3 scripts/build-hero.py` today regenerates both SVGs byte-identical (15942 bytes
   each), so the generator and the committed files agree.
8. Cruise mode (design spec 5.8.1, #282) is designed, not built (#283). No page says so;
   `[decisions.cruise]` in a workspace config is refused today by `bin/wuwei config check`
   with `unknown key decisions` (verified in a scratch workspace outside the repository).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Docs cannot drift from the CLI and the config again (Priority: P1)

A maintainer adds a command or a config section and forgets the docs; the docs tests fail and
name what is missing.

**Why this priority**: the issue calls these two tests the lasting deliverable.

**Independent Test**: the two coverage tests in `tests/test_docs.py`, run against the real
help output and the real template and schema.

**Acceptance Scenarios**:

1. Given `bin/wuwei --help` and the template, when the docs tests run, then the command
   coverage test and the section coverage test pass.
2. Given a command in the help output that has no row in the `## Commands` table of
   `reference.md` (or a row for a command the help no longer prints), when the command
   coverage test runs, then it fails naming the command.
3. Given a template table header or a top-level schema table that `configuration.md` does
   not name as `` `[section]` `` or `` `[[section]]` ``, when the section coverage test
   runs, then it fails naming the section.

### User Story 2 - A reader finds every shipped area from the README (Priority: P1)

A new reader of the README sees the first day as it is (init, calibrate, interview, plan),
finds each shipped area with one click, and is never told that a designed-only feature
ships.

**Why this priority**: the README is the entry point the owner asked to be current.

**Independent Test**: README assertions in `tests/test_docs.py`.

**Acceptance Scenarios**:

1. Given the README, when a reader opens `## What ships today`, then it lists the loop,
   guards, gates with tiers, remote operation, cockpit and board, calibration and heartbeat,
   each with one link to the page that explains it.
2. Given the README quick start and `index.md` "Start here", then `init`, `bin/wuwei
   calibrate`, `bin/wuwei calibrate --interview` and `/wuwei plan` appear in that order.
3. Given the README and every site page, when a paragraph mentions cruise mode, then it says
   "not built" and points at the design spec; nothing presents its levels as shipped.
4. Given the comparison section, then the WUWEI row and "Where WUWEI is worse" match today:
   one owner, Claude Code only, hooks 40 to 100 ms per tool call depending on hardware
   (40 to 50 ms CPU p95 on M-series), cooperative not an isolation boundary, proven only by
   the author until the live rehearsal passes. The existing comparison test stays green.

### User Story 3 - The site is one coherent whole (Priority: P2)

**Why this priority**: the pages exist; this makes them agree and cross-link.

**Independent Test**: site assertions in `tests/test_docs.py`.

**Acceptance Scenarios**:

1. Given `docs/site/*.md`, then `index.md` links every other page (derived from the
   directory, not a fixed list).
2. Given `concepts.md`, then it has sections on review tiers, decision classes and levels
   (designed, not built), the session registry, the listener, the heartbeat, and the cockpit
   and board, each linking to the page with the detail.
3. Given `daily.md`, then the gates step names the `tier` that `dispatch next` returns, and
   section 5 says how a DM answer shows (`phone answers`) and that the host records it.
4. Given `security.md` and `docs/integrity.md`, then both name the plugin's board MCP server
   declared in the signed `plugin.json` and the registry gate (`bin/wuwei mcp check`).
5. Given `recovery.md` and `rehearsal.md`, then each links the other.
6. Given the site and README, then the stale sentences in Problem item 5 are gone.

### User Story 4 - The hero shows the current day (Priority: P2)

**Why this priority**: the owner named the SVG explicitly; it is generated, so it is cheap
to keep exact.

**Independent Test**: hero assertions in `tests/test_docs.py` plus the existing generator
and geometry tests.

**Acceptance Scenarios**:

1. Given `python3 scripts/build-hero.py`, then both SVGs regenerate byte-identical to the
   committed ones (existing `test_hero_files_match_their_generator`).
2. Given either SVG, then it shows a `Calibrate` station before Plan with an owner
   `interview` touchpoint, a tier caption on the gate markers (one gate or three), a `Phone`
   owner surface with a decision answered from the `DM`, and a `heartbeat` pulse on the
   guard ring; the process is still the non-linear loop with owner pulses and both themes.
3. Given either SVG, then it is under 20000 bytes, its `<desc>` and the README `alt` text
   name calibrate, tier, phone and heartbeat, and every new animated element is hidden under
   `prefers-reduced-motion`.
4. Given the dark and light SVGs with colours masked, then they are identical (existing
   `test_hero_variants_share_geometry_and_motion`).

### Edge Cases

- A command spelled with a dash (`fast-checks`, `git-hook`): the table row uses the help
  spelling, `bin/wuwei git-hook`.
- `[[repos]]` is an array of tables: either `` `[repos]` `` or `` `[[repos]]` `` counts.
- `[repos.gates]` is a schema sub-table not in the template; the existing
  `test_repository_gate_keys_are_documented` already pins its keys and the section map
  names it, but the section test does not derive nested schema tables.
- `[decisions.cruise]` is in neither the template nor the schema; it is documented as
  designed, not built, and the section test does not require it.
- The help output's command list must be read with no workspace in scope (cwd outside any
  `.wuwei/`), so a developer's workspace or `.env` cannot change it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `docs/site/reference.md` MUST have a `## Commands` section whose table has one
  row per command printed by `bin/wuwei --help`, as `` | `bin/wuwei <command>` | ... | ``,
  with what it does and a link to where it is described when another page describes it.
- **FR-002**: A test MUST read the commands from the real `--help` output (one subprocess:
  `sys.executable -P -m wuwei --help` with `PYTHONPATH` set to `cli`, cwd `tmp_path`) and
  assert the table's command set equals it, naming missing and extra commands.
- **FR-003**: `docs/site/configuration.md` MUST name every template table header and every
  top-level table of `workspace.SCHEMA` as `` `[section]` `` (or `` `[[repos]]` ``), via a
  short section map near the top that links to the heading that documents its keys.
- **FR-004**: A test MUST derive those sections from the template (the same header regex the
  key test uses) and from `workspace.SCHEMA` (top-level dict or list values) and fail
  naming each one the page does not name.
- **FR-005**: `test_site_pages_and_links` MUST derive the page list from `docs/site/*.md`.
- **FR-006**: README MUST have `## What ships today` between "What WUWEI is and is not" and
  "How WUWEI compares", with one link per area (loop, guards, gates with tiers, remote
  operation, cockpit and board, calibration, heartbeat), and one sentence naming cruise
  mode as designed, not built, linking the design spec.
- **FR-007**: README quick start and `index.md` "Start here" MUST show init, calibrate
  (with `config promote` and `promote`), the interview, then `/wuwei plan`.
- **FR-008**: Every paragraph in README and `docs/site/*.md` that mentions cruise MUST say
  "not built".
- **FR-009**: `concepts.md`, `daily.md`, `security.md`, `docs/integrity.md`, `recovery.md`,
  `rehearsal.md` and `index.md` MUST carry the content in User Story 3, and the stale
  sentences in Problem item 5 MUST be gone, each pinned by a test.
- **FR-010**: `scripts/build-hero.py` MUST add the four stations of User Story 4 without
  moving existing nodes, paths or token timings, and the committed SVGs MUST be its output.
- **FR-011**: No page or test may contain an em-dash, an emoji or an absolute local path.
- **FR-012**: No runtime code under `cli/` or `adapters/` changes, and neither does
  `templates/workspace/config.toml`.

### Key Entities

- **Command table**: the `## Commands` table in `reference.md`; one row per CLI command.
- **Section map**: the table near the top of `configuration.md` naming each config section
  and the heading that documents it.
- **Hero stations**: calibrate pill, tier caption, phone pill, heartbeat pulse, generated by
  `scripts/build-hero.py` for both palettes.

## Success Criteria *(mandatory)*

- **SC-001**: Removing any row from the command table, or any section name from the
  section map, makes `python -m pytest -q tests/test_docs.py` fail naming it.
- **SC-002**: The full suite passes; `python3 scripts/build-hero.py` leaves `git status`
  unchanged after the SVGs are regenerated.
- **SC-003**: Each shipped area is one click from the README.

## Assumptions

- The notes name no dry-run workspace for this docs item; the reproduction was the help
  output, the template, the schema and the pages on `main`, plus one scratch workspace
  outside the repository to confirm `config check` refuses `[decisions.cruise]`.
- "Every `bin/wuwei --help` command appears on reference.md" is read as a `## Commands`
  table with exactly the help's command set, so a removed command fails too.
- "Every template config section" includes the top-level schema tables missing from the
  template (`[listen]`, `[responder]`, `[chat]`), because the issue names `[listen]`; the
  template itself is not changed (FR-012). Nested schema tables that are inline in practice
  (`repos.identity`, `sessions.rotate_after`, `outbound.people`) are not required as
  `[section]` names.
- The issue's `[gates]` is the per-repository `[repos.gates]`; its keys are already pinned
  by `test_repository_gate_keys_are_documented`. `[heartbeat]` is not a section; the
  heartbeat is configured by `watch.ping_url`, already pinned by `test_heartbeat_is_documented`.
- The issue's `integrity.md` is `docs/integrity.md` (there is no `docs/site/integrity.md`).
- The issue's "hooks 40 to 50 ms on M-series" refines, not replaces, the pinned "40 to 100 ms"
  bullet: the README keeps the range and adds the M-series figure from `reference.md`.
- Hero size budget: under 20000 bytes per SVG (15942 today); no budget was written down
  before. Labels use the exact words `Calibrate`, `interview`, `tier`, `Phone`, `DM` and
  `heartbeat`, so the test can pin them.
- The `**Planned:**` steward-led proposal cycle in `charter-overrides.md` is shipped: the plan
  skill runs `steward run --trigger close|sweep|tool-calls`, and seats write proposals that
  `promote` lands.
- "Planned planner rotation" in configuration.md becomes "Scheduled planner rotation" so
  "planned" is not read as unshipped.
- `security.md`'s "when built, an external control plane" is the design spec 9.1 wording for
  an off-host boundary, which the local Slack listener is not; it stays, as do the phrases
  `test_guard_boundaries_are_stated_once` pins.
- Only `scripts/build-hero.py`, the two SVGs, README, `docs/site/*.md`, `docs/integrity.md`
  and `tests/test_docs.py` change.
