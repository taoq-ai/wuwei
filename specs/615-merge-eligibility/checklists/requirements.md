# Specification Quality Checklist: merge eligibility after a real day

**Purpose**: Validate specification completeness and quality before planning
**Created**: 2026-10-09
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focused on owner value: merges the policy should clear are no longer kept with the owner
- [x] All mandatory sections completed
- [x] Each of the three bugs names its cause and its fix

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Acceptance scenarios cover the three bugs of the report
- [x] Edge cases identified (item with evidence, unmeasured repository, rename across an excluded path, excluded never-auto file)
- [x] Scope bounded; assumptions recorded; the design spec conflict is raised

## Feature Readiness

- [x] Every functional requirement maps to acceptance scenarios
- [x] No new refusal under observe or guarded (#530); fail closed where a fact is unmeasured
- [x] Only the owner's answer writes `merge_deploys = false`; calibration still never proposes it
