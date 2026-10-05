# Specification Analysis Report: 528-cap-from-host

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against
`.specify/memory/constitution.md` (1.4.0) and design spec sections 5.3, 5.13, 9 and 15.8.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Constitution | HIGH (raised as a possible CRITICAL) | plan.md Design 1 and 7; constitution Constraints (telemetry) | The launch guard (a hook) would read `seat.usage` token totals and apply a derived bound; the constitution says telemetry aggregation runs only in CLI commands and telemetry derivations are proposals the owner applies. | Checked against the design spec, which wins: 5.3 records `seat.usage` per iteration for cost and 15.8 has the agent-launch guard refuse a launch that would cross the daily token cap on the same events. The bound applies the owner's own `tokens_per_day`; no record is added in the hook. Not telemetry (5.13). Stated in plan.md Constitution Check. | Resolved |
| U1 | Underspecification | HIGH | issue Acceptance 1; tasks T019 (first draft) | The first draft of T019 launched a fifth builder on a four-item fixture and, with a constant fake memory, a live fit would never reach CAP. | T019 now launches three, drops the fake to the floor and expects `CAP 3` from the live derivation. | Resolved |
| I1 | Inconsistency | HIGH | spec Assumptions (SessionStart); issue Scope bullet 1 | The issue says derive on init and every SessionStart; the plan derives at plan propose and at every enforcement point and adds nothing to SessionStart. | Kept, recorded as an assumption with the overturn condition: every launch path re-derives live, so a SessionStart derivation would only display; init writes the derived default `0`. | Resolved (assumption) |
| I2 | Inconsistency | MEDIUM | spec FR-001; existing workspaces' `cap = 1`, `seats = 4` | Existing workspaces keep the old template's explicit values as owner overrides, so they stay at cap 1 until the owner sets `cap = 0`. | Recorded under Assumptions and Deferred; the plan line names what the host fits next to an owner value. The orchestrator may file the migration as a follow-up. | Accepted |
| A1 | Ambiguity | MEDIUM | spec US2 scenario 3 | "Launch as many seats as fit the remaining budget" with zero fitting. | CAP floors at 1 with `(budget)` (state requires `cap >= 1`; the 15.8 governor owns the 100 percent stop). | Resolved (assumption) |
| A2 | Ambiguity | MEDIUM | spec FR-003 | Per-seat token cost source and the unmeasured case. | Median input plus output per `seat.usage` row on the newest day that has any; no bound while unmeasured, said in the text. | Resolved |
| R1 | Risk | MEDIUM | plan.md Test fallout; T000, T025 | Defaults move from 1 and 4 to derived, and `plan propose` now measures the host; tests on the real host adapter become machine dependent. | T000 pins `os.cpu_count` in the Day fixture; T025 adds `cap = 1` only where a test depends on one builder. | Resolved |
| P1 | Performance | LOW | plan.md Design 7 | The guard now scans day directories for the seat cost and reads today's events for the budget on each Agent launch (#346 latency). | Accepted: Agent launches are infrequent and the guard already reads the day's events for briefs. | Accepted |
| T1 | Ordering | LOW | tasks T012, T017 | `cap_bound` is producer-owned by default, so the state part of T017 passes before T012; the event part fails first as required. | No change. | Accepted |
| D1 | Docs | LOW | tasks T024 | The `docs/site/configuration.md` `cap` row is read by a test for `calibrate` and `morning gate`. | Noted in plan.md section 11. | Resolved |

## Coverage Summary

| Requirement | Has task? | Task IDs | Notes |
| --- | --- | --- | --- |
| FR-001 defaults 0, template | yes | T001, T002 | |
| FR-002 shared derivation | yes | T005, T007 | |
| FR-003 token budget | yes | T003, T004, T006, T007, T015 | |
| FR-004 plan propose and template | yes | T010, T011, T012 | |
| FR-005 approve records bound | yes | T010, T012 | |
| FR-006 launch set re-derives | yes | T013, T014, T015, T016 | |
| FR-007 guard and opinion | yes | T019, T020 | opinion covered by the shared helper and the full suite |
| FR-008 status line | yes | T021, T022 | |
| FR-009 calibrate never proposes cap | yes | T008, T009 | |
| FR-010 gate card | yes | T010, T012 | |
| FR-011 reserved event and key | yes | T017, T018, T012 | |
| FR-012 docs and design 5.3 | yes | T023, T024 | |
| SC-001 to SC-003 | yes | T013, T015, T011 | |
| SC-004 suite green, no new refusal | yes | T025 | |

## Constitution Alignment

- Stdlib only, three-state exits, one behaviour one function (`calibrate.host` is the only
  derivation), test first (every behaviour task follows its test task), ponytail (no new
  module or port): aligned.
- Autonomy (#530): no new refusal; CAP and `host.seats` refusals keep their texts and the
  `seats` area posture.
- Telemetry constraint: see C1, resolved by the design spec's 5.3 and 15.8.
- `tests/test_invariants.py` is absent on this base; #530 part E adds the #528 row.

## Unmapped Tasks

T000 (fixture), T026 (hygiene).

## Metrics

- Functional requirements: 12; success criteria: 4
- Requirements with at least one task: 12 of 12 (100 percent)
- Ambiguity count: 2; duplication count: 0
- CRITICAL issues: 0 open; HIGH issues: 3 found, 3 resolved

## Next Actions

No CRITICAL or HIGH finding is open; implementation may proceed.
