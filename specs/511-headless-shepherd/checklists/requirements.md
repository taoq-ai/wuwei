# Specification Quality Checklist: Headless shepherd

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-08
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Root cause stated with file and line
- [x] Focused on the owner's need (PRs keep moving overnight, the morning starts with what happened)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain (answered under Assumptions)
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover the three Acceptance bullets of the issue
- [x] Edge cases are identified (live planner, owning day, unreadable PR, lock held, dedup)
- [x] Scope is bounded: two of the three scheduling variants deferred with reasons
- [x] Dependencies and assumptions identified

## Program principles

- [x] #530: no new refusal under any posture (FR-013)
- [x] #551: the session path of `shepherd schedule` returns an action (command, why, then, card), not prose
- [x] No model call at night (FR-004, SC-002)
- [x] Trusted records are producer-only (FR-006, FR-007)

## Notes

- Deferred: Claude Code scheduled task variant (a model call per run) and repository workflow
  variant (no workspace on a code-host runner).
