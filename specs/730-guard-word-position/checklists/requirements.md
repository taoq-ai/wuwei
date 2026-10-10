# Specification Quality Checklist: the command guard judges words by position

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details beyond the root cause and the shared spots it names
- [x] Focused on the seat's and the owner's outcome (ordinary searches pass, owner actions stay refused)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain (answered under Clarifications)
- [x] Requirements are testable and unambiguous (each FR maps to tasks T001 to T012)
- [x] Success criteria are measurable (exit codes on named commands, full suite green)
- [x] Acceptance scenarios cover the issue's three Acceptance rows
- [x] Edge cases identified (bypass forms, scope outside a workspace, pre-flight commands)
- [x] Scope is bounded (interpreters and argument-position variables deferred)
- [x] Dependencies and assumptions identified (#671 overlap, missing notes file)

## Feature Readiness

- [x] Every functional requirement has acceptance scenarios
- [x] User scenarios cover the primary flows (search, variable, refusal text)
- [x] No existing refusal is weakened (FR-007, SC-002)

## Notes

- The reproduction ran in a throwaway fixture workspace; no orchestrator notes file exists for #730.
