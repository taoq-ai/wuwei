# Specification Analysis Report: 865-zero-diff-checks

Artifacts reviewed: `spec.md`, `plan.md`, `tasks.md`, constitution, the design spec's build loop, and the existing check path.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | An empty committed diff alone can hide uncommitted work. | FR-001 and T003 require the shared status reader before a skip. |
| A2 | HIGH | A skipped check could be mistaken for passing evidence. | The plan keeps configured commands on the build record, scopes the skip to one check invocation, and records an explicit skip reason; it does not write passing fast-check evidence. |
| A3 | HIGH | A failed diff read could be mistaken for an empty diff. | FR-004 and T003 require exit 2 with a reason. |
| A4 | MEDIUM | A code-producing item with no new commit may still park. | FR-005 preserves `_unbuilt`; issue #997 owns that parallel path. This issue prevents a missing-linter park. |
| A5 | MEDIUM | `npm run lint` lacks the relative executable fallback. | The spec records it under Deferred; the current fallback and `[checks] bootstrap` remain available for changed items. |

**Coverage**: FR-001: T002, T003, T004, T005; FR-002: T002, T004; FR-003: T003, T005; FR-004: T003, T005; FR-005: T005, T007.

**Result**: 0 open CRITICAL or HIGH findings. The requirement and task order are consistent.
