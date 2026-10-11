# Feature Specification: delete the cockpit (board, dashboard, menu bar, brief packs)

**Feature Branch**: `808-cockpit-out`

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #808, part 5 of the #789 deletion pass: "Delete the cockpit: the board MCP server (and its entry in the plugin manifest), the dashboard, the SwiftBar menu bar, brief packs and drills, and the phone status signal command, with their templates, fixtures and tests. None of them is reached by the item loop or the five edges; `next`, `status --line` and `report` remain the owner's surfaces. Telemetry and DORA stay (owner, 2026-10-11)."

## Context

The cockpit is a set of read-only owner views layered over day state:

- the board: `wuwei board`, a stdio MCP server declared under `mcpServers.cockpit` in
  `.claude-plugin/plugin.json`, offering the `wuwei_board` tool and the `ui://wuwei/board.html`
  resource (an MCP Apps page);
- the dashboard: `wuwei dashboard`, a loopback HTTP server rendering `templates/dashboard.html`
  from `cockpit_snapshot` and `board_snapshot`;
- the SwiftBar menu bar: `templates/swiftbar/wuwei.1m.sh` and `wuwei init --menu-bar`;
- brief packs and the defend drill: `wuwei brief pack [--meeting]` and `wuwei brief answer N TEXT`
  in `cli/wuwei/brief_pack.py`, the `brief_packs` and `brief_drill` state keys, the
  `brief_drill_score` metric, and the `brief.lead_minutes` and `brief.style` config keys;
- the signal command: `wuwei signal classify`, a stdin wrapper over `signal.classify`.

None of them is called by the item loop (brief, seat, gates, verdict lint, fix rounds,
`pr raise --item`, merge) or by the five edges. `wuwei next`, `wuwei status --line` and
`wuwei report` stay the owner's surfaces. The classifier `cli/wuwei/signal.py` stays: the status
view reads it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No cockpit commands or server (Priority: P1)

The owner and the planner see no board tool, dashboard, menu bar or signal command. Claude Code
starts no WUWEI MCP server.

**Why this priority**: it is the issue.

**Independent Test**: `bin/wuwei --help --all` lists none of `board`, `dashboard`, `signal`;
`.claude-plugin/plugin.json` has no `mcpServers`; `wuwei init --menu-bar` is refused by argparse.

**Acceptance Scenarios**:

1. **Given** the plugin, **When** `wuwei board`, `wuwei dashboard` or `wuwei signal classify`
   runs, **Then** argparse refuses it as an unknown command (exit 2).
2. **Given** the plugin manifest, **When** Claude Code loads the plugin, **Then** it declares no
   MCP server.
3. **Given** `wuwei init --menu-bar`, **When** it runs, **Then** argparse refuses the flag.
4. **Given** `wuwei doctor` with `adapters.scanner = "none"`, **When** the gates section is
   built, **Then** it has the `mcp gate` row and no `mcp <name>` row for WUWEI's own servers.

---

### User Story 2 - No brief packs or drill (Priority: P1)

`wuwei brief` writes seat briefs only.

**Why this priority**: it is the issue.

**Independent Test**: `wuwei brief pack` exits 2 naming `expected ROLE ITEM NAME`;
`wuwei brief ROLE ITEM NAME --body TEXT` still writes and logs a brief.

**Acceptance Scenarios**:

1. **Given** a workspace, **When** `wuwei brief pack` or `wuwei brief answer 1 x` runs,
   **Then** it exits 2 naming the expected form and writes nothing.
2. **Given** a workspace, **When** `wuwei brief lead DISCOVERY lead-1 --body b` runs, **Then**
   the brief is written and logged exactly as today.
3. **Given** `metrics.collect`, **When** it runs, **Then** its result has no `brief_drill_score`.
4. **Given** the schema, **When** `load_config` reads a config without `[brief]`, **Then**
   `config['brief']` holds `remote`, `prior_branch_pattern` and `full_path_patterns` only.

