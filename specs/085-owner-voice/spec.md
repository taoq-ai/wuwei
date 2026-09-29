# Feature Specification: Owner voice

**Feature Branch**: `085-owner-voice`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #85 and design section 4.8.

## User Scenarios & Testing

### User Story 1 - Protected owner profile (Priority: P1)

The owner keeps an audience-specific voice profile in the workspace. Agents cannot edit it directly; proposals go through the existing promotion gate.

**Independent Test**: Tool writes to voice.md are refused, while a valid proposal lands through promote.

### User Story 2 - Learn from owner examples (Priority: P1)

The owner runs `wuwei voice learn` to generate reviewable proposals from the owner's own sent chat messages and PR comments. Other people's content and personal data never enter proposals or the repository.

**Independent Test**: Mixed-author adapter data produces only redacted owner exemplars. Missing chat adapter gives exit 2 and no files.

### User Story 3 - Audience lint (Priority: P1)

Outward text is checked against shared and audience rules for length, never phrases and required prefix, on top of existing outward lint.

**Independent Test**: The same text can pass review and fail an internal channel.

## Requirements

- **FR-001**: Protect `.wuwei/memory/voice.md` exactly as owner-controlled configuration is protected, including aliases and shell writes.
- **FR-001a**: New workspaces contain an empty voice profile with audience headings and no real exemplars.
- **FR-002**: `voice learn` reads configured sent chat channels and configured PR comment references through read-only adapters, accepts only configured owner handles, and writes redacted audience proposals into today's proposals directory.
- **FR-003**: No adapter or malformed response is exit 2 with no partial proposals.
- **FR-004**: Promote accepts valid voice proposals and records results in the existing ledger.
- **FR-005**: Outward lint applies shared and mapped audience mechanical voice rules and fails closed on malformed profile rules.
- **FR-006**: Repository files contain no real exemplars.

## Success Criteria

- Owner-only filtering, redaction, promotion, protection and per-audience lint pass automated tests.
- Missing chat adapter returns exit 2 without creating proposals.
- Full repository test suite passes.

## Assumptions

- Owner identifiers are listed in `owner.handles`. Chat sources map audience names to channel IDs under `voice.sources`; PR references under `voice.review_prs` use the `review` audience.
- Learning proposes only mechanical rules observable from examples and redacted exemplars. The owner fills in register, structure and preferred phrases at the morning gate.
- A missing voice profile leaves existing outward lint in force until the owner promotes a proposal.
