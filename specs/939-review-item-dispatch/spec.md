# Feature Specification: Review Item Dispatch

**Issue**: #939  
**Created**: 2026-10-13  
**Status**: Ready

## User Scenarios & Testing

### Review an existing PR (Priority: P1)

A lead marks a verdict-only candidate as review and names its PR and sentinel role. The planner sends that role a gate brief at the PR head. No builder or specification step is created.

**Acceptance scenarios**:

1. Given a review candidate for an open PR with no paths, when it is approved and dispatched, then the next seat is its named sentinel at the PR head.
2. Given a review candidate, when its sentinel reports PASS or a named FIX finding, then the item finishes without a builder, build checks, or a PR raising step. ESCALATE reaches the owner card and PARK parks the item.
3. Given an unavailable or changed PR head, when the planner dispatches, then it does not brief a verdict against another head.
4. Given a stale review worktree, when its HEAD is an ancestor of the PR head, then the planner offers a fast-forward command. If it is ahead or diverged, the planner refuses and names the local commit options.
5. Given a finished review while its PR remains open, the day report lists the verdict and its workspace-relative file, and close does not report an unclaimed pushed branch.

### Preserve build candidates (Priority: P2)

Candidates without a kind continue through the existing builder flow.

**Acceptance scenario**: Given an ordinary candidate without kind, approval and dispatch still create a builder brief with the configured spec mode.

## Requirements

- **FR-001**: Accept only build, review, or measure as a candidate kind, defaulting to build when absent.
- **FR-002**: A review candidate must name an existing PR and one sentinel role.
- **FR-003**: Dispatch a review candidate to that sentinel with a brief anchored to the PR head, never to a builder.
- **FR-004**: A review item uses the existing one-role gate decision and receipt path. PASS and FIX complete it; ESCALATE and PARK retain their gate handling.
- **FR-006**: A fork PR, or a PR whose head repository is unknown, is refused before checkout.
- **FR-007**: `plan add` and `plan set` can correct an omitted kind before the first seat, with a review PR and role when applicable.
- **FR-008**: A completed review action and the day report identify its gate verdict file.
- **FR-009**: A non-review candidate may carry `pr: null` as an absent PR.
- **FR-005**: The lead charter must explain the kind field.

## Success Criteria

- **SC-001**: The PR-3168-DELTA scenario produces one sentinel brief and zero builder briefs.
- **SC-002**: The review brief names the current PR head and has no spec step.
- **SC-003**: Existing candidates without kind follow the same build route as before.

## Assumptions

- `review` requires `pr` in owner/repo#number form and `review_role` in arch, quality, security, or goal. The named role gets a fresh sentinel seat.
- A review item uses a clean worktree on a branch in the PR repository. Fork PRs and unknown head repositories are refused. Checkout and briefing are separate steps so an adopted path is recorded before briefing. A target missing from the cached PR listing is read directly. The brief and receipt recheck the live PR head. A stale worktree gets a fast-forward command only when its HEAD is an ancestor of the PR head; if ancestry is unavailable, it is refused.
- The review starts in the gate phase after admission. An owner can correct kind before the first seat with `plan set`; that change uses the existing Owner step card.
- A completed review item has no ordinary PR ping, shepherd, or tracker duty.
- The review verdict is the deliverable. PASS and FIX mark the item done; ESCALATE and PARK use the normal gate decision. The review item does not raise or merge the PR.
- Proposed design wording for the owner: A review candidate names its existing PR and sentinel role; it runs only that gate at the PR head and completes on the verdict.

## Clarifications

No open questions. The recommended choices are recorded under Assumptions.