---

### User Story 3 - Upgrade removes the retired keys (Priority: P2)

A workspace whose `config.toml` still sets `brief.lead_minutes` or a `[brief.style]` table is
cleaned by `wuwei init --upgrade`, which says what it removed.

**Why this priority**: the issue acceptance; the mechanism is #799's, this part only names the
keys.

**Independent Test**: after #799, `init --upgrade --dry-run` on such a config prints a "Would"
line naming `brief.lead_minutes`; `init --upgrade` removes it and prints the "Upgraded
config.toml: remove ..." line.

**Acceptance Scenarios**:

1. **Given** `[brief]` with `lead_minutes = 30` and `[brief.style]` with `speed = 180`, **When**
   `init --upgrade` runs after this part and #799, **Then** both are removed and reported, and
   `[brief]` keeps its other keys.

---

### User Story 4 - No page mentions the cockpit (Priority: P2)

No module, manifest entry, skill, charter or docs page refers to the board, dashboard, SwiftBar
or brief packs.

**Why this priority**: the issue acceptance.

**Independent Test**: the grep in plan.md "Verification" is empty outside `CHANGELOG.md`,
`specs/`, the tracker's own `board` key (a GitHub Projects board) and the design-spec
retirement notes.

### Edge Cases

- A day's `state.json` that already holds `brief_packs` or `brief_drill` still loads; nothing
  reads those keys, and `state set` no longer reserves them.
