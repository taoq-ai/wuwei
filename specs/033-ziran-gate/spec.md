# Feature Specification: ZIRAN agent-surface gate

**Feature Branch**: `033-ziran-gate`
**Created**: 2026-09-29
**Status**: Ready
**Input**: Issue #33, security integration S4.

## User Scenarios & Testing

### User Story 1 - Findings prevent a clean security gate (Priority: P1)

The lead receives security findings for agent-facing changes before raising a PR.

**Independent Test**: Receive a security verdict for a flagged item using a vulnerable
fixture agent and recorded scanner output.

**Acceptance Scenarios**:

1. Given a vulnerable fixture agent in a worktree and `agent_surface` set, when the
   security verdict is received, then it is FIX with each ZIRAN finding as a verdict row.
2. Given a measured clean agent, when its security verdict is received, then PASS is
   possible if the sentinel has no other blocking findings.
3. Given a trust-boundary finding below the configured threshold, then it still blocks.
4. Given an unflagged item or a different sentinel, then no scanner is invoked.
5. Given only ordinary findings below threshold, then append them as notes and retain PASS.

### User Story 2 - Unmeasured never passes (Priority: P1)

The lead can distinguish unavailable security evidence from a clean measurement.

**Independent Test**: Exercise missing tools, error exits, timeouts and invalid reports.

**Acceptance Scenarios**:

1. Given ZIRAN is not installed, when the gate runs, then it reports unmeasured (exit 2),
   never PASS, and does not record a received gate.
2. Given scanner none, a command error, timeout, unreadable or malformed result,
   then the same unmeasured outcome and a reason are returned.
3. Given a delta security review, then scanning runs again against the reviewed worktree.

### Edge Cases

- Unknown severity, error-shaped bodies and incomplete findings cannot count as clean.
- Missing worktree evidence cannot bypass scanning for a flagged item.
- Report text cannot inject verdict rows or expose private markers in events.
- A changed HEAD during scanning invalidates the measurement.

## Requirements

### Functional Requirements

- FR-001: Reuse the scanner port for audit and threshold evaluation; only those external
  operations are permitted by this adapter.
- FR-002: Scan flagged security gates before recording a verdict; retain sentinel findings.
- FR-003: Every finding carries severity, evidence, scenario and blocking disposition.
- FR-004: Tool failures report exit 2 with a reason. Scanner adapter findings use exit 1;
  dispatch receive returns 0 when a valid verdict is recorded, including FIX.
- FR-005: Scanner findings use the existing reserved event and gate state producers.
- FR-006: Configuration documents scanner selection and severity threshold.
- FR-007: Unrelated calls outside a WUWEI workspace remain unaffected.

### Key Entities

- Item flags: existing approved `agent_surface`, `trust_surface`, `boundary_relevant` flags.
- Scanner result: measured report or unmeasured reason.
- Gate verdict: existing reviewed HEAD, finding rows and received gate state.

## Success Criteria

- SC-001: Every vulnerable fixture finding appears in the security verdict.
- SC-002: All unmeasured cases refuse a clean gate with exit 2.
- SC-003: The existing suite and deterministic offline acceptance tests pass.

## Assumptions

- Item configuration means existing approved day-state item flags, not a new config table.
- Scanner selection defaults to none; the default severity threshold is high.
- The existing dispatch receive boundary owns mandatory scanning and records findings.
- Audit targets the worktree in the dispatched brief. No new executable-path config.
- Known CI finding exits are distinct from command errors and require valid evidence.
- Dependencies #5, #22 and scanner/event ports from #15/#105 are already present.

## Deferred

- #34 live-trace scanning, blocked by taoq-ai/ziran#421.
- #35 MCP audit and drift, blocked by taoq-ai/ziran#422.
- Compatible upstream audit JSON output and CI JSON/--severity-threshold support are
  required for live S4 use; the available CLI does not expose them. See research.md.
- S1 plugin-agent support and release pinning remain upstream work.
