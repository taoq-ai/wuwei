# Specification Quality Checklist: delete the invariant walk and the prose-pinning tests

**Purpose**: Validate specification completeness and quality before implementation
**Created**: 2026-10-11
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] Every removed unit is classed (a) process machinery or (b) a real process-error check
- [X] Every (b) unit names the passing test that holds it after the change
- [X] No kept test or budget is loosened; tests go only with the walk or the prose they pin
- [X] No emojis, no em-dashes, no absolute local paths, no client, repository or people's names

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain; open questions answered under Clarifications
- [X] Every file to edit is named with what changes; no file is deleted
- [X] CI workflows, scripts and config checked for walk and budget references
- [X] Success criteria are measurable (one test collected, grep empty, version 2.0.0)
- [X] Edge cases named (timing list, tone budget, instruction lint, shared helpers)

## Feature Readiness

- [X] Every functional requirement maps to a task (analysis.md Coverage)
- [X] Moved tests are shown red once by a temporary mutation
- [X] The new 9.2 text is given verbatim in plan.md
- [X] No CRITICAL or HIGH finding is open in analysis.md
