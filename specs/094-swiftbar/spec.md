# Feature Specification: Optional menu bar indicator

**Feature Branch**: `094-swiftbar`
**Created**: 2026-09-28
**Status**: Ready
**Input**: GitHub issue #94

## User Scenarios & Testing

### User Story 1 - See current attention level (Priority: P1)

A macOS owner with SwiftBar can see whether the day has pages, nudges, or neither while WUWEI is in the background.

**Independent Test**: Render the menu from representative status snapshots.

**Acceptance Scenarios**:

1. **Given** one page, **when** the plugin renders, **then** it shows a red mark and lists `Pages: 1` in its menu.
2. **Given** no pages and one nudge, **when** the plugin renders, **then** it shows an amber mark and lists `Nudges: 1`.
3. **Given** no pages or nudges, **when** the plugin renders, **then** it shows a green mark and both zero counts.
4. **Given** unreadable or unmeasured status, **when** the plugin renders, **then** it shows a grey unknown mark, never green.

### User Story 2 - Find installation instructions (Priority: P2)

A macOS owner can request instructions for placing the optional plugin in SwiftBar.

**Independent Test**: Request menu bar instructions and inspect the response without changing workspace files.

**Acceptance Scenarios**:

1. **Given** macOS, **when** the owner requests menu bar setup, **then** the response identifies the shipped plugin and how to set its workspace.
2. **Given** another operating system, **when** the owner requests menu bar setup, **then** no menu bar integration is offered.

### Edge Cases

- Missing workspace, executable, status command, or malformed status produce unknown with a reason.
- A status count must be a nonnegative integer; invalid counts cannot produce green.
- When SwiftBar is absent, the optional plugin does not run and no integration is active.

## Requirements

### Functional Requirements

- **FR-001**: The optional indicator MUST display red for one or more pages, amber for nudges without pages, and green only for a measured zero and zero snapshot.
- **FR-002**: The indicator MUST show page and nudge counts in menu lines.
- **FR-003**: An unreadable, invalid, or unmeasured status MUST show a grey unknown mark and a reason.
- **FR-004**: Setup instructions MUST be available on macOS without changing workspace state.
- **FR-005**: Other operating systems and systems without SwiftBar MUST have no active menu bar integration.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All four measured and unmeasured status scenarios render the expected mark and counts in automated checks.
- **SC-002**: No invalid or unreadable snapshot renders green in automated checks.
- **SC-003**: Setup instructions leave workspace files unchanged.

## Assumptions

- The existing status snapshot supplies counts, not individual page or nudge descriptions; listing the counts satisfies the menu requirement.
- Owners install SwiftBar separately and choose its plugin folder. Setup provides instructions and does not install an app.
- The workspace path is supplied to the plugin through `WUWEI_WORKSPACE` in its SwiftBar environment or by editing the copied script.
- The existing `.wuwei/executable` pointer locates `bin/wuwei` after workspace initialization.

## Deferred

- Individual alert descriptions require a richer status contract in a separate issue.
