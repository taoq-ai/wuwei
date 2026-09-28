# Feature Specification: Adapter interfaces and registry

**Feature Branch**: `005-adapters`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #5, M0 Foundation; design sections 3.4 and 8, binding orchestrator notes.

## User Scenarios & Testing

### User Story 1 - Honest absent integrations (Priority: P1)

A gate or operator can call an integration without mistaking missing evidence or an
unperformed action for success.

**Independent Test**: Call every absent integration operation and inspect its result and event.

**Acceptance Scenarios**:

1. Given scanner `none`, when a gate asks for a scan, then the result is
   `unmeasured` (exit 2) and an event is written.
2. Given any measurement operation with `none`, when called, then exit 2 and
   reason `unmeasured` are returned and printed.
3. Given any action operation with `none`, when called, then exit 2 and
   reason `no adapter configured` are returned and printed, recording that nothing was done.
4. Given an event write failure, when an adapter is called, then it fails closed with
   exit 2 and an explanatory reason, never claiming that the event was recorded.

### User Story 2 - Validate adapter selection (Priority: P1)

An operator selects installed adapters and receives useful diagnostics for invalid selections.

**Independent Test**: Check valid and invalid adapter selections and load installed modules.

**Acceptance Scenarios**:

1. Given an unknown adapter name, when `wuwei config check` runs, then it exits 1,
   naming the key, known names and source line when known.
2. Given an installed adapter name, when selected, then the registry loads that module.
3. Given an unknown kind or a path-like adapter name, when loaded, then it is rejected.

### User Story 3 - Reliable workspace configuration (Priority: P2)

Repository entries cannot silently resolve missing paths to the current directory, and
leftover initialization staging directories are recognizable.

**Independent Test**: Validate missing, blank and duplicate repository fields and observe staging paths.

**Acceptance Scenarios**:

1. Given a repo without a nonblank name or path, config check exits 1 with
   `repos.N.name: required` or `repos.N.path: required`, including the line when known.
2. Given repeated repository names or resolved paths, config check exits 1 naming the duplicate entry.
3. Given workspace initialization, the staging directory begins with `.wuwei-init-`.

### Edge Cases

- Unknown module names, private files and path traversal cannot be loaded as adapters.
- Missing workspaces and event I/O failures remain exit 2.
- Events omit arguments, message text, server details and other potentially sensitive payloads.
- Multiple calls append separate events without changing existing day state.

## Requirements

- **FR-001**: Support tracker, chat, review_bot, runtime and scanner operations from design section 8.
- **FR-002**: Share a result containing exit, data and reason across all operations.
- **FR-003**: Discover installed implementations by kind and select from workspace configuration.
- **FR-004**: All `none` calls record adapter, kind, call, exit, reason and that no action occurred.
- **FR-005**: Invalid selections report actionable configuration findings.
- **FR-006**: Repository names and paths are required; names and resolved paths are unique.
- **FR-007**: Initialization staging paths have a recognizable prefix.

### Key Entities

- Adapter result: exit code, optional data, explanatory reason.
- Adapter event: existing day event envelope with operation metadata, never operation arguments.

## Success Criteria

- Every absent operation returns exit 2 with the specified reason and one event on successful I/O.
- All invalid adapter selections and invalid repository entries are rejected by config check.
- All shipped adapter modules satisfy their operation contract.
- The full offline test suite passes using the requested interpreter.

## Assumptions

- Actions return exit 2 with `no adapter configured`; an unsent message is not success.
- Measurements are review_bot score/open_findings, scanner audit/gate/traces/mcp,
  tracker history, and runtime status/result. Their reason is `unmeasured`.
- Runtime `claude` stays the configured default. Until #26, it is reserved and accepted
  by config validation but loading it raises an explicit unavailable error. Discovery lists
  only installed modules. Explicit runtime `none` is provided; no silent fallback occurs.
- Optional keyword-only `root` selects an event workspace; omitted uses existing discovery.
- No additional gates or external tools are built here; scanner acceptance uses the adapter boundary.
- Required repo fields reject missing, empty and whitespace-only strings; names use exact equality.
- Repo paths expand `~` and resolve relative to the workspace root, including symlinks.

## Deferred

- Claude and Codex runtime implementations: #26.
- Real tracker, chat, review bot and scanner integrations and consuming gates: their own issues.
