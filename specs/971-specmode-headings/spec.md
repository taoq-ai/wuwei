# Feature Specification: Spec-mode heading forms

**Feature Branch**: `971-specmode-headings`  
**Created**: 2026-10-13  
**Status**: Ready  
**Input**: GitHub issue #971, seen on IDENTITY-QUARANTINE-REVIEW.

## User Scenarios & Testing

### User Story 1 - Clarification section with a suffix (Priority: P1)

A builder records owner rulings under `## Clarifications (section 12)`. Spec mode recognizes the clarify step so work can continue.

**Independent Test**: A spec with that heading passes the clarify check; a spec with only `## Notes` still reports a missing clarification section.

### User Story 2 - Governing label variants (Priority: P1)

A builder names a document with `**Governing**:`, `**Governing:**`, or `- Governing:`. The analyze and gate paths resolve that document and require its governed check.

**Independent Test**: Both paths resolve each label while a plain `Governing:` label and an item-level `governed_by` keep working.

### Edge Cases

- A body line merely mentioning Clarifications must not count as a section heading.
- A missing or invalid governing reference must keep the existing refusal behavior.

## Requirements

### Functional Requirements

- **FR-001**: The clarify step MUST accept a level-two `Clarifications` heading with trailing text, including the reported `(section 12)` form.
- **FR-002**: The governing lookup MUST accept `**Governing**:`, `**Governing:**`, and `- Governing:` as well as `Governing:` in `spec.md`.
- **FR-003**: Item-level `governed_by` MUST continue to take precedence over the spec line.
- **FR-004**: Missing clarification sections and invalid governing references MUST retain their existing refusals.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The reported heading and governing label forms are recognized in automated regression tests.
- **SC-002**: Every explicit test file importing the changed module passes.

## Clarifications

- 2026-10-13: Accept the field forms directly, since this lets builders keep valid Markdown while preserving the existing checks.

## Assumptions

- Trailing text means text after the `Clarifications` word on the same level-two heading, with a separating space or tab. A different word such as `ClarificationsExtra` is not the same heading.
- Governing labels start at the beginning of a line, with an optional `- ` bullet. Bold labels place the colon either before or after the closing `**`.
- Owner cards are not needed because no owner decision is required for these parser changes.
