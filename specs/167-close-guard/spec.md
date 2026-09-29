# Feature Specification: Refuse unresolved day close

**Feature**: 167-close-guard
**Created**: 2026-09-29
**Status**: Draft
**Issue**: #167

## User Scenarios & Testing

### US1: Account for approved work (P1)

As the planner, I cannot close a day while approved work remains unresolved.

Acceptance scenarios:
1. Given an approved open or blocked item without a park or carry record, close
   returns 1 and names the item.
2. Given every approved item merged, parked or carried and no other outstanding
   closing obligations, close returns 0.
3. Given a pushed item branch without a raised or claimed PR, close names the
   branch, even if the item has been parked.

### US2: Resolve owner decisions (P1)

As the owner, I cannot lose a pending decision when the planner closes the day.

Acceptance scenarios:
1. Given a pending owner decision, Stop at day close refuses and names its ID.
2. Retry flags cannot bypass the refusal; unrelated sessions and projects retain
   their existing behavior.
3. Malformed or unreadable evidence refuses with exit 2 and a reason.

### US3: Record build parks (P1)

As the planner, a build loop stopped by repeated failures has a usable park record.

Acceptance scenarios:
1. Repeated failure or exhausted iterations creates a unique D-<n> decision that
   passes decision lint and accounts for the blocked item at close.
2. Existing decisions are preserved; a parked phase alone is insufficient.

## Requirements

- FR-001: Both close entry points enforce identical unresolved-work conditions.
- FR-002: Refusals identify every unresolved item, owner decision and pushed branch.
- FR-003: Unavailable evidence is unmeasured, never clean.
- FR-004: Park decisions carry options, scores, reversibility, outcome and revisit
  criteria in the existing decision format.
- FR-005: Local seat-authored text cannot prove an owner action.
- FR-006: Existing PR, reply, visibility and retro conditions remain enforced.

## Key Entities

Approved item; item worktree and PR link; decision and recorded seat outcome;
externally verified PR disposition; pushed branch.

## Assumptions

- Only today's approved items and decisions participate in the new checks.
- Existing item-to-PR links from #162 and verified PR dispositions are reused.
- A seat park or carry is a valid two-way decision within its own branch or PR,
  recorded through decision routing, with `Outcome: parked <item>` or
  `Outcome: carried <item>`. A phase label or an unrecorded file is insufficient.
- Owner-routed decisions remain pending without externally verified completion.
  Existing owner-authored PR dispositions can provide that completion. Arbitrary
  edits to Outcome do not prove owner approval.
- Pushed means a branch has a remote-tracking ref in the item's recorded worktree.
  No network fetch is added at close. Remote deletion/freshness is outside this fix.
- A merged phase alone is insufficient; the linked PR must be measured as merged.
- Items without a worktree have no branch to inspect. Completed linked PRs are
  measured through the existing PR reader.

## Success Criteria

- All three issue acceptance scenarios have automated regression coverage.
- Each listed unresolved entity appears in the refusal, including mixed failures.
- Build parks pass the same lint used for authored decisions.
- Existing unrelated-project and three-state-exit tests remain green.

## Deferred

A general externally authenticated owner-decision completion command is outside
this issue; existing PR disposition verification remains the supported proof.
