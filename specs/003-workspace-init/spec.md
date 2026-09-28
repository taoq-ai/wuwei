# Feature Specification: Workspace initialization and configuration

**Feature Branch**: `003-workspace-init`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: GitHub issue #3, dependent on #2.

## User Scenarios & Testing

### User Story 1 - Initialize a workspace (Priority: P1)

An owner starts a body of work with a reusable workspace skeleton.
**Independent Test**: Initialize an empty directory and inspect the resulting files.
**Acceptance Scenarios**:
1. Given an empty directory, when `wuwei init` runs, the section 3.3 layout exists and `wuwei config check` exits 0.
2. Given a target path with spaces, initialization creates the same skeleton there.
3. Given an existing `.wuwei/`, initialization exits 1 without modifying it.

### User Story 2 - Check configuration (Priority: P1)

An owner can correct configuration mistakes before running work.
**Independent Test**: Check a manually created workspace with valid and invalid configuration.
**Acceptance Scenarios**:
1. Given a typo'd key, checking exits 1 naming the key and its line.
2. Given valid supported fields, checking exits 0 and omitted settings receive defaults.
3. Given wrong types, invalid ranges, or an unsupported profile, checking exits 1 with the field and expected value.
4. Given unreadable or missing workspace/configuration, checking exits 2 with a reason.

### User Story 3 - Locate workspace and day (Priority: P2)

Later commands share one workspace and day resolution contract.
**Independent Test**: Resolve from nested directories and with environment overrides.
**Acceptance Scenarios**:
1. The nearest ancestor containing `.wuwei/` is selected unless explicitly overridden.
2. A deterministic clock override selects the expected day without creating directories.
3. An invalid workspace override never falls back to another workspace.

### Edge Cases

Existing files and dangling symlinks named `.wuwei` must not be overwritten.
Malformed TOML and unknown nested fields are findings; filesystem failures are could-not-run.
Boolean values are not integers. Defaults are independent between loads.

## Requirements

- FR-001: Copy the workspace skeleton and commented configuration defaults from shipped templates.
- FR-002: Include charters, memory spine/index/changelog/notes, days and archive; do not create a dated day.
- FR-003: Validate all known fields, nested tables and list elements; reject unknown fields.
- FR-004: Support owner, repos, cap, host, profile, boundary, environments, outward and adapters.
- FR-005: Name the config file and unknown key in findings; include the source line when the heuristic can locate it.
- FR-006: Share workspace discovery, clock, day path and config loading across commands.
- FR-007: Preserve the existing three-state exit contract and command discovery.

## Success Criteria

- SC-001: A newly initialized workspace passes checking without edits.
- SC-002: Typo scenarios consistently identify the offending key and line.
- SC-003: Repeated initialization preserves every existing workspace file.
- SC-004: All supported settings and error categories have offline automated checks.

## Assumptions

- Workspace root means the directory containing `.wuwei`; `WUWEI_WORKSPACE` points to that root, absolute or relative to cwd. Explicit override must contain `.wuwei`.
- `WUWEI_NOW` uses an ISO datetime; its represented calendar date is used, otherwise local now. Offset-free overrides use the local timezone, so the clock always returns an aware datetime. Helpers do not create directories.
- `cap = 1`, `host.free_memory_mb = 1024`, `host.seats = 1`; cap and seats are positive integers, memory is nonnegative. These conservative defaults are policy choices, not host measurements.
- Owner name and pronouns are strings, initially empty. Repos are table arrays with name/path strings, default_branch `main`, fast_checks string arrays.
- Boundary and environments are maps of user-defined names to descriptive strings. Outward max_length is a channel-name map of positive integers. Dynamic map names are data, not schema keys.
- Outward patterns and banned_characters are string arrays, initially empty. Pattern compilation and lint enforcement belong to guards.
- All fixed schema fields have defaults; no real repository or adapter availability check is required here.
- Syntax/encoding/schema errors are findings (1); discovery and I/O failures are could-not-run (2).

## Deferred

Adapter implementation validation belongs to #5. State/day creation, outward guards, scanner integration, upgrades and archiving remain with their later features.
