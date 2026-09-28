# Feature Specification: Versioned charter upgrade

**Feature Branch**: `040-charter-upgrade`
**Created**: 2026-09-28
**Status**: Ready
**Input**: GitHub issue #40, versioned charters and `wuwei init --upgrade`

## User Scenarios & Testing

### User Story 1 - Upgrade an existing workspace (Priority: P1)

An owner upgrades a workspace created by the previous minor release and sees the configuration additions and charter overrides that need review.

**Independent Test**: Run upgrade against a fixture made from the older workspace template, with a local charter override.

**Acceptance Scenarios**:

1. Given a workspace from the previous minor version, when the owner runs `wuwei init --upgrade`, then upgrade succeeds, adds current configuration keys with defaults and template comments, preserves owner values, refreshes the executable pointer, and lists local charters whose base version changed.
2. Given an already upgraded workspace, when upgrade runs again, then files do not change and no migration is reported.

### User Story 2 - Preview and safely refuse (Priority: P1)

An owner previews the changes and receives an actionable error for content that cannot be migrated safely.

**Acceptance Scenarios**:

1. Given an older workspace, when the owner runs `wuwei init --upgrade --dry-run`, then the command prints the intended changes without writing files.
2. Given an unknown configuration key, when upgrade runs, then it refuses with the key and line number and changes no files.
3. Given unreadable or malformed configuration or charter input, when upgrade runs, then it exits 2 with a reason and changes no files.

### Edge Cases

- Upgrade requires an existing `.wuwei` directory at the chosen path.
- Existing charter overrides remain byte for byte intact.
- A local charter with no readable version stamp is reported for review.
- A missing executable pointer is created by upgrade.

## Requirements

### Functional Requirements

- **FR-001**: `init --upgrade` MUST migrate an existing workspace configuration to the current template schema, retaining every owner value and comment.
- **FR-002**: Missing configuration keys MUST receive template defaults and comments in their proper TOML tables.
- **FR-003**: Upgrade MUST reject unknown keys with their key path and source line, without modifying workspace files.
- **FR-004**: Upgrade MUST atomically update changed configuration and the executable pointer to the running plugin's `bin/wuwei`.
- **FR-005**: Upgrade MUST list local charter overrides whose version differs from the shipped base version and MUST leave them untouched.
- **FR-006**: Dry run MUST print the plan and make no changes. A repeated upgrade MUST be idempotent.
- **FR-007**: Failures to read or write needed files MUST exit 2 with a reason.

## Success Criteria

- **SC-001**: A fixture based on the previous minor workspace template upgrades successfully and passes `config check`.
- **SC-002**: Changed charter overrides are named in output and retain their original bytes.
- **SC-003**: Dry run and repeat runs produce no file changes.

## Assumptions

- The charter frontmatter `version:` is the base-version comparison marker. A missing local stamp needs owner review.
- Workspace configuration has no explicit schema version; absent current template keys identify additions.
- Owner-set values, including old defaults written in their workspace, remain owner values.
- The status line command is emitted again so the owner can apply it to Claude Code settings; the stored executable pointer serves installed git hooks.

## Deferred

- Automatic three-way merge of charter overrides is outside this issue.
