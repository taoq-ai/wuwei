# Specification Quality Checklist: tickets from the card

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-10-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focused on owner value: an approved plan starts with no terminal command for tickets
- [x] All mandatory sections completed
- [x] Root causes are stated with file and line, reproduced through the real hook

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover the three acceptance lines of the issue (links and draft on Approve, strict prints, a builder is refused naming the planner)
- [x] Edge cases identified (skip tiers, rerun, adapter failure, already approved, tracker-discovered ids)
- [x] Scope bounded; assumptions recorded (no title matcher, no tracker link verb, strict keeps refuse-and-list)

## Feature Readiness

- [x] Every functional requirement maps to acceptance scenarios
- [x] The guard change carries a 9.2 invariant row (I36) and its check
- [x] Design spec conflict (5.11 reason and writers) raised for the owner, not resolved silently
