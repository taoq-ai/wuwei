# Specification analysis: 522-plain-tone

Artifacts read: `spec.md`, `plan.md`, `tasks.md`, `.specify/memory/constitution.md` (1.4.0).

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Inconsistency | HIGH | tasks.md T006, T005 | The base measurement said "before changing any text", but T005 already adds the reference row, so the order was ambiguous and the before column could mix in new text. | Resolved: T006 now runs before any existing text changes (Phases 4, 5 and 7); the new row is held to the rule by the lint itself. |
| A2 | Underspecification | HIGH | plan.md test_tone cards | `_text` returns `(text, family)` pairs; the plan used it as a list of strings, which would measure tuples. | Resolved: plan.md says to take the texts of the pairs. |
| A3 | Inconsistency | MEDIUM | spec.md root cause, plan.md | Line ranges for `gate_widget` did not match the base (`approves` starts at line 257). | Resolved: spec cites 257-265, plan cites 247-272. |
| A4 | Inconsistency | MEDIUM | spec.md FR-002, US2, US3 | "average at most 20" against the rule text "under 20". | Resolved: every artifact uses under 20 (`average < 20`); exit 1 at 20 or more. |
| A5 | Test first | MEDIUM | tasks.md T009 | The `why last refusal` acceptance test may pass on the base if the records floor reason is already short, so it would not fail first. | Accepted: it is an acceptance check over existing text; T011 rewrites the reason only if it fails. T012 (budgets) is the failing test that drives the pass. |
| A6 | Ambiguity | MEDIUM | spec.md FR-005, tasks.md T014 | "Every guard reason reread" has no measurable end beyond the class budget. | Accepted: the reasons budget (0 over 35, nominal rate at or below before) is the measurable gate; the reread is the pass itself. |
| A7 | Scope risk | MEDIUM | tasks.md Phase 7 | The pass touches about 250 reason literals, 4 skills, 11 charters and 3 docs pages, with many tests asserting text. One fix round may not be enough. | Mitigated: each task greps tests and docs before a change and runs its focused tests; meaning unchanged; no assertion deleted. |
| A8 | Coverage | LOW | spec.md SC-002 | "Average lower than before" for concepts, daily and README is recorded in research.md but not asserted. | Accepted: the per-file lint exit 0 (T019) and the research table cover it. |
| A9 | Constitution | LOW | Workflow | Strict mode lists clarify and checklist; this run does specify, plan, tasks and analyze. Clarify questions are answered under Assumptions (AGENTS.md). | Checklist runs before implement, as the pipeline schedules it. |
| A10 | Efficiency | LOW | tests/test_tone.py | The budget test parses every CLI module again (test_reasons does too). | Accepted: well under a second; no shared cache for one caller. |

No CRITICAL finding. Both HIGH findings are resolved in the artifacts.

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 Plain tone rule | T007, T008 |
| FR-002 measure and command | T001, T002, T003, T005 |
| FR-003 read-only, help group, reference row | T004, T005 |
| FR-004 class budgets | T006, T012, T020 |
| FR-005 the pass | T011, T013, T014, T015, T016, T017, T018, T019 |
| FR-006 before and after table | T006, T020 |
| US3 why and cards | T009, T010, T011 |
| SC-003 full suite | T021 |

Every functional requirement has at least one task; every behaviour task has a test task
before it.

## Constitution alignment

- I stdlib: `re` and `pathlib` only.
- II exits: 0 at the rule, 1 over it, 2 with a reason when a path cannot be read.
- III one function: `measure` is shared by the command and the test.
- IV test first: tests precede each implementation task (A5 noted).
- V ponytail: no new core module, no config, a marked suffix heuristic.
- #530 and #551: no refusal added or changed, no planner path change.

## Metrics

- Functional requirements: 6; tasks: 22; requirements with tasks: 6 of 6.
- CRITICAL: 0; HIGH: 2 (resolved); MEDIUM: 5; LOW: 3.
