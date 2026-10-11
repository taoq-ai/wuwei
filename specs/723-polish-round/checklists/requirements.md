# Specification Quality Checklist: polish round

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-10-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focused on owner value: reviewer notes on a pass are fixed in place instead of becoming a new item
- [x] All mandatory sections completed
- [x] The root cause is stated with file and line, reproduced on main

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover every item of the issue (offer with notes, builder round, one gate re-check, PR after, skip, never, always, recorded on the item, notes in the brief)
- [x] Edge cases identified (no notes, FIX at round one, cap used, second opinion, docs-only, light, blocking polish delta, raised item)
- [x] Scope bounded; assumptions recorded

## Feature Readiness

- [x] Every functional requirement maps to acceptance scenarios
- [x] The changed decision rule has its 9.2 invariant (I58)
- [x] The polish record is CLI-written only; a re-check delta is accepted only for the recorded polish gate
