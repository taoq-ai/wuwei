# Specification Analysis Report: 567-process-depth

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.4.0), design 5.3, 5.6 and 5.8, and issue #567.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Security / inconsistency | HIGH | spec FR-001, plan `dispatch.depth` | The first draft let the builder's predicted `depth` (computed at brief time on a near-empty diff) lighten gate checks: an item briefed and gated without `dispatch next` tiering it would pass three gates with three-row verdicts. | Resolved: `depth(row, gate=True)` reads only the tier `dispatch next` recorded from the real diff, else `standard`; every gate reader (gate brief line, `verdict.light`, `_recorded_gates`, `_seats`, sentinel retro) uses it; T001 and T015 test the case. |
| A2 | Coverage | MEDIUM | spec US2 scenario 2 | "The verdict says so" for a skipped step zero is instructed in the brief (exact `Mutation: skipped (depth standard)` row) but not enforced by the lint. | Accepted: enforcing it is a new refusal, which #530 forbids under observe and guarded. Recorded under Assumptions. |
| A3 | Ambiguity | MEDIUM | spec Assumptions | Light depth only occurs when a repository sets `gates.floor = "light"`; the default floor is `standard` (#280). | Recorded under Assumptions with the overturn; the standard column (classes by diff, mutation on guard code) is the default gain. |
| A4 | Ambiguity | MEDIUM | spec FR-009 | "Without a delta round" for light: the plan keeps the `delta` round key and continues the same seat with re-read feedback. | Recorded under Assumptions: one state machine for receive, the PR gate check and the budget; T021 asserts the feedback differs. |
| A5 | Underspecification | MEDIUM | plan `CLASS_PATHS` | The class glob table is a heuristic; a class can be missed at standard. | Accepted: sentinels still check their classes independently (charters keep the class ownership); the table is one constant the owner can tune. |
| A6 | Performance | LOW | plan `verdict.lint_file` | The PostToolUse verdict lint now reads day state once per gate write. | Accepted: one JSON read on a gate write; failures fall back to today's shape. |
| A7 | Constitution | LOW | plan Docs and design | Constitution: the design spec is amended only by its owner. | The owner wrote the rule as a design 5.3 amendment in the issue; the amendment carries "(owner, 2026-10-08, #567)" like earlier items. |
| A8 | Coverage | LOW | issue Deliver, "SubagentStop" | `seat.py stop_with_report` and the Codex adapter lint through `lint_file`. | Covered without a task: both inherit `light` through `lint_file`. |
| A9 | Terminology | LOW | issue "eleven-row" | The builder charter lists ten classes; the verdict regex accepts twelve. | Recorded under Assumptions: the CLI table covers the ten builder classes. |

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T001, T002 |
| FR-002 | T007, T008 |
| FR-003 | T009, T010 |
| FR-004 | T011, T012 |
| FR-005 | T003 to T006 |
| FR-006 | T013, T014 |
| FR-007 | T015 to T018 |
| FR-008 | T019, T020 |
| FR-009 | T021, T022 |
| FR-010 | T023, T024 |
| FR-011 | T025 to T028 |
| FR-012 | T031, T032 |
| FR-013 | T033 |
| FR-014 | T013, T015, T019 (no new refusal: every change lightens a check or adds a read-only command) |
| SC-001, SC-002 | T029, T030 |
| SC-003 | T031 |
| SC-004 | T034 |

Every behaviour task has its test task ordered first. No task is unmapped.

## Constitution alignment

- I stdlib: no dependency added.
- II exits: `sweep classes` exits 0 or 2 with the reason; unresolvable depth falls back to the
  current shape, never to clean.
- III one behaviour, one function: `dispatch.depth`, `dispatch.tier` (unchanged), `verdict.lint`,
  `verdict.light`; callers reuse them.
- IV test first: enforced by task order.
- V ponytail: one helper, one table, one keyword; charters shrink (SC-003).
- VII security: depth comes from CLI-written state; the gate tier alone lightens gates (A1).
- #530: no new refusal. #551: the builder's sweep is a command the brief names.

## Metrics

- Requirements: 14 functional, 4 success criteria. Tasks: 34.
- Coverage: 100 percent of requirements have at least one task.
- CRITICAL: 0. HIGH: 1 (resolved). MEDIUM: 4 (accepted, recorded). LOW: 4.
