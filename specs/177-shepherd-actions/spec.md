# Feature Specification: Shepherd PR Actions

**Feature Branch**: `177-shepherd-actions`  
**Created**: 2026-09-29  
**Status**: Ready

## User Scenarios & Testing

### User Story 1 - Resolve a conflicted PR (Priority: P1)

Given an owned conflicted PR, `pr act` returns a rebase step tied to its item worktree. After the step succeeds, the PR action is recorded done.

### User Story 2 - Open a fix round (Priority: P1)

Given red CI or a review fix request, `pr act` opens a builder fix round with the measured failure or review feedback. The item returns to its gates after the round.

### User Story 3 - Answer review threads (Priority: P1)

Given an unanswered question, `pr act` creates a reply draft or sends a reply when the outward tier allows. A scope disagreement creates an owner decision record.

### Edge Cases

- Missing item links, worktrees, port evidence, or tools fail closed with a reason.
- Repeated actions do not silently duplicate an existing fix round or reply.
- An unknown build item exits 2.

## Requirements

- **FR-001**: PR actions use fresh code host evidence and the recorded item link.
- **FR-002**: Conflict resolution runs through the VCS port, configured fast checks and push guards, then records completion only on success.
- **FR-003**: Red CI and review fix requests start a build next round with source feedback.
- **FR-004**: Unanswered threads use outward tiers and preserve drafts when send is not permitted.
- **FR-005**: Scope disputes create a decision record for the owner.
- **FR-006**: Unknown build items exit 2.

## Success Criteria

- Each acceptance scenario passes using recorded host payloads and fake ports.
- The complete test suite passes.
- No external tool or network is required in tests.

## Assumptions

- A conflicting rebase may need human conflict resolution; the planner executes the returned step and retries after resolving files.
- Unknown review prose is a question draft. Explicit scope change or disagreement language routes to a decision.

## Deferred

- General semantic review classification and a broader draft manager belong to later work; this feature uses conservative routing and a local reply draft.
