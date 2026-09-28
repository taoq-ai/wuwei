# Feature Specification: Runtime adapters

**Feature Branch**: `026-runtime-adapter`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: Issue #26 and amendments.

## User Scenarios & Testing

### User Story 1: Dispatch a chartered seat

A planner dispatches a saved brief to the configured runtime. Claude uses the plugin agent type. Codex receives the same charter as a readable path and runs from the item's worktree.

**Acceptance Scenarios**:

1. Given the default runtime, dispatch uses a Claude plugin agent type and returns a job handle.
2. Given a Codex job whose reported workspace root differs from the worktree, dispatch cancels it and reports a finding.
3. Given a matching Codex workspace, status and result are polled from that worktree. Tool failures, malformed output and timeouts report exit 2 with a reason.
4. Given a Codex seat that wrote a gate verdict, the shared verdict lint runs and a refusal is returned to the seat; its retro is captured through the shared checker.

### User Story 2: Build until green or stuck

A builder runs checks after each seat result. A failed check is fed to the next iteration, up to the configured limit.

**Acceptance Scenarios**:

1. Given the same failing check signature three times, the item parks as stuck after iteration 3 with a decision record.
2. Given a seat that fixes the check on iteration 2, the loop ends green with two usage events.
3. Given an unavailable runtime or check, the loop reports exit 2 and does not count it as green.

## Requirements

- FR-001: Runtime adapters implement dispatch, status, result and same-seat continuation through the registry with three-state results.
- FR-002: Codex verifies job workspace immediately after dispatch and cancels on mismatch.
- FR-003: Runtime values and executable paths used by the Codex companion are configuration, without engagement-specific defaults.
- FR-004: Build iterations record reported usage and stop on green, repeated signature, or iteration limit.
- FR-005: Gate verdicts and retro output from Codex use the shared validators.

## Assumptions

- Claude's `Agent` tool is invoked by the calling Claude host; the adapter returns the plugin agent type and brief as dispatch data. There is no standalone `claude` binary dependency.
- Codex companion is configured by path, with no built-in machine-specific location. The companion's `task`, `status`, `result` and `cancel` commands return JSON.
- The caller supplies an existing worktree and brief. Only a matching workspace root permits later status/result operations.
- The build loop is a CLI command and uses the configured fast checks through the existing checks port.

## Deferred

- Recovery of interrupted build loops and planner scheduling belong to later orchestration work.
