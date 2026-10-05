# Specification Quality Checklist: Decision classes (MIT CISR) and fewer cards

**Purpose**: Validate specification completeness and quality before planning
**Feature**: [spec.md](../spec.md)

## Content quality

- [x] Root cause stated with file and line
- [x] Acceptance scenarios come from the item's Acceptance section
- [x] No [NEEDS CLARIFICATION] markers; open points answered under Assumptions

## Requirement completeness

- [x] Requirements are testable and unambiguous (class rule, margin, outputs named)
- [x] Edge cases identified (repeat route, CLI-owned cards, old state, close)
- [x] Scope bounded: what must not change is listed in the plan
- [x] No new refusal under observe or guarded

## Feature readiness

- [x] Every functional requirement maps to a test task before its implementation task
- [x] Success criteria are verifiable by the suite
