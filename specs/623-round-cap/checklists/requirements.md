# Specification Quality Checklist: round cap

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-10-09
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focused on owner value: rounds end at a configurable cap, notes ship, blockers park with a record
- [x] All mandatory sections completed
- [x] The root cause is stated with file and line, reproduced on main

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover every item of the issue (notes ship after the cap, blocking park with record, `max_rounds = 1`, per tier, scope rule, report)
- [x] Edge cases identified (gates that passed earlier, every gate rotated, second opinion, manual transitions, PR stage reset)
- [x] Scope bounded; assumptions recorded

## Feature Readiness

- [x] Every functional requirement maps to acceptance scenarios
- [x] The changed decision rule has its 9.2 invariant (I35)
- [x] A trust-boundary security finding still always blocks
