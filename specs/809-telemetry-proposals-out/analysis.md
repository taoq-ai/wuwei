# Specification Analysis Report: 809-telemetry-proposals-out

Artifacts read: spec.md, plan.md, tasks.md, `.specify/memory/constitution.md` (1.5.0), the
#789 pass plan (part 6 and the owner constraints), issue #809, and the code at main `221f1f2`.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|---|---|---|---|---|---|
| C1 | Constitution | CRITICAL (resolved) | spec Assumptions; plan item 17 | The constitution lets only the owner amend the design spec; 5.13 defines the proposals. | #789 is the owner's instruction (2026-10-11); every 5.13 edit is marked "(owner, 2026-10-11, #789)". |
| I1 | Inconsistency | HIGH (resolved) | pass plan PR 6 line vs issue #809 | An older plan line scoped part 6 wider than the owner's later call. | The issue governs: only proposals go; telemetry, its weekly counts and DORA stay (spec Assumptions, plan Summary). |
| U1 | Underspecification | HIGH (resolved) | spec FR-007, US3; tasks T004 | Old week files hold `proposals`, `evidence` and `presented`; a strict reader would break preview, send or sharing after the upgrade. | `payload` already picks `KEYS` only and `load_week` checks only `week`; T004 adds one test that a legacy week loads, previews and validates. |
| U2 | Underspecification | HIGH (resolved) | plan item 2, Risks | `latest_final` is called by `_proposals` and by `_final` (preview, send). Deleting it with the action would break kept commands. | Plan and T007 keep it explicitly. |
| G1 | Coverage | MEDIUM (resolved) | FR-005; T002 | The `next` row had only a pass assertion; deleting the row needs a failing test first. | T002 asserts no `next.action` names `telemetry`. |
| G2 | Coverage | MEDIUM (resolved) | FR-006; T009 | `tests/test_signal_status.py` compares emitted kinds to an expected table; dropping the producer without the tuple fails it. | T009 removes `presented` from the tuple, `signal.SILENT` and the event map together. |
| R1 | Risk | MEDIUM | plan Risks; T001, T010 | Parts 3 and 4 remove or rename lines this part edits (`guide.py`, `WRITES`, agent.md block, the docs guide assertion, the `nudge` tier). | T001 rebases first; T010 is conditional; T009 follows part 4's tier name. |
| R2 | Risk | LOW | plan Risks | `tests/test_dora.py` imports `write_day` from `tests/test_telemetry.py`. | Helper kept; T008 runs `test_dora.py`. |
| A1 | Ambiguity | LOW | spec Edge Cases | An old `telemetry.presented` event on the upgrade day classifies as an unknown kind. | Accepted in Assumptions: one day, nothing counts it. |
| C2 | Constitution | LOW | constitution Constraints | The constitution sentence "What it derives is a proposal the owner applies" goes stale. | T013 deletes it with a patch bump. |
| C3 | Constitution | LOW | constitution Workflow (9.2 invariant rule) | Applies to guard and decision-rule changes. | No guard or decision rule changes. |

No CRITICAL or HIGH finding is open.

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 | T007, T008 |
| FR-002 | T006, T007 |
| FR-003 | T006, T007 |
| FR-004 | T004, T005 |
| FR-005 | T002, T003 |
| FR-006 | T009 |
| FR-007 | T004 |
| FR-008 | T010 |
| FR-009 | T011, T012, T013 |

Every task maps to a requirement; no requirement is without a task.
