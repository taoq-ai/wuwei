# Specification Quality Checklist: steward trigger

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-10-09
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focused on owner value: fewer steward seats a day, none in the middle of a fix round, and a number to tune from
- [x] All mandatory sections completed
- [x] Root causes are stated with file and line, and the false premise (a steward size trigger) is corrected

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover both acceptance lines of the issue (250 calls give one review; mid-round waits) and the report ask
- [x] Edge cases identified (stuck fix, due while mid-round, running steward, parked item)
- [x] Scope bounded; assumptions recorded, including the rejected steward.ignore

## Feature Readiness

- [x] Every functional requirement maps to acceptance scenarios
- [x] No guard or decision rule changes; no new refusal, no new event kind, no new config key
- [x] Design spec conflict (5.5 default) raised for the owner, not resolved silently
