# Feature Specification: MCP audit and drift watch

**Feature**: #35, branch `035-ziran-mcp`  
**Status**: Implemented  
**Created**: 2026-09-29

## User Scenarios & Testing

### US1: Register attached servers (P1)

As the owner, I want init and upgrade to baseline the workspace's attached MCP
servers and report poisoning before work begins.

Acceptance: project, installed-plugin and user configurations are discovered;
each configuration is checked separately. First-registration poisoning is
reported. Missing tools, invalid inputs and unreachable servers are unmeasured.

### US2: Check before morning launches (P1)

As the owner, I want changed tools flagged before any seat launches.

Acceptance: given a server whose tool description changed since registration,
the morning plan flags it and the seat launch guard refuses. High or critical
findings remain open until an owner decision. Incomplete checks block with exit
2 and a reason. Medium and low findings are reported with exit 0. A later clean
check does not erase an open decision. A new day requires a new measurement.

### US3: Protect evidence and owner decisions (P1)

As the owner, I want untrusted tool descriptions confined to reports and no seat
able to clear a block by writing an approval file or event.

Acceptance: events include only server name, drift type, severity and tool name.
Snapshots, check status and accepted decisions are producer-only. A seat-written
decision is a proposal, not owner evidence. Owner confirmation happens on the
host, outside agent tools. Outside a workspace the gate is a clean no-op.

### Edge cases

Duplicate server names across configs, malformed reports, partial results,
missing reports, timeouts, stale measurement, scan interruption, symlinks,
repeated checks, day rollover and forged events fail safely.

## Requirements

- FR-001: Discover repo MCP files, installed plugin MCP files and the user MCP
  settings file from documented configurable paths.
- FR-002: Use the existing scanner adapter and version check, passing file paths
  only to the external scanner; preserve per-config snapshots and reports.
- FR-003: Register at init and upgrade and check at morning proposal before
  launch; enforce 2 > 1 > 0 across configurations.
- FR-004: Keep high/critical findings pending until an owner decision; never let
  an owner decision excuse an incomplete measurement.
- FR-005: Reserve authoritative state and event kinds, protect scanner files,
  and reuse shared scope, writer, decision and adapter helpers.
- FR-006: Run offline tests first and the full suite; leave changes uncommitted.

## Key Entities

Configuration source; persistent per-source snapshot; per-run report; daily
measurement; persistent open decision; host-confirmed decision evidence.

## Success Criteria

- SC-001: A changed description is reported before all tested launch paths.
- SC-002: Every incomplete scan blocks with exit 2 and a reason.
- SC-003: No description values or config secrets occur in events or argv.
- SC-004: Owner decisions cannot be forged through supported seat writes.

## Assumptions

- Missing default user/plugin files and absent repo MCP files mean no attachment;
  explicit user/plugin path overrides must exist. Empty attachment sets are clean.
- Defaults are `.mcp.json` in the workspace and configured repos,
  `~/.claude/plugins/installed_plugins.json` for installed plugin paths, and
  `~/.claude.json` for user MCP settings. Relative overrides use the workspace.
- Plugin registry version 2 installation entries use `installPath`, `scope` and
  optional `projectPath`; project/local installations must match a workspace repo.
- Findings survive repeat checks and day rollover. Exit 2 requires a successful
  recheck; a host-confirmed proceed decision can clear only measured findings.
- Host confirmation follows the existing integrity terminal boundary and threat
  model; local files cannot resist a determined process running as the owner.

## Deferred

Remote owner authentication belongs to M5. Server protocol, scanning and snapshot
semantics belong to ZIRAN #422. No replacement scanner is implemented here.
