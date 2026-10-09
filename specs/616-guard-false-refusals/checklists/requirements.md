# Specification Quality Checklist: guard false refusals on a published merge and on read-only gate reads

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-10-09
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focused on owner value: a merged branch pushes and the planner's reads are not refused
- [x] All mandatory sections completed
- [x] Root causes named with the functions that carry them

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover both bugs of the request
- [x] Edge cases identified (foreign commit on no remote, new branch, forged tracking ref, quality caller on a security gate, interpreter snippets)
- [x] Scope bounded; assumptions recorded; the design 9.2 rows are raised

## Feature Readiness

- [x] Every functional requirement maps to acceptance scenarios
- [x] No new refusal under any posture (#530); two guard rules narrowed, each with its invariant test
- [x] Records floor kept: every call that can write a gate file is still linted
