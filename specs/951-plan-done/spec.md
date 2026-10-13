# Owner completed plan items

**Feature Branch**: `951-plan-done`  
**Created**: 2026-10-13  
**Status**: Ready  
**Input**: Issue #951

## User Scenarios & Testing

### Owner completes outside a build (P1)

Given a planned, parked, or implementation item with no live seat, when the owner answers Yes on an item and reason bound Owner step card and reruns `wuwei plan done <id> --reason "<text>"`, the item becomes done with owner attribution and that reason. A missing, mismatched, No, or spent Yes, or a live seat, refuses without changing the item. A live seat refusal names `seat stop`.

### Day end reflects completion (P2)

Given an owner completed item, the report lists it under Done with its reason and any recorded worktree or branch. Close does not flag it as open, and Parked and Carry do not list it. Existing worktrees and branches remain untouched.

### Edge Cases

Empty reasons, unknown items, unsupported phases, and already done items are refused.

## Requirements

- **FR-001**: `plan done` MUST accept planned, parked, and implement items with a nonempty reason.
- **FR-002**: It MUST refuse live work on that item and name `seat stop`.
- **FR-003**: It MUST require one unspent Yes bound to item and reason through `needs_owner`.
- **FR-004**: It MUST record `status: done`, `by: owner`, the reason, and an event.
- **FR-005**: Report MUST show it under Done; close, Carry, and Parked MUST omit it.
- **FR-006**: Recorded worktrees and branches MUST be preserved and listed in the report.
- **FR-007**: Done items MUST release build capacity and held builds, and MUST not offer a plan resume decision.
- **FR-008**: Manual `build next` MUST return done without launching work for an owner completed item.
- **FR-009**: Carry and park MUST refuse a done item; `why` MUST show the owner completion and reason.
- **FR-010**: The completion event MUST be silent in attention status and the public reference MUST list the command and Owner step.

## Success Criteria

- All three allowed starting states complete with one matching Yes.
- Every refusal causes zero completion writes.
- The report shows an owner completed item once under Done, never under Carry or Parked.

## Assumptions

- Live work includes registered running seats, including adhoc seats, and live build checks or loops for the item, as reported by `state.in_flight`.
- The reason is normalized to one line like `plan park`.
- `by` and `reason` are direct item fields. Completion leaves the phase unchanged; done status is terminal.
- Already done items are refused so a rerun cannot replace the original reason.
- A terminal done status takes precedence over the retained phase in CAP accounting, held builds, parked decisions, manual build routing, and why. No design spec edit is proposed.
