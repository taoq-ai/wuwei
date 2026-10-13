# Feature Specification: Clear Blocked none notes and explain owner cards

**Feature Branch**: `972-blocked-none`
**Created**: 2026-10-13
**Status**: Ready for implementation
**Input**: GitHub issue #972, IDENTITY-QUARANTINE-REVIEW field case on 0.32.0.

## User Scenarios & Testing

### User Story 1 - Builder can report no blocker with a note (Priority: P1)

A builder can write `Blocked: none. The live phase reads "implement", but the brief forbids production code this run, so implementation waits for the owner.` without creating an owner escalation card.

**Independent Test**: Record that exact value in a stopped builder's retro and ask for the next step.

**Acceptance Scenarios**:

1. Given a stopped builder, when its latest Blocked value begins with `none.` followed by a note, then the next step proceeds without a Blocked owner card.
2. Given a stopped builder, when its latest Blocked value begins with `none,` or `none;` followed by a note, then the next step proceeds without a Blocked owner card.
3. Given a substantive Blocked value, when the next step runs, then it still requests the owner's decision.

### User Story 2 - Owner card replay explains exact wording (Priority: P1)

An owner who answered a reworded question can see why a repeated command still asks for the same card.

**Independent Test**: Record a Yes on a reworded version of the card, then rerun the blocked build step.

**Acceptance Scenarios**:

1. Given no matching answer for a blocked builder card, when `build next` is rerun, then its reason explicitly says to ask that card verbatim and includes the exact card.
2. Given a matching Yes answer, when the same step is rerun, then the existing Yes path continues.

### Edge Cases

- `none` is matched case insensitively after trimming surrounding whitespace.
- `nonetheless`, `none needed`, and `none:` do not match the specified `none` punctuation rule.
- The explanatory suffix may be empty after one of the three accepted punctuation marks.

## Requirements

### Functional Requirements

- **FR-001**: A stopped builder's Blocked value equal to `none` or beginning with `none.` , `none,` or `none;`, case insensitively, MUST count as no blocker for all consumers of the blocked decision.
- **FR-002**: A Blocked value outside that rule MUST keep the existing escalation behavior.
- **FR-003**: When the blocked card has no matching recorded answer, the command's reason MUST instruct the caller to ask the included card verbatim.
- **FR-004**: Matching Yes and No answers MUST keep their existing effects.

## Success Criteria

- **SC-001**: The field case and all three punctuation variants proceed without an owner escalation.
- **SC-002**: Replaying a blocked build step after a reworded Yes presents the exact card and a verbatim instruction; the affected offline tests pass.

## Assumptions

- The rest of a `none` value remains in the recorded retro field. Surfacing it elsewhere is optional because the issue says it can surface as a note, and this feature does not add a new note channel.
- The three punctuation marks must immediately follow `none`. Other separators retain the existing blocker interpretation.
- The verbatim instruction applies to every unanswered blocked builder card, including the first presentation, because the replay path has no reliable way to distinguish an unrecorded reworded answer from no answer.
- No owner question is required under AGENTS.md; these choices follow the reported field case and the shortest shared fix.
