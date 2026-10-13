# Feature Specification: Ruling IDs at token boundaries

**Feature Branch**: `941-ruling-lint` | **Created**: 2026-10-13 | **Status**: Ready

**Input**: Issue #941, brief refusal for item IDs and worktree paths.

## User Scenarios & Testing

### User Story 1 - Brief an item with a D-like substring (Priority: P1)

**Independent Test**: Brief `CID-MAPPING-VIEW-API` with a body naming `worktrees/WS-READ-ROUTE-4734`; the brief file exists and contains the body.

**Acceptance Scenarios**:

1. Given that item and path, when a builder brief is written, then no ruling is inferred from either substring.
2. Given a standalone unresolved ruling ID, when a brief is written, then it is still refused.

### User Story 2 - Explain a missing outbound body file (Priority: P2)

**Independent Test**: An outward send with `--body-file` naming an absent file is refused with a direction to write it in a separate command first.

## Requirements

- **FR-001**: Ruling IDs are recognized only when the preceding character is neither a letter, digit, hyphen, slash nor underscore.
- **FR-002**: A genuine unresolved ruling ID still refuses the brief.
- **FR-003**: A missing outbound body file refusal says the file does not exist and to write it in a separate command first.

## Success Criteria

- **SC-001**: The field case writes a brief without renaming its item or hiding its path.
- **SC-002**: A missing body file refusal identifies the absent file before any send.

## Assumptions

- The design document is owner-only. The requested token boundary and one-line file guidance live here.
- The outbound guard can determine a missing file without executing the compound command. An unreadable existing file retains the current generic message.
