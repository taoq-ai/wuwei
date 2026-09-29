# Feature Specification: ZIRAN role audit in CI

**Feature Branch**: `036-ziran-ci-audit`
**Created**: 2026-09-29
**Status**: Implemented
**Input**: Issue #36, ci(security): audit role allowlists with ZIRAN in CI (S1).

## User Scenarios & Testing

### User Story 1 - Refuse widened agent capabilities (Priority: P1)

As a maintainer, I need pull requests and main pushes checked against reviewed
agent grants so additional dangerous tool chains cannot pass unnoticed.

**Independent Test**: Audit the current agents, then audit a temporary copy with
WebFetch added to the builder.

**Acceptance Scenarios**:

1. **Given** the recorded grants, **when** current agents are audited, **then**
   the audit passes despite existing dangerous tools and chains.
2. **Given** a PR adding WebFetch to the builder, **when** CI audits it, **then**
   CI fails naming the builder's new dangerous chain.
3. **Given** an unreadable baseline or audit error, **when** CI audits, **then**
   the job fails instead of reporting clean.

### User Story 2 - Keep reviewed grants reproducible (Priority: P2)

As a maintainer, I need local drift detection and a documented regeneration loop
so generated agents and reviewed grants stay aligned.

**Independent Test**: Compare recorded agent names and tools with the allowlist
without requiring a scanner installation.

**Acceptance Scenarios**:

1. **Given** the committed baseline, **when** default tests run, **then** all
   allowlist agents and tools match its version 1 grants exactly.
2. **Given** changed allowlist grants without re-recording, **when** tests run,
   **then** the consistency check fails locally.
3. **Given** a reviewed charter or allowlist change, **when** the maintainer
   follows the documented loop, **then** agents and baseline are regenerated.

### Edge Cases

- Missing ZIRAN skips only optional real-tool tests with an explicit reason.
- A present scanner that fails to run fails its tests and CI.
- Existing Bash and Write grants remain accepted; new critical findings do not.
- SARIF upload permission failure does not override the audit outcome.

## Requirements

### Functional Requirements

- **FR-001**: Audit `agents/` on pull requests and pushes to main using the ZIRAN
  action and package pinned to v0.40.0, at high severity.
- **FR-002**: Record `agents/ziran-baseline.json` with the real released CLI;
  never hand-write grants or introduce a converter or runtime dependency.
- **FR-003**: Preserve audit failures for exits 1 and 2 and the action's default
  SARIF reporting, granting security-events write at job scope.
- **FR-004**: Default tests must compare version 1 baseline agent/tool grants
  with `agents/allowlist.json` using stdlib only.
- **FR-005**: When ZIRAN is available, exercise clean and WebFetch-widened copies
  through the real audit; require exit 1 and a builder BL003 row with WebFetch
  for the widened copy. Run these tests in the audit job environment.
- **FR-006**: Document building agents after reviewed source changes, recording
  the baseline with the pinned version, and committing both generated artifacts.

### Key Entities

- Allowlist: source tool grants keyed by role.
- Baseline: scanner-generated version 1 grants and dangerous chains per agent;
  excludes prompts and descriptions.
- Audit finding: rule, agent and tools identifying a dangerous chain.

## Success Criteria

- **SC-001**: All nine existing roles pass with recorded grants.
- **SC-002**: Adding WebFetch to the builder fails and identifies its chain.
- **SC-003**: Agent or tool drift is detected locally without a scanner install.
- **SC-004**: Maintainers can reproduce reviewed grants using the documented loop.

## Assumptions

- Issue #20's generator and golden tests are available and reused unchanged.
- Binding issue notes resolve spec section 7's proposal wording: the recorded
  baseline is the proposal; no separate allowlist proposal mechanism is built.
- Use the released PyPI package if available, otherwise the same release's git
  install spec. The baseline is reviewed source, not proof of owner approval.
- Optional real-tool tests are the explicitly requested exception to offline
  fake-only tests. They make no network calls and skip only for an absent CLI.

## Deferred

None within S1. Runtime traces, MCP drift and agent-surface gates remain in their
existing adapters and other issues.
