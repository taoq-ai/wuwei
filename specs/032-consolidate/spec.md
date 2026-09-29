# Feature Specification: Consolidation

**Issue**: #32
**Date**: 2026-09-29

## User Scenarios & Testing

### User Story 1: Weekly review (P1)

The owner runs `/wuwei consolidate` weekly to find stale summaries, contradictions, near-duplicates, and archive candidates. Clean review exits 0, findings exit 1, and unreadable evidence exits 2 with a reason.

### User Story 2: Safe folding (P1)

The owner folds a near-duplicate through a proposal naming a live survivor. Memory and charters are snapshotted before the fold. The retired note remains intact in the archive.

### User Story 3: Day archive (P1)

The owner runs consolidation to move expired days into `archive/`. Given 35 consecutive day directories and a 30-day retention window, five move and the index still lists all 35 report summaries. A seat's raw move or removal of a day directory is refused.

## Requirements

- FR-002: Report stale summaries, potential contradictions, near-duplicates and note archive candidates.
- FR-003: Snapshot memory and charters before a fold, require a live survivor, and preserve the full retired note.
- FR-004: Archive expired days through a dedicated CLI producer, rebuild the index, and commit protected changes using the promotion trailer path.
- FR-005: Document weekly scheduling as an owner step, without a new daemon.
- FR-006: Make the comparison threshold and day retention configurable.

## Success Criteria

- SC-001: The 35-day scenario moves five days and keeps 35 indexed summary lines.
- SC-002: Every fold has a readable pre-fold snapshot and an archived source.

## Assumptions

- A day moves when it is more than 30 days old. The current day never moves.
- Text similarity surfaces near-duplicate candidates for owner review; a proposal chooses the authoritative survivor.
- Contradiction detection surfaces candidate conflicts, with semantic judgment left to the owner.

## Deferred

- Automatic weekly scheduling uses the owner's task scheduler or existing sweep cadence.
