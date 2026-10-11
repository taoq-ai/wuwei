# Feature Specification: delete the MCP registry gate; scanner findings stay for the security gate

**Feature Branch**: `b7-leftovers` (feature directory `specs/840-mcp-gate-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #840, part 18 of the #789 deletion pass: "chore(mcp): delete the MCP registry
gate; scanner findings stay for the security gate".

## Context

The MCP registry gate (design 7, S3) is:

- `wuwei mcp check`: discovers the MCP servers Claude Code would attach, scans each through
  the scanner port, and stores a registry under `.wuwei/`;
- `wuwei mcp decide`: records the owner's answer on a D-n decision record, confirmed in the
  planner session or by a y/N prompt at the host terminal (`integrity._host_confirm`);
- a launch gate: `guards/agent_launch.check_mcp` on every seat launch, and `mcp.launch` in the
  Claude and Codex runtime adapters, block a launch on findings in `scanner.mcp.block` or on a
  check that could not run;
- the readers: the `mcp` row of `next`, the morning `plan propose` check and its sweep line,
  the brief's `MCP unmeasured:` header, the `doctor` gates rows and `mcp-reports` fix, `status`
  attention lines, `init`'s first registration, the event, signal and state producer tables.

Each makes the planner or the owner reason about a process (which record, which answer, a
host-terminal prompt). The owner kept (pass plan, "Kept by the lead") the ZIRAN scanner
findings the security gate reads: design 7 S2 (runtime traces, `scanner.trace_sweep`) and S4
(the agent-surface gate, `scanner.rows` merged into the security verdict by
`dispatch.receive`). Neither reads the registry.

Part 14 (#834) left a slice of `decision.py` for the MCP cards, the D-n branch of
`guards/answers.py`, and `decision.owner_confirm` with its `_host_confirm` fallback, with LEFT
rows in `tests/test_reasons.py` naming part 18. Part 16 (#838) deletes the learning cards, the
drafts and `commands/outbound.py`, so after it the MCP gate is the last caller of
`_host_confirm` and of the D-n record library. Part 17 (#839) hands `agent_launch.check_mcp`
to this part.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A seat launches without an MCP registry check (Priority: P1)

**Why this priority**: the launch gate is the unit the issue deletes; a leftover call would
refuse launches with a reason that names a command that no longer exists.

**Independent Test**: launch a builder seat in a workspace with `adapters.scanner = "ziran"`
and no registry record; dispatch through the Claude and Codex runtime adapters.

**Acceptance Scenarios**:

1. **Given** a workspace with a scanner configured and no registry record, **When** a seat
   `Agent` call runs PreToolUse, **Then** no MCP check runs and no reason names `mcp`.
2. **Given** the Claude or Codex runtime adapter, **When** `dispatch` or `continue_job` runs,
   **Then** it builds the launch without reading any MCP registry.
3. **Given** a seat brief, **When** it is written, **Then** it carries no `MCP unmeasured:`
   header.

### User Story 2 - The morning plan and `next` have no MCP step (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a fresh day with no plan, **When** `wuwei next` runs, **Then** after `pr-flow`
   it goes to the lead brief; no `mcp` row exists.
2. **Given** `wuwei plan propose <lead.json>`, **When** it runs, **Then** it runs no MCP check,
   refuses nothing over MCP, and the measured sweep has no `mcp` line.
3. **Given** the CLI, **When** `wuwei mcp check` or `wuwei mcp decide` runs, **Then** argparse
   refuses it as an unknown command.

### User Story 3 - The security gate still receives scanner findings (Priority: P1)

**Why this priority**: the owner kept the ZIRAN findings the security sentinel reads.

**Acceptance Scenarios**:

1. **Given** a security verdict received for an item with `agent_surface` and
   `adapters.scanner = "ziran"`, **When** `dispatch receive` runs, **Then** `scanner.rows` adds
   the `## ZIRAN findings` section and a blocking finding turns PASS into FIX, as today.
2. **Given** a watch sweep with traces, **When** `scanner.trace_sweep` runs, **Then** it pages
   and parks as today.

### User Story 4 - No host-terminal prompt and no D-n record are left (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the source under `cli/wuwei`, **When** `tests/test_reasons.py` scans it, **Then**
   no module defines or calls `_host_confirm` or opens `/dev/tty`, and no LEFT row names part 18.
2. **Given** an AskUserQuestion whose header is `D-<n>`, **When** PostToolUse runs, **Then** it
   records nothing; an Owner step card is still recorded as today (#831).
3. **Given** `wuwei doctor`, **When** it runs, **Then** no row reads the MCP registry or the
   answered D-n cards.

### User Story 5 - `init --upgrade` removes the retired keys (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a config with `[scanner.mcp]` holding `project_file`, `user_file`,
   `timeout_seconds` and `block`, **When** `init --upgrade` runs, **Then** it removes those four
   keys and keeps `scanner.mcp.plugins_file` (Assumption 2).

### Edge Cases

- A workspace upgraded from an earlier version keeps the registry files and the
  `.wuwei/ziran/<server>/` report directories. Nothing reads them; part 24's obsolete-file
  removal in `init --upgrade` takes them (plan.md Handoff).
- Today's events may hold `mcp.finding`, `mcp.checked` and `mcp.decided` rows. Telemetry and
  metrics read past days and keep accepting them; `status` no longer turns them into attention.
- A day's `decisions/D-<n>.md` from an MCP decision stays on disk as history; `decision.naming`
  still maps it to items for the 5.6 metrics of past days.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `cli/wuwei/mcp.py`, `cli/wuwei/commands/mcp.py`, the scanner port operation
  `mcp` (registry `PORTS`, `adapters/scanner/ziran.py` `mcp` and `_mcp_report`,
  `adapters/scanner/none.py` `mcp`) and their tests MUST be deleted.
- **FR-002**: No launch path MUST read an MCP registry: `agent_launch.check_mcp` and its
  `GUARDS` entry, and the `mcp.launch` calls in `adapters/runtime/claude.py` and
  `adapters/runtime/codex.py`, go.
- **FR-003**: `plan propose`, `next`, `brief`, `doctor`, `status`, `init`, `config`,
  `protect_state`, `event`, `signal` and `state` MUST NOT import `wuwei.mcp` or name the gate.
- **FR-004**: `scanner.rows`, `scanner.merge`, `scanner.trace_sweep`, `ziran.audit`,
  `ziran.gate` and `ziran.traces` MUST stay unchanged; their tests stay green.
- **FR-005**: `integrity._host_confirm` and `HOST_TERMINAL` MUST be deleted, and no module
  MUST call `_host_confirm` or open `/dev/tty`. `tests/test_reasons.py` MUST assert it.
- **FR-006**: `decision.py` MUST keep only what non-MCP callers read: `widget` (plan and close
  gate cards), `gate`, `naming` and `answered` (metrics, telemetry, tracker over past days).
  The record library (fields, evaluate, scoring, write, card hash, owner confirm, owner record,
  today path) MUST go.
- **FR-007**: `guards/answers.record_gate` MUST keep only the Owner step branch (#831). The D-n
  branch and the planner-session `gate_asked` write MUST go, with `sessions.caller` and
  `sessions.gate_topics`, and `doctor`'s `answered cards` row with `_unrecorded` and
  `_owner_on_file`.
- **FR-008**: `scanner.mcp.project_file`, `scanner.mcp.user_file`,
  `scanner.mcp.timeout_seconds` and `scanner.mcp.block` MUST leave the schema and template and
  join `workspace.RETIRED`. `scanner.mcp.plugins_file` stays (Assumption 2).
- **FR-009**: Charters, skills, the generated agents, the design spec (7 S3 and the sections
  that name the gate), README and the docs site MUST name no `wuwei mcp`, MCP registry or MCP
  launch gate; `docs/site/reference.md` keeps no `mcp` row (any duplicate goes with it).
- **FR-010**: The part 18 LEFT rows of `tests/test_reasons.py` MUST be deleted.

### Key Entities

- **Scanner findings** (kept): `scanner.finding` events and the `## ZIRAN findings` verdict
  section written by `dispatch.receive`; `traces.*` and `scanner.finding` events from the
  sweep.

## Success Criteria *(mandatory)*

- **SC-001**: `grep -rnE "wuwei\.mcp|from wuwei import mcp|commands\.mcp|mcp check|mcp decide|check_mcp|mcp\.launch|scanner\.mcp\.block|_host_confirm|owner_confirm|HOST_TERMINAL"`
  over `cli/`, `adapters/`, `charters/`, `skills/`, `agents/`, `hooks/`, `templates/`,
  `scripts/` and `docs/site/` returns nothing.
- **SC-002**: The scanner tests (the ZIRAN adapter tests and the `dispatch receive` scanner
  cases) pass unchanged.
- **SC-003**: `init --upgrade` on a config with the four retired keys removes them and prints
  one line each (`tests/test_config_transition.py`).
- **SC-004**: Every touched test file passes. No test is loosened: deleted tests cover only
  deleted code.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. The gate is (a) process machinery: the owner answered MCP findings on a D-n card or at a
   host terminal, and the planner ran the check as a ritual step. It stops no process error in
   the "process control kept" table. An MCP server's risk is a trust question the owner settles
   when attaching the server; the security sentinel still scans an `agent_surface` change.
2. `scanner.mcp.plugins_file` stays under its name. `integrity.registered`,
   `specmode.present` and `doctor`'s plugin rows read it to find installed plugins, and tests
   point it at fixtures. Renaming it would retire a key an owner may have set; part 24 may move
   it with the CLI rewrite.
3. Telemetry is kept. Its constants keep accepting `mcp` rows of past days where a stored row is
   validated against them; only the live guard area goes (plan.md).
4. `decision.py` keeps its name. Its four survivors are card helpers (`widget`, `gate`) and
   past-day readers (`naming`, `answered`); a rename is churn with no reader gain.
5. Files of the old registry under `.wuwei/` stay on disk until part 24's obsolete-file removal.
6. Parts 16 (#838) and 17 (#839) land first on this batch's base: this part edits their end
   state (plan.md marks each such edit).
