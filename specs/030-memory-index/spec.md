# Feature Specification: Memory index and payload

**Feature Branch**: `030-memory-index`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: Issue #30 and amendment dated 2026-09-28.

## User Scenarios & Testing

### User Story 1: Browse current memory (Priority: P1)

A seat runs `wuwei index` to get a stable summary of active notes and past days.

**Acceptance Scenarios**:

1. Given a note body change, when the index runs again, then its note line updates and no other line changes.
2. Given an invalid note, when the index runs, then it writes `INVALID <slug>: <reason>` and exits 1.
3. Given more than `memory.max_notes` active notes, when the index runs, then it writes every line, names the overflow count, and exits 1.

### User Story 2: Load session memory (Priority: P1)

A seat runs `wuwei payload` to see the complete spine, generated index and today's state, followed by byte and token estimates.

**Acceptance Scenarios**:

1. Given a valid workspace, when payload runs, then it prints those three sources and a final size line.
2. Given an unreadable or malformed source, when payload runs, then it exits 2 with a reason.

## Requirements

- FR-001: Index entries include active note slug, type, summary and a token estimate based on note content.
- FR-002: Past day entries include date and the first report line, or `no report`.
- FR-003: Entries have deterministic sorted order; writes replace the index atomically.
- FR-004: Invalid notes remain visible in the index and return a finding.
- FR-005: Active note count exceeding the configured maximum returns a finding while retaining all entries.
- FR-006: Payload returns spine, index and today's state, plus byte and token sizes; the CLI prints them.
- FR-007: Index refuses symlinked day directories and reports, treats undecodable notes and reports as findings, and requires a valid notes directory and config.

## Success Criteria

- SC-001: A body-only change alters exactly one index line.
- SC-002: Repeated runs on an unchanged workspace produce identical index bytes.
- SC-003: Invalid notes and capacity overflow never disappear from the index.
- SC-004: The full repository test suite passes.

## Assumptions

- Archived notes are excluded from the active index. Invalid notes count as findings but not as active notes.
- Past days are valid date directories before today, including archived day directories when present.
- Missing reports show `no report`; an existing empty report also shows `no report`.
- The token estimate is ceiling of character count divided by four, using the entire note for index entries.
- Payload reads the existing index and does not regenerate it. Today's absent state uses the state reader's defaults.
- A missing spine or index is an operational error for payload. An absent config is an operational error for index.

## Deferred

- SessionStart hook wiring: issue #15.
- Archive selection: issue #81.
- Last promote line and its ledger contract: issue #81.
