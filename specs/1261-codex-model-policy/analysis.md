# Specification Analysis Report

Read spec.md, plan.md, tasks.md, data-model.md, research.md and the constitution after the prerequisite check.

| ID | Category | Severity | Location | Summary | Recommendation |
| --- | --- | --- | --- | --- | --- |
| None | Consistency | None | All artifacts | No unresolved critical, high, medium or low finding. | Proceed with final checks. |

| Requirement | Covered | Tasks |
| --- | --- | --- |
| FR-001 mapping | Yes | T001, T002, T003 |
| FR-002 precedence | Yes | T002, T003 |
| FR-003 shared generation/doctor | Yes | T002, T003 |
| FR-004 distinct metadata | Yes | T004, T005, T008, T009 |
| FR-005 report and no attestation | Yes | T004, T005, T006 |
| FR-006 budgets and reuse | Yes | T003, T005, T007 |
| SC-001 consumer tests | Yes | T002, T004, T007 |
| SC-002 route differential | Yes | T007 |
| SC-003 checks and artifacts | Yes | T006, T007 |

Constitution: stdlib only, six config keys, test first, existing records and no added refusal. Runtime is 3,787 lines, +21 against parent 2864b109, within both caps. Source deletes the obsolete no-model docstring and Codex advice skip.

Metrics: 9 requirements and criteria, 9 tasks, 100% coverage, 0 ambiguity, 0 duplication, 0 critical or high findings, no unmapped tasks. Scope and precedence are consistent across the artifacts. Fork policy records a request, never measured inheritance.

Validation: generation red 8, telemetry red 8, malformed metadata red 1. Whitespace and fresh-fork advice each had a failing consumer check before a one-line fix. Focused green 119 and wider green 356. Route differential: 288 routes, 1,152 cases per tree, zero moved verdicts/reasons against original main and immediate parent. Initial full suite: 3,811 passed, 7 skipped at cacc2c2c. Final focused checks cover the two validation fixes. Parent metadata and concurrency fix integration is pending and will be verified separately.

Parent integration: e341ab45 includes the shared sanitizer and identity/report fixes. Ten new metadata consumer cases failed before integration, then the Codex/model/hook suite passed 768 tests. Brief requested models are extracted from the fully scrubbed prompt before clipping; all new turn/fork fields are inside the shared sanitized seat dictionary. The final 1254 retention follow-up and root's combined full suite remain pending.

First native FIX round at 702986c1: two blocking defects and one advice inconsistency were reproduced. Expanded consumers ran red with 13 failures and 9 passes. The single fix batch accepts only nonblank strings for turn metadata, requires a separate effort token, and shares requested-model extraction. Codex/model consumers plus vendor and runtime checks then passed 164 tests. Both blocking findings are addressed; native delta review remains pending. No shell command parser changed and no full suite was repeated.
