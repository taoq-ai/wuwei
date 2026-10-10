# Specification Quality Checklist: one broken main is one fix item

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-10-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focused on owner value: one break on main costs one fix item, not a builder round per item
- [x] All mandatory sections completed
- [x] Root cause stated with file and line, reproduced on main

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover both acceptance lines of the issue (two items on one fix item with no fix round; the fix ships and both rerun)
- [x] Edge cases identified (own-file failures, test failures, mixed failures, unreadable diff, self-hold, repeat break after a merged fix, a parked fix item releasing and never re-holding, two repositories, Codex loop)
- [x] Scope bounded: fast checks only; CI checks and #637 deferred with reasons
- [x] Dependencies and assumptions identified (built on main without #646 or #637 by owner directive; the path heuristic ceiling)

## Feature Readiness

- [x] Every functional requirement maps to acceptance scenarios
- [x] The new hold rule carries a 9.2 invariant row (I57) and its check
- [x] No conflict with the design spec: the build loop rule gains a dated amendment line
