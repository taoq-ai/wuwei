# Feature Specification: Protected native seat attestation

**Feature Branch**: `codex/1258-native-attestation`
**Created**: 2026-10-27
**Status**: Specified
**Input**: Approved item 1258, full tier, goal G-2.

## Promise and acceptance in our words

A genuine native seat stop can attest its latest own report after protected records prove its parent launch, role and identity. Reuse existing report retention and preserve legacy behavior. Protect the native record root, report child recorded settings accurately, and keep ordinary owner answers unconfirmed.

Acceptance: match the first child metadata, fork boundary, parent call and result, requested role, native identity and canonical path. Reject every mismatch, inherited report, earlier replay, unreadable record and root escape. Existing write shapes stay refused and reads remain available. Preserve report versions, race claims, notification delivery, credentials and board identity. Child settings come from its own post-fork turn. Ordinary replies grant no ruling. Runtime stays within the approved 4,000 cap and the 111-line item budget.

## User Scenarios & Testing

### User Story 1: Trust a native seat report (P1)

The planner can use a native gate's verdict with the same report-proof standard as a legacy seat.

1. Given matching protected parent and child records, when SubagentStop supplies the latest own final report, then the canonical seat can stop and attest that report.
2. Given a mismatched launch, role, identity, final report or completion, when the stop arrives, then it remains unconfirmed.
3. Given a child turn after its fork, when the attestation records settings, then requested, parent, child-recorded and provider-resolved settings remain distinct.

### User Story 2: Preserve reports and their protection (P1)

The planner receives the latest valid report once through the existing store.

1. Given a native record write through an existing guarded route, when it targets the protected root, then it is refused.
2. Given repeated, corrected, notified or racing reports, when the planner calls or stops, then legacy delivery semantics hold.
3. Given ordinary native owner text, when hooks process it, then it grants no approval or ruling.

### Edge Cases

Malformed JSON, missing metadata, duplicate ordinals, missing payload types, inherited finals, symlink escapes, unreadable files, wrong call ids, UUID/path collisions, credential strings, missing child settings and delayed task completion.

## Requirements

- FR-001: Require first-record child identity and an increasing nonnegative ordinal sequence; exclude inherited records.
- FR-002: Match exactly one parent spawn call/result by call id, requested role and canonical child path before mapping the stop identity.
- FR-003: Require the last own assistant final report and agreement from any later completion record. The genuine stop supplies completion before that record exists.
- FR-004: Read only regular protected account-derived records; changing HOME cannot move the accepted root.
- FR-005: Extend every existing native edit, shell, wrapper and Windows path protection without changing shell parsing.
- FR-006: Preserve latest valid report selection, atomic claims, notifications, redaction and cross-session board identity.
- FR-007: Read child model and effort only from its own post-fork turn context, retaining an unmeasured provider model without supplied resolution.
- FR-008: Preserve legacy readers and ordinary owner-answer refusal. Add no configuration key, pending-seat framework or report store.

### Key Entities

Protected parent launch, protected child metadata and own rows, latest final report, optional later completion, existing kept report and notification.

## Success Criteria

- SC-001: Every specified negative proof case produces no attestation.
- SC-002: Genuine native proof records verified seat identity and the exact final report; ordinary IDs remain canonical, sensitive IDs use stable privacy keys.
- SC-003: Existing legacy report and guard checks pass unchanged, except documented native protection reasons.
- SC-004: Root runtime is at most 4,000 lines and this item adds at most 111 lines.

## Clarifications

- 2026-10-27: You approved the native fix and 4,000 runtime cap. Item 1260 remains separate.
- SubagentStop supplies completion; waiting for task_complete could block the callback that precedes it.
- Child-recorded settings do not prove provider resolution.

## Assumptions:

- The account's default native session root is the supported source, because it is observed and protected. A different supported root requires separate proof.
- Trusted lifecycle callbacks and harness-owned records share the existing legacy threat model. A measured lifecycle difference would overturn this.
- The existing report store can retain native identity through hashing, because its atomic and latest-valid behavior already handles races. A failing native case would overturn this.

## How this fails:

1. An inherited final or another parent's child produces a false PASS. Probe fork boundaries, call pairing and role/path mismatches first.
2. A transcript escape lets a seat forge proof. Probe edits, shell writes, wrappers, Windows spellings and symlink escapes.
3. A corrected or notified report disappears or repeats. Probe the real delivery consumer, latest versions and concurrent claims.

Rollback: Revert the feature and restore the prior trusted plugin artifact. Trust changes are handled separately by the planner.
