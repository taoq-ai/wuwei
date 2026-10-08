# Specification Analysis Report: 559-calibration

Artifacts: `spec.md`, `plan.md`, `tasks.md`, constitution `.specify/memory/constitution.md`.

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Underspecification | HIGH | spec FR-003, plan | Issue says "per role" but no record or event carries a role; seats share the planner session id, so the CLI cannot see the writer. | Resolved: optional `Role:` record field (FR-001), stored in the CLI-written payload (FR-002); assumption recorded. |
| A2 | Ambiguity | HIGH | spec FR-004, FR-007 | "Calibrated over at least ten records" left the under-ten case open; capping it would drop every default L2 class the day this lands. | Resolved: three states; `too few` blocks promotion only, no cap, no routing change; assumption recorded. |
| A3 | Coverage | HIGH | spec Root cause | Confidence is not in any stored outcome, so no reader can score it. | Resolved: FR-002, T003/T004 add `confidence` to `seat_outcome`. |
| A4 | Inconsistency | MEDIUM | plan routing | `route_owner` and `mandate` compute CISR separately; the stored row could disagree with the route. | Resolved: both pass `ambiguous`, `mandate` stores `cisr: kind` (plan, T016). |
| A5 | Interaction | LOW | plan cruise.level | A spent budget lowers from the capped level and holds the true running level; refill restores the running level and the cap still applies while uncalibrated. Consistent with 5.8.1. | No change. |
| A6 | Behaviour | MEDIUM | spec Assumptions | Promotion now waits for `calibration_min` scored records with stored confidence, which start accruing only after this lands. | Accepted: the rule requires calibration for promotion; recorded under Assumptions. |
| A7 | Behaviour | MEDIUM | spec Assumptions | A role always writing `medium` and always right scores 0.16, above 0.15. | Accepted: owner's mapping and threshold; recorded. |
| A8 | Constitution | none | plan Constitution Check | Test first, stdlib only, no new refusal, no forgeable trust, exits 0/1/2. | Pass. |
| A9 | Duplication | none | plan | Window reader reused from #558 via one keyword; no second reader. | Pass. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001, FR-002 | T003, T004 |
| FR-003 | T007 to T010 |
| FR-004 | T005, T006 |
| FR-005 | T001, T002 |
| FR-006 | T011, T012 |
| FR-007 | T013, T014 |
| FR-008, FR-009 | T015, T016 |
| FR-010 | T017, T018 |
| FR-011 | T019, T020 |
| FR-012 | T021 to T024 |

Every behaviour task has a test task ordered before it. No unmapped task.

## Metrics

- Requirements: 12; tasks: 25; coverage 100 percent.
- CRITICAL: 0; HIGH: 3 (all resolved in the artifacts); MEDIUM: 3; LOW: 1.
