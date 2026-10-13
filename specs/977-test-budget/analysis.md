# Specification Analysis Report: 977-test-budget

Artifacts reviewed: `spec.md`, `plan.md`, `tasks.md`, constitution, CI count step, and the issue.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Reducing function definitions alone could silently remove case coverage. | FR-002 and FR-004 require original inputs and assertions plus per-file collected-count comparison; T004 and T007 enforce them. |
| A2 | HIGH | A generic wrapper could hide unrelated tests while satisfying the regex. | Identical bodies use a common table. Cases with different assertion shapes group only under a shared named behavior and fixture signature; their original bodies stay in named scenario functions. A broad grouping by shared setup was reverted during implementation. |
| A3 | MEDIUM | Whole-suite collection could change for unrelated reasons. | Record baseline node IDs and compare counts per changed file. |
| A4 | MEDIUM | The existing CI test checks synthetic counts only. | T002 adds a regression for the real suite count before consolidation. |

**Coverage**: FR-001: T002, T007; FR-002: T003, T004, T007; FR-003: T004, T008; FR-004: T001, T005, T007; FR-005: T006, T008.

**Result**: 0 open CRITICAL or HIGH findings. No design-spec change or runtime code is needed.