- A day's `events.jsonl` that already holds `brief.pack` or `brief.answer` events: the
  classifier now gives them the unknown-kind tier (today `nudge`, `warn` after #801). This
  affects at most the day of the upgrade.
- `adapters.calendar` stays: `status` reads the next meeting through it. `adapters.tts` and
  `adapters.transcripts` stay as ports with no caller (Assumptions, Deferred).
- A third party plugin or `.mcp.json` declaring a server named `cockpit` is still discovered and
  measured by the MCP registry gate exactly as today (part 18 owns that gate).
- Before #799, an unknown key raises under the strict posture; a strict workspace that sets
  `brief.lead_minutes` would fail to load if this part merged first. The merge order (part 2
  before part 5) prevents it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `cli/wuwei/commands/board.py`, `cli/wuwei/commands/dashboard.py`,
  `cli/wuwei/commands/signal.py` and `cli/wuwei/brief_pack.py` MUST be deleted.
- **FR-002**: `.claude-plugin/plugin.json` MUST NOT declare `mcpServers`.
- **FR-003**: `templates/dashboard.html`, `templates/swiftbar/` and `tests/fixtures/swiftbar/`
  MUST be deleted.
- **FR-004**: `wuwei init` MUST NOT accept `--menu-bar`.
- **FR-005**: `wuwei brief` MUST accept only `ROLE ITEM NAME` with `--body` or `--file`; the
  `--meeting` flag and the `pack` and `answer` forms MUST be gone.
- **FR-006**: `workspace.SCHEMA['brief']` MUST drop `lead_minutes` and `style`; the template
  MUST drop them; `calendar.url` stays.
- **FR-007**: `state.py` MUST NOT reserve `brief_packs` or `brief_drill`; `commands/event.py`
  MUST NOT map `brief.pack` or `brief.answer`; `signal.SILENT` MUST NOT list them;
  `metrics.collect` MUST NOT return `brief_drill_score`.
- **FR-008**: `doctor` MUST NOT print `mcp <name>` rows for servers in WUWEI's own
  `plugin.json` (there are none).
- **FR-009**: Charters, skills, built agents, README, NOTICE and `docs/site/*` MUST NOT refer
  to the board, the dashboard, SwiftBar, brief packs, the defend drill or the `wuwei_board`
  tool.
- **FR-010**: Design spec passages describing the cockpit, the menu bar, briefings, the board
  and `wuwei signal classify` MUST be marked retired "(owner, 2026-10-11, #789)".
- **FR-011**: The retired config keys `brief.lead_minutes` and `brief.style` MUST be added to
  `workspace.RETIRED` (now if #799 is on the base, else at rebase).
- **FR-012**: Telemetry and DORA MUST be unchanged: no edit to `cli/wuwei/telemetry.py`,
  `cli/wuwei/commands/telemetry.py`, `cli/wuwei/commands/dora.py` or their tests.
- **FR-013**: Tests that cover only deleted code MUST be deleted with it; tests that also cover
  kept code (calendar ICS parsing, the `say` adapter, drafts and metrics fail-closed, doctor
  decision supersede, the watch trace sweep, the ticket id on `next`) MUST keep that coverage.

### Key Entities

- **Retired config keys**: `brief.lead_minutes`, `brief.style` (table: `length`, `speed`).
- **Retired state keys** (left in old days, never read): `brief_packs`, `brief_drill`.
- **Retired event kinds** (left in old logs): `brief.pack`, `brief.answer`.

## Success Criteria *(mandatory)*

- **SC-001**: The grep in plan.md "Verification" returns no hit in kept code, manifests,
  charters, skills, agents or docs/site.
- **SC-002**: Every touched test file passes with `python -m pytest -q <files>`.
- **SC-003**: No assertion over kept behaviour is removed without a test that still covers it.

## Assumptions

- **Order**: parts 1 to 4 (#798, #799, #800, #801) merge first; this branch rebases onto them.
  Edits to `__main__.GROUPS`, `commands/__init__.READ_ONLY` and `WRITES`,
  `tests/test_cli_known_command.py`, the guide block in `docs/site/agent.md`,
  `tests/test_nudges_mode.py` and the prose pins in `tests/test_docs.py` apply only where those
  parts left them.
- **Signal module stays**: the issue's "phone status signal command" is `wuwei signal classify`
  (`commands/signal.py`). `cli/wuwei/signal.py` stays because `commands/status.py` reads
  `SILENT` and `classify`.
- **Calendar stays**: `status` shows the next meeting through `adapters.calendar` and
  `calendar.url`; only the brief pack's meeting window (`brief.lead_minutes`) goes.
- **tts and transcripts ports stay (Deferred)**: after this part nothing calls them. Removing
  them changes `telemetry.ADAPTERS`, which `telemetry.validate` uses to accept a stored week, so
  a stored week that names `tts` would stop loading. Telemetry is the owner's (2026-10-11), so
  their removal is deferred to a follow-up issue with a telemetry schema step. Their config
  rows are reworded to say no command calls them.
- **MCP registry gate untouched**: `cli/wuwei/mcp.py` keeps its signed-manifest coverage branch
  and `tests/test_mcp.py` keeps its lookalike-server cases (the name `cockpit` there is a
  fixture for a third party server); part 18 deletes that gate. Only the stale comment at
  `tests/test_mcp.py:775` is reworded.
- **NOTICE credits**: MCP Apps is credited only for the board's `ui://` resource, so it goes.
  Model Context Protocol stays credited for the server configuration format the MCP registry
  gate reads, until part 18.
- **Docs scope**: the issue acceptance names docs pages, so docs change at sentence level now;
  part 24 rewrites the site.
- **Design spec**: the constitution lets only the owner amend it; #789 is the owner's
  instruction, so retired passages are marked "(owner, 2026-10-11, #789)", as the sibling parts
  do.
- **Constitution**: its "the planner ends each turn with the board in one line" means the
  `next` and status summary, not the cockpit board; no amendment.

## Deferred

- Delete the `tts` and `transcripts` ports (`adapters/tts/`, `adapters/transcripts/`,
  `registry.PARAMETERS`, `SCHEMA['adapters']`, the template, docs rows, `telemetry.ADAPTERS`
  with a stored-week compatibility step). To be filed as its own issue linked to #789.
