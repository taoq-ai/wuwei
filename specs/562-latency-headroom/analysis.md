# Specification Analysis Report: 562-latency-headroom

Artifacts: spec.md, plan.md, tasks.md, against `.specify/memory/constitution.md` and the
item's Acceptance section.

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Coverage | HIGH | spec SC-002, tasks T023 | SC-002 first asked a 25 percent above-floor cut on all four paths; push and PreToolUse are within 1 to 2 percent of their SC-001 figure on the last green run, so the bar was arbitrary and possibly unreachable by removing work. | Resolved: 25 percent for the status line, 10 percent for PreToolUse, SessionStart and push, with the runner gap stated. |
| A2 | Underspecification | HIGH | tasks T005 | The integrity import test was conditional ("only if profiling shows"), so no test pinned FR-002. | Resolved: a fresh-interpreter test asserts `import wuwei.integrity` leaves `wuwei.registry` unloaded. |
| A3 | Inconsistency | HIGH | plan item 1, spec FR-001 | The plan kept `seats` (`state.running_by_goal`, #487) in the line snapshot although `_groups` never renders it; the issue names #487 as cost to remove. | Resolved: seats per goal skipped for the line in FR-001 and plan item 1. |
| A4 | Coverage | MEDIUM | spec US1.1, SC-001 | Runner figures cannot be produced locally. | Accepted: recorded under Assumptions; SC-002 and SC-003 are the local gates, the job confirms SC-001. |
| A5 | Ambiguity | MEDIUM | spec FR-007 | "Moved most" could be absolute or relative. | Resolved in spec Assumptions: relative change of the budgeted measure; T016(b) pins the 15 ms scenario against a 20 percent heartbeat rise. |
| A6 | Constitution | MEDIUM | plan item 9 | Collapsing the walk could silently drop coverage if a declared read set is wrong. | Resolved: `UNREAD` sentinel raises on any use; T020 pins it; exact case count asserted. |
| A7 | Underspecification | LOW | plan items 4 and 5 | Further SessionStart, PreToolUse and push cuts depend on profiling not yet run. | Accepted: tasks T012 and T013 require a pinning test before each cut and the figures in the PR body. |
| A8 | Coverage | LOW | spec FR-010 | Docs figures need a quiet host. | Accepted: figures added only when measured quietly. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T002, T003, T004 |
| FR-002 | T005, T006 |
| FR-003 | T007, T008 |
| FR-004 | T009, T010, T011, T012 |
| FR-005 | T012, T013 |
| FR-006 | T014, T015 |
| FR-007 | T016, T017 |
| FR-008 | T018, T019 |
| FR-009 | T020, T021 |
| FR-010 | T022 |
| SC-002, SC-003 | T001, T021, T023 |

Every behaviour has a test task before its implementation task. No refusal is added or
changed (#530), no planner action changes (#551), no budget, probe or job setting is
loosened (#346); the invariant bound is tightened from 3.0 to 1.0 s. No new rule, so the
9.2 invariant table is unchanged.

CRITICAL: 0. HIGH: 3, all resolved in the artifacts. MEDIUM: 3. LOW: 2.
