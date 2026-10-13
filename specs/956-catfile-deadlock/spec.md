# Feature Specification: Prevent git cat-file batch deadlock

**Feature Branch**: `956-catfile-deadlock`
**Created**: 2026-10-13
**Status**: Ready
**Input**: GitHub issue #956

## User Scenarios & Testing

### User Story 1 - Inspect a large development checkout (Priority: P1)

As a WUWEI user, I can start a session, initialize, or run doctor against a plugin git checkout with many tracked files without the integrity read hanging.

**Independent Test**: Read a committed tree whose cat-file request and response each exceed 64 KiB and compare every blob with the committed content.

**Acceptance Scenarios**:

1. Given a checkout with a batch request and output each over 64 KiB, when `read_tree` reads `HEAD`, then it returns all tracked blobs within its existing timeout.
2. Given a small checkout, when `read_tree` reads `HEAD`, then its existing content and error behavior remain intact.

### Edge Cases

- Empty trees return an empty dictionary without starting cat-file.
- Git failures and timeouts retain the existing exit 2 result.

## Requirements

### Functional Requirements

- **FR-001**: A git batch read MUST provide request bytes through a temporary file so stdin does not contend with captured output pipes.
- **FR-002**: The existing subprocess timeout, stdout and stderr capture, and error conversion MUST remain in effect.
- **FR-003**: The temporary file MUST close after subprocess completion or failure.
- **FR-004**: Runtime code MUST use only the Python 3.11 standard library.

## Success Criteria

- **SC-001**: The large-tree regression reads every committed blob with request and output each above 64 KiB.
- **SC-002**: Existing `read_tree` and other tests importing the changed adapter pass.

## Assumptions

- The issue's field stacks identify simultaneous stdin and stdout pipe writes as the macOS failure mode.
- A temporary file is seeked to byte zero before the subprocess starts.
- Existing 30 second timeout remains the desired limit.
- No design spec wording change is needed for this adapter fix.
