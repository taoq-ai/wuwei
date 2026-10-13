# Feature Specification: Measurement Handoff Gates

**Issue**: #866  
**Created**: 2026-10-13  
**Status**: Ready

## User Scenarios & Testing

### Measure without a code diff (Priority: P1)

A lead marks a zero-path production measurement as measure. A seat records its findings and scratch artifacts. The item needs no specification or code fast checks.

**Acceptance scenarios**:

1. Given BACKFILL-EVIDENCE with kind measure and no paths, when dispatched, then its seat brief says the spec is skipped.
2. Given a completed zero-diff measurement, when the seat stops, then no build check runs.
3. Given a zero-diff measurement without lead risk flags, when the gate is dispatched, then one quality seat reviews its numbers and existing scratch artifacts.
4. Given a measurement on an existing PR branch, gate tiering compares its worktree with the builder's starting HEAD.
5. Given a finished measurement, the day report lists its current verdict and workspace-relative verdict file.

### Preserve code gates (Priority: P2)

Code changes continue through their existing tier and gate rules.

**Acceptance scenario**: Given a build item with a changed code path, its normal floor and gate roles still apply.

## Requirements

- **FR-001**: A measure candidate has no changed paths and is admitted with kind measure.
- **FR-002**: A measure item skips the specification steps and configured fast checks.
- **FR-003**: A measure item with zero diff and no risk flags receives one quality gate regardless of repository floor. Trust or agent surface flags retain the normal standard gates.
- **FR-004**: The quality gate brief cites the handoff by its day state file and only existing, resolved workspace artifact paths. It does not inline the handoff text.
- **FR-005**: A measure item that produces a code diff must not silently use the zero-diff gate exception.
- **FR-006**: A measure item completes after its quality PASS without opening a PR or a polish build.
- **FR-007**: A completed measurement is absent from close's open work and report's Open and Carry sections.
- **FR-008**: The measurement builder brief names one scratch destination, and the gate brief retains absolute handoff paths when they resolve inside the workspace.
- **FR-009**: A completed measurement action and the day report identify its gate verdict file.

## Success Criteria

- **SC-001**: The BACKFILL-EVIDENCE scenario produces zero build check actions and no more than one gate seat.
- **SC-002**: Its quality brief identifies both the handoff content and scratch outputs.
- **SC-003**: A code-changing build item keeps its existing gate set.

## Assumptions

- A measurement uses the existing builder seat as its authoring seat to avoid a new role or subsystem. Its final result text is the handoff recorded by the build loop.
- Measurement evidence is in the builder result under the day's `state.json`. Scratch paths are cited only when they exist in the workspace. Relative and absolute paths inside the workspace are rendered as resolved, workspace-relative artifact references. The builder may write elsewhere in the workspace and name those outputs in its handoff.
- A measurement is compared with its recorded starting HEAD and worktree status so an unchanged pre-existing PR branch diff does not park it. If the starting HEAD is unavailable, use the merge-base diff. A changed HEAD or dirty worktree returns to the seat for correction.
- The completion write uses the existing `state.write` event kind.
- Proposed design wording for the owner: A zero-diff measurement skips specification and fast checks; its handoff can receive one quality review of the evidence.

## Clarifications

No open questions. The recommended choices are recorded under Assumptions.
