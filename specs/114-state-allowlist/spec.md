# Feature Specification: Generic writer allowlists

**Feature Branch**: `114-state-allowlist`
**Created**: 2026-09-29
**Status**: Ready for implementation
**Input**: Issue #114, generic state set and event write only an allowlist.

## User Scenarios & Testing

### User Story 1 - Keep trusted state producer-owned (Priority: P1)

An owner can tune supported settings and annotate existing items without allowing a seat
using generic commands to manufacture evidence consumed by guards or sweeps.

**Independent Test**: Set supported settings and notes, then attempt trusted and unknown
paths and verify refusal without a state or event change.

**Acceptance Scenarios**:

1. Given any key outside the allowlist, when `wuwei state set` runs, then it exits 1
   naming the dedicated command, or saying it is written by its dedicated command.
2. Given an unapproved day, setting `cap` or `seat_policy` succeeds; after approval these
   settings remain frozen. An existing item's `note` remains editable.
3. Given a parent replacement, nested unknown key, or callback changing producer state,
   the generic writer refuses. Dedicated producers retain their existing behavior.

### User Story 2 - Keep trusted events producer-owned (Priority: P1)

An owner can append a free note, but cannot manufacture trusted event evidence.

**Independent Test**: Append a note, then try trusted and unknown kinds without appending.

**Acceptance Scenarios**:

1. Given a trusted event kind, when `wuwei event` runs, then it exits 1 with producer guidance.
2. Given an unknown kind, the same refusal applies by default.
3. Given a note event, it is appended with the shared clock and read-only file mode.

### User Story 3 - Prevent trust-boundary regression (Priority: P1)

A maintainer gets a failing regression test if readers gain trust in generically writable data.

**Independent Test**: Enumerate reader keys and event kinds from repository source and
exercise their generic command paths, including prefixes and nested item keys.

**Acceptance Scenarios**:

1. Every state key and event kind read by guards, sweeps and policies is enumerated by a
   source-driven test. Trusted evidence is refused through generic commands.
2. The explicitly permitted owner settings are tested separately with the approval freeze.
3. State and event files remain mode 0444 after writes and failures.

### Edge Cases

Unknown keys, no-op writes, wholesale item replacements, item creation via note, invalid
JSON, corrupt state, concurrent writers, midnight rollover, and post-approval edits.

## Requirements

### Functional Requirements

- **FR-001**: Generic state writes MUST allow only pre-approval `cap`, pre-approval
  `seat_policy` (including nested policy values), and existing item `note`.
- **FR-002**: Generic events MUST allow only `note`; unknown kinds MUST be denied.
- **FR-003**: Refusals MUST exit 1 and identify the producer where known, with generic
  dedicated-command guidance otherwise. Invalid allowed input and I/O errors retain exit 2.
- **FR-004**: Dedicated producers MUST retain shared locking, validation and atomic writes.
- **FR-005**: Tests MUST enumerate reader keys/kinds from source and protect the default denial.
- **FR-006**: Read-only file anchors and design section 9.1 MUST remain intact. Same-uid
  direct file writes remain the documented residual; this does not authenticate owner actions.

### Key Entities

- Day state: owner settings, existing item notes, and producer-owned records.
- Event: a timestamped note or an event emitted by a dedicated producer.

## Success Criteria

- **SC-001**: All non-allowlisted generic writes are refused without altering stored evidence.
- **SC-002**: Every current trusted reader key/kind is covered by source-driven regression checks.
- **SC-003**: Existing producer and full regression suites pass; file modes remain 0444.

## Assumptions

- The issue's allowlist direction supersedes the older pre-flight instruction to add RESERVED keys.
- No additional generic owner settings are documented in docs/specs or templates. `envelope`
  is produced by plan approval and is not generically tunable.
- `cap` and `seat_policy` retain the existing post-approval freeze. Item notes cannot create items.
- `note` is the sole free event kind. Former arbitrary kinds such as `started` require a producer.
- This worktree already contains the prerequisite guards and writer helpers from main.
- Test fixtures that need evidence without an existing public producer use the internal producer
  writer, never the generic API. Malformed fixture states still exercise validation directly.

## Deferred

Public producers absent from main for PR-set registration and some item/evidence metadata
remain separate feature work. This issue closes their generic write paths and uses the existing
internal producer writer for fixture setup; it does not invent new evidence verification flows.
