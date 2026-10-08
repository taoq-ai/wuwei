# Specification Analysis Report: 560-shadow-promotion

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
and the issue's Deliver and Acceptance sections.

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Constitution (#530, no new refusal) | HIGH | plan 6 | `wuwei cruise shadow` was not in `commands.READ_ONLY`, so the protect_state guard would treat a read-only print as a record command (a card below strict, a refusal under strict). | Fixed: plan 6 and T015/T016 add it to `READ_ONLY`; docs `reference.md` and `agent.md` list it (T018). |
| A2 | Coverage | MEDIUM | spec US3, plan 10 | The I13 invariant check is pure (`level()` ignores `shadow`); the full live-route equality is asserted in `tests/test_cruise.py` (T005), not in the invariant walk, because a route per case would break the walk's 3 s CPU budget. | Accepted: T005 compares outcome row, payload, file and output with and without a shadow. |
| A3 | Ambiguity | MEDIUM | spec FR-006 | What happens after `shadow_days` with fewer than `shadow_min` scored. | Resolved in Assumptions: the shadow keeps running, no expiry. |
| A4 | Ambiguity | MEDIUM | spec FR-003 | "The gate asks once" with a `keep` answer. | Resolved: the card write ends the shadow; a new proposal needs fresh agreements (FR-007). |
| A5 | Underspecification | LOW | spec Edge Cases | A shadow-write failure after the live route. | Resolved: stderr warning, live exit unchanged (plan 4). |
| A6 | Consistency | LOW | tasks T007, T013 | Three existing tests assert the old card-on-count flow. | Covered: T007 and T013 update them before the code. |
| A7 | Trust | LOW | plan 8 | `decision_shadows` and `decision.shadow` are read by the scorer. | Covered: reserved to `wuwei decision route` (T005/T006). |

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 config | T001, T002 |
| FR-002 stored shadow, writer | T003, T004 |
| FR-003 start, passed card, asked once | T007-T010 |
| FR-004 raise gate, ledger counts, level write clears | T003, T009, T010, T013 |
| FR-005 shadow answer at the routing point | T005, T006 |
| FR-006 scoring, end, pass | T009-T012 |
| FR-007 fresh agreements after an end | T011, T012 |
| FR-008 command, status, report | T015, T016 |
| FR-009 design, invariants, docs | T017, T018 |
| FR-010 no refusal | A1 fix, T005, T017 |

Every behaviour has a test task ordered before its implementation task. No unmapped tasks.

## Metrics

- Requirements: 10; tasks: 19; coverage 100 percent.
- CRITICAL: 0; HIGH: 1 (resolved); MEDIUM: 3 (resolved or accepted); LOW: 3.
