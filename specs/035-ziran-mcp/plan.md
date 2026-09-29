# Implementation Plan: MCP audit and drift watch

## Summary

Extend the existing scanner.mcp port with per-file watch-registry calls. Add one
core module for discovery, persistent measurement and owner decisions. Call it
from init/upgrade, morning proposal and launch gates. Preserve raw reports only
under protected `.wuwei/ziran/`; events contain four finding metadata fields.

## Technical Context

Python 3.11 stdlib runtime, pytest offline tests. Existing ZIRAN >= 0.39.0 check,
registry.Result, atomic writer, locked events, scope helpers and decision parser.
The existing scanner.mcp(servers) argument becomes a list of config file paths.
No added dependencies or subprocess calls in core.

## Constitution Check

Stdlib only; external scanner behind existing adapter; exits 0/1/2; test before
implementation; producer-owned files and reserved events; workspace scope only.
No deviations. Extension hooks skipped as requested.

## Design

- Discover workspace/repo project files plus installed plugin paths and user file
  using scanner.mcp settings. Missing defaults are optional; unreadable files fail.
- Adapter checks version and runs once per config using only file paths. Store
  snapshots in `.wuwei/ziran/snapshots/<source digest>` and reports in a unique
  run directory. Validate report shape, allowed types and severity/code consistency.
- Persist an incomplete status before external work. Status includes check date,
  exit and a pending decision reference. Serialize checks/decisions with a lock.
- Preserve unresolved decisions across clean checks and day rollover. Queue a
  decision with safe static text and report location, never description values.
- Morning proposal checks before producing the plan. Launch gates read cached
  status and refuse absent/stale measurement when attachments exist.
- Owner host command validates the existing decision format, confirms a digest
  through the shared terminal helper and saves protected accepted evidence.
- Protect the entire ziran directory and deny the owner command through agent
  Bash using shared relevance detection. Reserve the MCP state namespace and
  event prefix. Gate both Agent and runtime adapter dispatch/continuation.

## Files

`adapters/scanner/ziran.py`, `cli/wuwei/mcp.py`, `cli/wuwei/commands/mcp.py`,
existing init/plan/launch/runtime/config/state/event/protect-state modules,
workspace config template, plan skill, and `tests/test_mcp.py`.

## Validation

Tests first for adapter reports and failures; discovery/init/upgrade; morning
acceptance and sticky decisions; protected files/events, scope and runtime
launches. One real PATH stub smoke test. Run the full requested pytest command.

## Deferred

Remote owner identity remains M5. The host terminal is the existing local friction
boundary, not a same-uid security boundary. ZIRAN owns protocol and snapshot logic.
